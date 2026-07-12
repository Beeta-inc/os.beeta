# -*- coding: utf-8 -*-
# Beeta Desktop Environment
# Copyright (C) 2023-2026 Beeta Technologies Inc.
# Licensed under GNU General Public License v3.0

"""Animation Orchestrator for Beeta Lock."""

import json
import socket
import os
from gi.repository import GLib

class WayfireIPC:
    def __init__(self):
        wayland_display = os.environ.get("WAYLAND_DISPLAY", "wayland-0")
        xdg_runtime = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
        self.sock_path = f"{xdg_runtime}/wayfire-{wayland_display}.socket"

    def send_cmd(self, method: str, data: dict = None):
        if not os.path.exists(self.sock_path):
            return
        
        msg = {"method": method, "data": data or {}}
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.connect(self.sock_path)
                s.sendall(json.dumps(msg).encode('utf-8'))
        except Exception:
            pass

class LockAnimations:
    def __init__(self, overlay_widget, card_widget):
        self.ipc = WayfireIPC()
        self.overlay = overlay_widget
        self.card = card_widget
        
    def play_wake_animation(self):
        """600ms Wake Animation: 
        1. Screen fades in (overlay opacity 0 -> 1)
        2. Wallpaper sharpens (Wayfire blur radius adjusted)
        3. Card floats upward
        """
        # Ensure blur is active on wayfire
        # We set blur offset high to obscure the desktop
        self.ipc.send_cmd("core/set_config_option", {"option": "blur/kawase_offset", "value": "15"})
        
        # UI starts hidden/shifted, then we apply the active classes
        self.overlay.add_css_class("wake-active")
        self.card.add_css_class("wake-active")

    def play_unlock_animation(self, on_complete):
        """400ms Unlock Animation:
        1. Card shrinks and fades
        2. Overlay fades out
        3. Desktop comes into focus
        """
        self.card.remove_css_class("wake-active")
        self.card.add_css_class("unlock-active")
        self.overlay.add_css_class("unlock-active")
        
        # Animate blur away
        self.ipc.send_cmd("core/set_config_option", {"option": "blur/kawase_offset", "value": "5"})
        
        # Wait 400ms then call on_complete
        GLib.timeout_add(400, on_complete)
        
    def play_shake_animation(self, widget):
        """Shake animation for wrong password."""
        widget.add_css_class("shake")
        GLib.timeout_add(400, lambda: widget.remove_css_class("shake"))
