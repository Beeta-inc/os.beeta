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

    def __init__(self, app: Gtk.Application, config: BeetaConfig, state_manager: StateManager) -> None:
        super().__init__(application=app)
        self._app = app
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
        
        # Main layout container
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        
        # Top bar area
        top_bar = Gtk.CenterBox()
        top_bar.set_margin_top(16)
        top_bar.set_margin_start(24)
        top_bar.set_margin_end(24)
        
        logo = Gtk.Label(label='Beeta OS')
        logo.add_css_class('topbar-logo')
        top_bar.set_start_widget(logo)
        
        live_pill = Gtk.Label(label='Live Center · Music playing')
        live_pill.add_css_class('glass-panel-rounded')
        live_pill.set_margin_start(16)
        live_pill.set_margin_end(16)
        top_bar.set_center_widget(live_pill)
        
        status_lbl = Gtk.Label(label='🔋 92%   📶 Wi-Fi')
        status_lbl.add_css_class('topbar-label-sub')
        top_bar.set_end_widget(status_lbl)
        
        main_box.append(top_bar)
        
        # 3-Column Content area
        content_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=48)
        content_box.set_halign(Gtk.Align.CENTER)
        content_box.set_valign(Gtk.Align.CENTER)
        content_box.set_hexpand(True)
        content_box.set_vexpand(True)
        
        # -- Left Column --
        left_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        left_col.set_size_request(300, -1)
        
        weather_card = self._create_card('Good Morning', '28°C · Sunny', 'weather-clear-symbolic')
        news_card = self._create_card('News of the Day', 'Tech stocks rally as AI...', 'applications-internet-symbolic')
        cal_card = self._create_card('Upcoming', '10:00 AM - Standup', 'x-office-calendar-symbolic')
        
        left_col.append(weather_card)
        left_col.append(news_card)
        left_col.append(cal_card)
        content_box.append(left_col)
        
        # -- Center Column --
        center_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=32)
        center_col.set_halign(Gtk.Align.CENTER)
        
        self._clock_time = Gtk.Label()
        self._clock_time.add_css_class('lock-clock-time')
        self._clock_date = Gtk.Label()
        self._clock_date.add_css_class('lock-clock-date')
        
        clock_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        clock_box.append(self._clock_time)
        clock_box.append(self._clock_date)
        clock_box.set_margin_bottom(32)
        center_col.append(clock_box)
        
        # Login Card
        login_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        login_card.add_css_class('glass-panel-rounded')
        login_card.add_css_class('login-card')
        
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
        
        pwd_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        pwd_box.add_css_class('login-entry-box')
        self._pwd_entry = Gtk.PasswordEntry()
        self._pwd_entry.set_show_peek_icon(True)
        self._pwd_entry.set_placeholder_text('Enter password')
        self._pwd_entry.connect('activate', self._on_login_submit)
        pwd_box.append(self._pwd_entry)
        login_card.append(pwd_box)
        
        pin_link = Gtk.Label(label='Use PIN instead')
        pin_link.add_css_class('login-sub')
        login_card.append(pin_link)
        
        center_col.append(login_card)
        content_box.append(center_col)
        
        # -- Right Column --
        right_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        right_col.set_size_request(300, -1)
        
        bg_apps = self._create_card('Background Apps', '3 apps running', 'applications-system-symbolic')
        sys_status = self._create_card('System Status', 'CPU: 22% | RAM: 46%', 'system-run-symbolic')
        note_card = self._create_card('Quick Note', 'Don\'t forget to...', 'accessories-text-editor-symbolic')
        
        right_col.append(bg_apps)
        right_col.append(sys_status)
        right_col.append(note_card)
        content_box.append(right_col)
        
        main_box.append(content_box)
        
        # Bottom text & controls
        bottom_bar = Gtk.CenterBox()
        bottom_bar.set_margin_bottom(24)
        bottom_bar.set_margin_start(48)
        bottom_bar.set_margin_end(48)
        
        btn_power = Gtk.Button(label='Shut down')
        btn_power.add_css_class('glass-panel-rounded')
        bottom_bar.set_start_widget(btn_power)
        
        unlock_label = Gtk.Label(label='Beeta Adaptive Welcome\nSwipe up or press any key to unlock')
        unlock_label.set_justify(Gtk.Justification.CENTER)
        unlock_label.add_css_class('login-sub')
        bottom_bar.set_center_widget(unlock_label)
        
        btn_camera = Gtk.Button(label='Camera')
        btn_camera.add_css_class('glass-panel-rounded')
        bottom_bar.set_end_widget(btn_camera)
        
        main_box.append(bottom_bar)
        
        main_overlay.add_overlay(main_box)
        self.set_child(main_overlay)
        self._update_clock()

    def _create_card(self, title: str, subtitle: str, icon_name: str) -> Gtk.Box:
        card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        card.add_css_class('glass-panel-rounded')
        card.set_margin_bottom(8)
        
        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_pixel_size(32)
        card.append(icon)
        
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        t_lbl = Gtk.Label(label=title)
        t_lbl.set_halign(Gtk.Align.START)
        t_lbl.add_css_class('launcher-cat-title')
        s_lbl = Gtk.Label(label=subtitle)
        s_lbl.set_halign(Gtk.Align.START)
        s_lbl.add_css_class('launcher-cat-sub')
        
        vbox.append(t_lbl)
        vbox.append(s_lbl)
        card.append(vbox)
        return card

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
