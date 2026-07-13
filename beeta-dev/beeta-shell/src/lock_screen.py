# -*- coding: utf-8 -*-
# Beeta Desktop Environment

from __future__ import annotations
from typing import TYPE_CHECKING
from datetime import datetime

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gtk4LayerShell', '1.0')
from gi.repository import Gtk, GLib, Gtk4LayerShell, Gio, GObject

if TYPE_CHECKING:
    from .config import BeetaConfig
    from .states import StateManager

class LockScreen(Gtk.Window):
    """Fullscreen lock screen overlay."""

    def __init__(self, config: BeetaConfig, state_manager: StateManager) -> None:
        super().__init__()
        self._config = config
        self._state_manager = state_manager
        
        # Init layer shell
        Gtk4LayerShell.init_for_window(self)
        Gtk4LayerShell.set_namespace(self, 'lockscreen')
        Gtk4LayerShell.set_layer(self, Gtk4LayerShell.Layer.OVERLAY)
        
        # Anchor to all 4 edges to cover the entire screen
        for edge in (
            Gtk4LayerShell.Edge.TOP,
            Gtk4LayerShell.Edge.BOTTOM,
            Gtk4LayerShell.Edge.LEFT,
            Gtk4LayerShell.Edge.RIGHT
        ):
            Gtk4LayerShell.set_anchor(self, edge, True)
            
        # Optional: Exclusive zone so other things get pushed out of the way,
        # but overlay layer is usually fine.
        Gtk4LayerShell.set_keyboard_mode(self, Gtk4LayerShell.KeyboardMode.EXCLUSIVE)

        self.add_css_class('lock-screen')

        # We will build the UI here
        self._build_ui()
        
        # Start a clock timer
        GLib.timeout_add_seconds(1, self._update_clock)
        
        # Hide by default
        self.set_visible(False)
        
        # Listen to state changes
        self._state_manager.connect('state-changed', self._on_state_changed)

    def _build_ui(self) -> None:
        main_overlay = Gtk.Overlay()
        
        # Darken the background slightly
        bg_dimmer = Gtk.Box()
        bg_dimmer.add_css_class('lock-screen-dimmer')
        main_overlay.set_child(bg_dimmer)
        
        # Center layout
        center_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=32)
        center_box.set_halign(Gtk.Align.CENTER)
        center_box.set_valign(Gtk.Align.CENTER)
        
        # Clock
        self._clock_time = Gtk.Label()
        self._clock_time.add_css_class('lock-clock-time')
        self._clock_date = Gtk.Label()
        self._clock_date.add_css_class('lock-clock-date')
        
        clock_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        clock_box.append(self._clock_time)
        clock_box.append(self._clock_date)
        clock_box.set_margin_bottom(64)
        
        center_box.append(clock_box)
        
        # Login Card
        login_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        login_card.add_css_class('glass-panel-rounded')
        login_card.add_css_class('login-card')
        
        # Profile pic placeholder
        profile_pic = Gtk.Image.new_from_icon_name('avatar-default-symbolic')
        profile_pic.set_pixel_size(80)
        profile_pic.add_css_class('login-avatar')
        login_card.append(profile_pic)
        
        name_label = Gtk.Label(label='Noywrit')
        name_label.add_css_class('login-name')
        login_card.append(name_label)
        
        sub_label = Gtk.Label(label='Welcome back')
        sub_label.add_css_class('login-sub')
        login_card.append(sub_label)
        
        # Password entry
        pwd_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        pwd_box.add_css_class('login-entry-box')
        self._pwd_entry = Gtk.PasswordEntry()
        self._pwd_entry.set_show_peek_icon(True)
        self._pwd_entry.set_placeholder_text('Enter password')
        self._pwd_entry.connect('activate', self._on_login_submit)
        pwd_box.append(self._pwd_entry)
        
        login_card.append(pwd_box)
        
        center_box.append(login_card)
        
        # Bottom text
        unlock_label = Gtk.Label(label='Swipe up or press any key to unlock')
        unlock_label.add_css_class('login-sub')
        center_box.append(unlock_label)
        
        main_overlay.add_overlay(center_box)
        
        # We can add left/right widgets later if needed, for now just the core.
        self.set_child(main_overlay)
        self._update_clock()

    def _update_clock(self) -> bool:
        now = datetime.now()
        self._clock_time.set_text(now.strftime('%I:%M %p'))
        self._clock_date.set_text(now.strftime('%A, %d %B %Y'))
        return GLib.SOURCE_CONTINUE
        
    def _on_login_submit(self, entry: Gtk.PasswordEntry) -> None:
        # In a real OS this would authenticate via PAM
        # For our UI prototype, just unlock instantly.
        entry.set_text('')
        self._state_manager.set_state('desktop')

    def _on_state_changed(self, mgr: StateManager, state: str) -> None:
        if state == 'locked':
            self.set_visible(True)
            self._pwd_entry.grab_focus()
        else:
            self.set_visible(False)
