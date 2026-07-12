# -*- coding: utf-8 -*-
# Beeta Desktop Environment
# Copyright (C) 2023-2026 Beeta Technologies Inc.
# Licensed under GNU General Public License v3.0

"""PAM Authentication Module for Beeta Lock.

Uses ctypes to interface directly with libpam.so.
Supports conversational PAM, enabling features like fprintd (fingerprint)
and howdy (face unlock) automatically if configured on the system.
"""

import ctypes
import ctypes.util
import getpass
import pwd
import os
import threading

libpam = ctypes.CDLL(ctypes.util.find_library("pam"))

# PAM Constants
PAM_SUCCESS = 0
PAM_PROMPT_ECHO_OFF = 1
PAM_PROMPT_ECHO_ON = 2
PAM_ERROR_MSG = 3
PAM_TEXT_INFO = 4

# PAM Structs
class pam_message(ctypes.Structure):
    _fields_ = [("msg_style", ctypes.c_int), ("msg", ctypes.c_char_p)]

class pam_response(ctypes.Structure):
    _fields_ = [("resp", ctypes.c_char_p), ("resp_retcode", ctypes.c_int)]

class pam_conv(ctypes.Structure):
    _fields_ = [("conv", ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.POINTER(pam_message)), ctypes.POINTER(ctypes.POINTER(pam_response)), ctypes.c_void_p)), ("appdata_ptr", ctypes.c_void_p)]

class BeetaAuthenticator:
    def __init__(self):
        self.username = pwd.getpwuid(os.getuid()).pw_name
        self.password = ""
        self.pam_handle = ctypes.c_void_p(0)
        self.message_callback = None
        
        # We define the callback here to keep it in scope
        @ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.POINTER(pam_message)), ctypes.POINTER(ctypes.POINTER(pam_response)), ctypes.c_void_p)
        def conv_func(num_msg, msg, resp, appdata_ptr):
            if num_msg <= 0:
                return PAM_SUCCESS

            # Allocate response array
            resp_array = (pam_response * num_msg)()
            for i in range(num_msg):
                m = msg.contents[i].contents
                style = m.msg_style
                
                # If there is a callback registered, we can inform the UI
                # (e.g., "Swipe finger on reader")
                if self.message_callback and m.msg:
                    try:
                        decoded_msg = m.msg.decode('utf-8')
                        self.message_callback(style, decoded_msg)
                    except:
                        pass
                
                if style == PAM_PROMPT_ECHO_OFF:
                    # Password prompt
                    pwd_bytes = self.password.encode('utf-8')
                    resp_array[i].resp = ctypes.cast(ctypes.create_string_buffer(pwd_bytes), ctypes.c_char_p)
                    resp_array[i].resp_retcode = 0
                elif style == PAM_PROMPT_ECHO_ON:
                    # Usually username prompt, but we shouldn't get this
                    resp_array[i].resp = ctypes.cast(ctypes.create_string_buffer(b""), ctypes.c_char_p)
                    resp_array[i].resp_retcode = 0
                elif style == PAM_ERROR_MSG or style == PAM_TEXT_INFO:
                    resp_array[i].resp = None
                    resp_array[i].resp_retcode = 0
                else:
                    return 19 # PAM_CONV_ERR

            # The response pointer must point to the allocated array
            # libpam will free this memory
            # Note: We must allocate memory using libc malloc so PAM can free it.
            libc = ctypes.CDLL(ctypes.util.find_library("c"))
            resp.contents = ctypes.cast(libc.malloc(ctypes.sizeof(pam_response) * num_msg), ctypes.POINTER(pam_response))
            for i in range(num_msg):
                resp.contents[i].resp_retcode = resp_array[i].resp_retcode
                if resp_array[i].resp:
                    libc_str = libc.strdup(resp_array[i].resp)
                    resp.contents[i].resp = ctypes.cast(libc_str, ctypes.c_char_p)
                else:
                    resp.contents[i].resp = None

            return PAM_SUCCESS

        self._conv_func = conv_func
        self.conv = pam_conv(self._conv_func, None)

    def set_message_callback(self, callback):
        """Register a callback for PAM messages (like fprintd instructions)"""
        self.message_callback = callback

    def authenticate(self, password: str) -> bool:
        """Authenticate using PAM."""
        self.password = password
        
        # Start PAM transaction
        # Service name 'login' or 'system-auth'
        ret = libpam.pam_start(b"login", self.username.encode('utf-8'), ctypes.byref(self.conv), ctypes.byref(self.pam_handle))
        if ret != PAM_SUCCESS:
            return False

        try:
            # Perform authentication
            # This is a blocking call. For fprintd, it might block until timeout or swipe.
            ret = libpam.pam_authenticate(self.pam_handle, 0)
            
            if ret == PAM_SUCCESS:
                # Check account validity (expired, etc)
                ret = libpam.pam_acct_mgmt(self.pam_handle, 0)
                
            return ret == PAM_SUCCESS
            
        finally:
            # Always end PAM transaction
            libpam.pam_end(self.pam_handle, ret)
            self.pam_handle = ctypes.c_void_p(0)
            self.password = "" # Clear password from memory
