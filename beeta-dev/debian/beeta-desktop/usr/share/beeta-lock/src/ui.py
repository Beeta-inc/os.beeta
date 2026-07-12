# -*- coding: utf-8 -*-
# Beeta Desktop Environment
# Copyright (C) 2023-2026 Beeta Technologies Inc.
# Licensed under GNU General Public License v3.0

"""UI Layout for Beeta Lock Screen."""

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib, Pango
import datetime
import pwd
import os

from auth import BeetaAuthenticator
from theme import LockTheme

class BeetaLockUI(Gtk.Box):
    def __init__(self, unlock_callback):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.set_name("overlay")
        self.unlock_callback = unlock_callback
        
        self.auth = BeetaAuthenticator()
        self.theme = LockTheme()
        
        # We also want to provide PAM feedback to the UI (e.g., "Swipe your finger")
        self.auth.set_message_callback(self.on_pam_message)
        
        # Main Layout: Top area (Time/Welcome) and Center (User Card)
        self.set_valign(Gtk.Align.FILL)
        self.set_halign(Gtk.Align.FILL)
        
        self.build_top_area()
        self.build_center_area()
        
        # Start clock timer
        GLib.timeout_add_seconds(1, self.update_clock)
        self.update_clock()

    def build_top_area(self):
        top_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        top_box.set_margin_top(80)
        top_box.set_margin_start(100)
        top_box.set_halign(Gtk.Align.START)
        
        # Clock
        self.clock_label = Gtk.Label()
        self.clock_label.set_name("clock-label")
        self.clock_label.set_halign(Gtk.Align.START)
        top_box.append(self.clock_label)
        
        # Date & City
        self.date_label = Gtk.Label()
        self.date_label.set_name("date-label")
        self.date_label.set_halign(Gtk.Align.START)
        top_box.append(self.date_label)
        
        # Adaptive Welcome
        username = pwd.getpwuid(os.getuid()).pw_gecos.split(',')[0] or self.auth.username
        welcome_str = self.theme.get_welcome_message(username)
        
        self.welcome_label = Gtk.Label(label=welcome_str)
        self.welcome_label.set_name("welcome-text")
        self.welcome_label.set_halign(Gtk.Align.START)
        self.welcome_label.set_margin_top(16)
        # Allows multiline
        self.welcome_label.set_wrap(True)
        self.welcome_label.set_justify(Gtk.Justification.LEFT)
        top_box.append(self.welcome_label)
        
        self.append(top_box)

    def build_center_area(self):
        center_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        center_box.set_valign(Gtk.Align.CENTER)
        center_box.set_halign(Gtk.Align.CENTER)
        center_box.set_vexpand(True)
        
        # The floating User Card
        self.card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        self.card.set_name("user-card")
        self.card.set_halign(Gtk.Align.CENTER)
        
        # Avatar placeholder (icon)
        avatar = Gtk.Image.new_from_icon_name("avatar-default-symbolic")
        avatar.set_pixel_size(80)
        avatar.set_margin_bottom(-8)
        self.card.append(avatar)
        
        # Username
        username = pwd.getpwuid(os.getuid()).pw_gecos.split(',')[0] or self.auth.username
        name_label = Gtk.Label(label=username)
        name_label.set_css_classes(["title"])
        self.card.append(name_label)
        
        # Password Entry
        self.entry = Gtk.PasswordEntry()
        self.entry.set_name("password-entry")
        self.entry.set_placeholder_text("Password")
        self.entry.set_show_peek_icon(True)
        self.entry.connect("activate", self.on_unlock_clicked)
        self.card.append(self.entry)
        
        # PAM Message Label (for fingerprint/howdy instructions)
        self.pam_label = Gtk.Label()
        self.pam_label.set_css_classes(["dim-label"])
        self.pam_label.set_visible(False)
        self.card.append(self.pam_label)
        
        # Unlock Button
        btn = Gtk.Button(label="Unlock")
        btn.set_name("unlock-button")
        btn.connect("clicked", self.on_unlock_clicked)
        self.card.append(btn)
        
        center_box.append(self.card)
        self.append(center_box)

    def update_clock(self):
        now = datetime.datetime.now()
        self.clock_label.set_text(now.strftime("%H:%M"))
        self.date_label.set_text(now.strftime("%A, %B %d"))
        return True

    def on_pam_message(self, style, msg):
        """Called by auth.py when PAM wants to talk to the user."""
        GLib.idle_add(self._update_pam_label, msg)

    def _update_pam_label(self, msg):
        self.pam_label.set_text(msg)
        self.pam_label.set_visible(True)

    def on_unlock_clicked(self, widget):
        password = self.entry.get_text()
        self.entry.set_text("")
        self.entry.set_sensitive(False)
        
        # Authenticate (this blocks, so ideally it should be in a thread, 
        # but for simplicity and speed of typical local auth, we block)
        success = self.auth.authenticate(password)
        
        self.entry.set_sensitive(True)
        if success:
            self.pam_label.set_visible(False)
            self.unlock_callback()
        else:
            self.pam_label.set_text("Incorrect password")
            self.pam_label.set_visible(True)
            self.entry.grab_focus()
            
            # Request shake animation from parent
            win = self.get_root()
            if hasattr(win, 'animations'):
                win.animations.play_shake_animation(self.card)
