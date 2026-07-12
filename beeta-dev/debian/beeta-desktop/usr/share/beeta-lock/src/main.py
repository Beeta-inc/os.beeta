# -*- coding: utf-8 -*-
# Beeta Desktop Environment
# Copyright (C) 2023-2026 Beeta Technologies Inc.
# Licensed under GNU General Public License v3.0

"""Beeta Lock Screen (Adaptive Welcome™)."""

import sys
import os
import signal
from pathlib import Path
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Gtk4LayerShell', '1.0')
from gi.repository import Gtk, Gdk, GLib, Gtk4LayerShell

from ui import BeetaLockUI
from animations import LockAnimations

class BeetaLock(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='com.beeta.lock',
                         flags=gi.repository.Gio.ApplicationFlags.FLAGS_NONE)
        self.window = None

    def do_activate(self):
        if self.window:
            self.window.present()
            return

        self.window = Gtk.ApplicationWindow(application=self)
        self.window.set_title("Beeta Lock")
        
        # Layer Shell Setup
        Gtk4LayerShell.init_for_window(self.window)
        # OVERLAY layer guarantees we are above EVERYTHING, even panels
        Gtk4LayerShell.set_layer(self.window, Gtk4LayerShell.Layer.OVERLAY)
        # Fill the entire screen
        Gtk4LayerShell.set_anchor(self.window, Gtk4LayerShell.Edge.TOP, True)
        Gtk4LayerShell.set_anchor(self.window, Gtk4LayerShell.Edge.BOTTOM, True)
        Gtk4LayerShell.set_anchor(self.window, Gtk4LayerShell.Edge.LEFT, True)
        Gtk4LayerShell.set_anchor(self.window, Gtk4LayerShell.Edge.RIGHT, True)
        
        # EXCLUSIVE mode grabs all keyboard input globally. This is how we lock.
        Gtk4LayerShell.set_keyboard_mode(self.window, Gtk4LayerShell.KeyboardMode.EXCLUSIVE)
        
        # Build UI
        self.ui = BeetaLockUI(unlock_callback=self.unlock)
        self.window.set_child(self.ui)
        
        # Animations
        self.window.animations = LockAnimations(self.ui, self.ui.card)
        
        # Load CSS
        self.load_css()
        
        self.window.present()
        
        # Start Wake Animation shortly after presenting
        GLib.timeout_add(50, self.window.animations.play_wake_animation)

    def load_css(self):
        provider = Gtk.CssProvider()
        
        # 1. Load static CSS (animations)
        static_css_path = Path(__file__).parent.parent / 'data' / 'style.css'
        if not static_css_path.exists():
            static_css_path = Path('/usr/share/beeta-lock/style.css')
        
        css_str = ""
        if static_css_path.exists():
            css_str += static_css_path.read_text()
            
        # 2. Load dynamic Adaptive Nature CSS
        css_str += self.ui.theme.get_lock_css()
        
        provider.load_from_string(css_str)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def unlock(self):
        """Triggered when auth is successful."""
        self.window.animations.play_unlock_animation(self.quit)

def signal_handler(sig, frame):
    # Lock screens should not be killable via signals normally,
    # but for development we allow SIGTERM.
    sys.exit(0)

def main():
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    app = BeetaLock()
    sys.exit(app.run(sys.argv))

if __name__ == '__main__':
    main()
