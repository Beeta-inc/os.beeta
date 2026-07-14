# -*- coding: utf-8 -*-
# Beeta Desktop Environment
# Copyright (C) 2023-2026 Beeta Technologies Inc.
# Licensed under GNU General Public License v3.0

"""Lock Screen overlay matching the Beeta OS design mockup.

Layout:
    Top bar:   'Beeta OS' left | 'Live Center' pill center | battery/wifi/time right
    Left col:  Weather card (with hourly forecast), News card, Calendar card
    Center:    Large clock, date, location, profile pic, password entry
    Right col: Background Apps, System Status, Quick Note
    Bottom:    'Shut down' left | 'Beeta Adaptive Welcome' center | 'Camera' right
"""

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

        for edge in (
            Gtk4LayerShell.Edge.TOP,
            Gtk4LayerShell.Edge.BOTTOM,
            Gtk4LayerShell.Edge.LEFT,
            Gtk4LayerShell.Edge.RIGHT,
        ):
            Gtk4LayerShell.set_anchor(self, edge, True)

        Gtk4LayerShell.set_keyboard_mode(self, Gtk4LayerShell.KeyboardMode.EXCLUSIVE)
        self.add_css_class('lock-screen')

        self._build_ui()
        GLib.timeout_add_seconds(1, self._update_clock)
        self.set_visible(False)
        self._state_manager.connect('state-changed', self._on_state_changed)

    # ── UI Builder ───────────────────────────────────────────────

    def _build_ui(self) -> None:
        main_overlay = Gtk.Overlay()

        bg_dimmer = Gtk.Box()
        bg_dimmer.add_css_class('lock-screen-dimmer')
        main_overlay.set_child(bg_dimmer)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # ─── Top Bar ─────────────────────────────────────────────
        top_bar = Gtk.CenterBox()
        top_bar.set_margin_top(16)
        top_bar.set_margin_start(24)
        top_bar.set_margin_end(24)

        # Left: Beeta OS logo
        logo_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        logo_icon = Gtk.Label(label='🟣')
        logo_text = Gtk.Label(label='Beeta OS')
        logo_text.add_css_class('lock-logo')
        logo_box.append(logo_icon)
        logo_box.append(logo_text)
        top_bar.set_start_widget(logo_box)

        # Center: Live Center pill
        live_pill = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        live_pill.add_css_class('lock-live-pill')
        live_dot = Gtk.Label(label='🟡')
        live_text = Gtk.Label(label='Live Center')
        live_text.add_css_class('lock-live-text')
        live_sub = Gtk.Label(label='Nothing playing')
        live_sub.add_css_class('lock-live-sub')
        live_pill.append(live_dot)
        live_pill.append(live_text)
        live_pill.append(live_sub)
        top_bar.set_center_widget(live_pill)

        # Right: battery/wifi/time
        right_status = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        bat_lbl = Gtk.Label(label='🔋 86%')
        bat_lbl.add_css_class('lock-status-text')
        wifi_lbl = Gtk.Label(label='📶')
        wifi_lbl.add_css_class('lock-status-text')
        self._topbar_time = Gtk.Label()
        self._topbar_time.add_css_class('lock-status-text')
        right_status.append(bat_lbl)
        right_status.append(wifi_lbl)
        right_status.append(self._topbar_time)
        top_bar.set_end_widget(right_status)

        main_box.append(top_bar)

        # ─── 3-Column Content ────────────────────────────────────
        content_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=32)
        content_box.set_halign(Gtk.Align.CENTER)
        content_box.set_valign(Gtk.Align.CENTER)
        content_box.set_hexpand(True)
        content_box.set_vexpand(True)
        content_box.set_margin_start(48)
        content_box.set_margin_end(48)

        # ── LEFT COLUMN ──────────────────────────────────────────
        left_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        left_col.set_size_request(280, -1)

        # 1. Weather Card
        weather_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        weather_card.add_css_class('lock-card')

        weather_header = Gtk.Label(label='Weather')
        weather_header.set_halign(Gtk.Align.START)
        weather_header.add_css_class('lock-card-title')
        weather_card.append(weather_header)

        # Temp row
        temp_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        sun_icon = Gtk.Label(label='☀️')
        sun_icon.add_css_class('lock-weather-icon')
        temp_lbl = Gtk.Label(label='31°C')
        temp_lbl.add_css_class('lock-weather-temp')
        desc_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        desc_main = Gtk.Label(label='Sunny')
        desc_main.add_css_class('lock-weather-desc')
        desc_main.set_halign(Gtk.Align.START)
        desc_box.append(desc_main)
        temp_row.append(sun_icon)
        temp_row.append(temp_lbl)
        temp_row.append(desc_box)
        weather_card.append(temp_row)

        feels = Gtk.Label(label='Feels like 34°C\nHumidity 68%')
        feels.set_halign(Gtk.Align.START)
        feels.add_css_class('lock-card-sub')
        weather_card.append(feels)

        # Hourly forecast row
        forecast = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        forecast.set_halign(Gtk.Align.FILL)
        forecast.set_homogeneous(True)
        for hr, ico, tmp in [('12 PM', '☀️', '33°'), ('03 PM', '⛅', '34°'), ('06 PM', '🌧️', '32°'), ('09 PM', '☁️', '29°')]:
            col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            col.set_halign(Gtk.Align.CENTER)
            h = Gtk.Label(label=hr)
            h.add_css_class('lock-forecast-time')
            i = Gtk.Label(label=ico)
            i.add_css_class('lock-forecast-icon')
            t = Gtk.Label(label=tmp)
            t.add_css_class('lock-forecast-temp')
            col.append(h)
            col.append(i)
            col.append(t)
            forecast.append(col)
        weather_card.append(forecast)
        left_col.append(weather_card)

        # 2. News Card
        news_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        news_card.add_css_class('lock-card')

        news_header_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        news_badge = Gtk.Label(label='Ⓜ')
        news_badge.add_css_class('lock-news-badge')
        news_title = Gtk.Label(label='News of the Day')
        news_title.add_css_class('lock-card-title')
        news_header_row.append(news_badge)
        news_header_row.append(news_title)
        news_card.append(news_header_row)

        news_content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        news_text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        news_text_box.set_hexpand(True)
        news_body = Gtk.Label(label='ISRO successfully tests\nNext-Gen Rocket Engine\nin new milestone.')
        news_body.set_halign(Gtk.Align.START)
        news_body.add_css_class('lock-card-body')
        news_meta = Gtk.Label(label='India Today · 1h ago')
        news_meta.set_halign(Gtk.Align.START)
        news_meta.add_css_class('lock-card-meta')
        news_text_box.append(news_body)
        news_text_box.append(news_meta)

        news_thumb = Gtk.Image.new_from_icon_name('media-record-symbolic')
        news_thumb.set_pixel_size(48)
        news_thumb.add_css_class('lock-news-thumb')

        news_content.append(news_text_box)
        news_content.append(news_thumb)
        news_card.append(news_content)
        left_col.append(news_card)

        # 3. Calendar/Upcoming Card
        cal_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        cal_card.add_css_class('lock-card')

        cal_header = Gtk.Label(label='Upcoming in few hours')
        cal_header.set_halign(Gtk.Align.START)
        cal_header.add_css_class('lock-card-title')
        cal_card.append(cal_header)

        events = [
            ('12:00 PM', 'Team Meeting', 'Online'),
            ('03:30 PM', 'Project Discussion', 'Work'),
            ('05:00 PM', 'Gym', 'Personal'),
        ]
        for time_str, title, loc in events:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
            time_lbl = Gtk.Label(label=time_str)
            time_lbl.add_css_class('lock-cal-time')
            time_lbl.set_size_request(80, -1)
            text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            t_lbl = Gtk.Label(label=title)
            t_lbl.set_halign(Gtk.Align.START)
            t_lbl.add_css_class('lock-cal-title')
            l_lbl = Gtk.Label(label=loc)
            l_lbl.set_halign(Gtk.Align.START)
            l_lbl.add_css_class('lock-cal-loc')
            text_box.append(t_lbl)
            text_box.append(l_lbl)
            row.append(time_lbl)
            row.append(text_box)
            cal_card.append(row)

        cal_footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        cal_footer.set_hexpand(True)
        cal_link = Gtk.Label(label='View full calendar')
        cal_link.add_css_class('lock-card-link')
        cal_link.set_hexpand(True)
        cal_link.set_halign(Gtk.Align.START)
        cal_arrow = Gtk.Label(label='→')
        cal_arrow.add_css_class('lock-card-link')
        cal_footer.append(cal_link)
        cal_footer.append(cal_arrow)
        cal_card.append(cal_footer)
        left_col.append(cal_card)

        content_box.append(left_col)

        # ── CENTER COLUMN ────────────────────────────────────────
        center_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        center_col.set_halign(Gtk.Align.CENTER)
        center_col.set_valign(Gtk.Align.CENTER)
        center_col.set_size_request(360, -1)

        # Clock
        self._clock_time = Gtk.Label()
        self._clock_time.add_css_class('lock-clock-time')
        self._clock_date = Gtk.Label()
        self._clock_date.add_css_class('lock-clock-date')
        self._clock_location = Gtk.Label(label='📍 Kolkata, India')
        self._clock_location.add_css_class('lock-clock-location')

        clock_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        clock_box.set_halign(Gtk.Align.CENTER)
        clock_box.append(self._clock_time)
        clock_box.append(self._clock_date)
        clock_box.append(self._clock_location)
        center_col.append(clock_box)

        # Profile pic
        profile_pic = Gtk.Image.new_from_icon_name('avatar-default-symbolic')
        profile_pic.set_pixel_size(96)
        profile_pic.add_css_class('lock-avatar')
        profile_pic.set_halign(Gtk.Align.CENTER)
        center_col.append(profile_pic)

        # Name
        name_lbl = Gtk.Label(label='Noywrit')
        name_lbl.add_css_class('lock-username')
        center_col.append(name_lbl)
        welcome_lbl = Gtk.Label(label='Welcome back')
        welcome_lbl.add_css_class('lock-welcome')
        center_col.append(welcome_lbl)

        # Fingerprint icon
        fp_icon = Gtk.Image.new_from_icon_name('fingerprint-symbolic')
        fp_icon.set_pixel_size(40)
        fp_icon.add_css_class('lock-fingerprint')
        fp_icon.set_halign(Gtk.Align.CENTER)
        center_col.append(fp_icon)

        # Password entry
        pwd_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        pwd_row.set_halign(Gtk.Align.CENTER)
        pwd_row.add_css_class('lock-pwd-row')
        self._pwd_entry = Gtk.PasswordEntry()
        self._pwd_entry.set_show_peek_icon(True)
        self._pwd_entry.set_placeholder_text('Enter password')
        self._pwd_entry.set_size_request(260, -1)
        self._pwd_entry.connect('activate', self._on_login_submit)
        pwd_row.append(self._pwd_entry)
        submit_btn = Gtk.Button()
        submit_btn.add_css_class('lock-submit-btn')
        submit_icon = Gtk.Image.new_from_icon_name('go-next-symbolic')
        submit_icon.set_pixel_size(20)
        submit_btn.set_child(submit_icon)
        submit_btn.connect('clicked', lambda b: self._on_login_submit(self._pwd_entry))
        pwd_row.append(submit_btn)
        center_col.append(pwd_row)

        pin_link = Gtk.Label(label='Use PIN instead')
        pin_link.add_css_class('lock-pin-link')
        center_col.append(pin_link)

        content_box.append(center_col)

        # ── RIGHT COLUMN ─────────────────────────────────────────
        right_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        right_col.set_size_request(280, -1)

        # 1. Background Apps
        bg_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        bg_card.add_css_class('lock-card')

        bg_title = Gtk.Label(label='Background Apps')
        bg_title.set_halign(Gtk.Align.START)
        bg_title.add_css_class('lock-card-title')
        bg_card.append(bg_title)

        apps = [
            ('🎵', 'Spotify', 'Playing'),
            ('🎮', 'Steam', 'Downloading · 73%'),
            ('📝', 'VS Code', 'Running'),
            ('💾', 'File Backup', 'Backing up...'),
        ]
        for ico, name, status in apps:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            icon_lbl = Gtk.Label(label=ico)
            icon_lbl.add_css_class('lock-app-icon')
            text_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            text_col.set_hexpand(True)
            n_lbl = Gtk.Label(label=name)
            n_lbl.set_halign(Gtk.Align.START)
            n_lbl.add_css_class('lock-app-name')
            s_lbl = Gtk.Label(label=status)
            s_lbl.set_halign(Gtk.Align.START)
            s_lbl.add_css_class('lock-app-status')
            text_col.append(n_lbl)
            text_col.append(s_lbl)
            row.append(icon_lbl)
            row.append(text_col)
            bg_card.append(row)

        view_all = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        va_lbl = Gtk.Label(label='View all (6)')
        va_lbl.add_css_class('lock-card-link')
        va_lbl.set_hexpand(True)
        va_lbl.set_halign(Gtk.Align.START)
        va_arrow = Gtk.Label(label='→')
        va_arrow.add_css_class('lock-card-link')
        view_all.append(va_lbl)
        view_all.append(va_arrow)
        bg_card.append(view_all)
        right_col.append(bg_card)

        # 2. System Status
        sys_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        sys_card.add_css_class('lock-card')

        sys_title = Gtk.Label(label='System Status')
        sys_title.set_halign(Gtk.Align.START)
        sys_title.add_css_class('lock-card-title')
        sys_card.append(sys_title)

        stats = [
            ('🔋', 'Battery', '86% · Charging'),
            ('💽', 'Storage', '256 GB free of 512 GB'),
            ('🧠', 'Memory', '6.2 GB used of 16 GB'),
            ('⚡', 'CPU', '22%'),
        ]
        for ico, name, val in stats:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            icon_lbl = Gtk.Label(label=ico)
            icon_lbl.add_css_class('lock-app-icon')
            text_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            text_col.set_hexpand(True)
            n_lbl = Gtk.Label(label=name)
            n_lbl.set_halign(Gtk.Align.START)
            n_lbl.add_css_class('lock-app-name')
            v_lbl = Gtk.Label(label=val)
            v_lbl.set_halign(Gtk.Align.START)
            v_lbl.add_css_class('lock-app-status')
            text_col.append(n_lbl)
            text_col.append(v_lbl)
            row.append(icon_lbl)
            row.append(text_col)
            sys_card.append(row)
        right_col.append(sys_card)

        # 3. Quick Note
        note_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        note_card.add_css_class('lock-card')

        note_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        note_icon = Gtk.Label(label='✍️')
        note_title = Gtk.Label(label='Quick Note')
        note_title.add_css_class('lock-card-title')
        note_header.append(note_icon)
        note_header.append(note_title)
        note_card.append(note_header)

        note_body = Gtk.Label(
            label='Discipline is choosing between\nwhat you want now and what\nyou want most.\n— Unknown'
        )
        note_body.set_halign(Gtk.Align.START)
        note_body.add_css_class('lock-note-body')
        note_card.append(note_body)
        right_col.append(note_card)

        content_box.append(right_col)
        main_box.append(content_box)

        # ─── Bottom Bar ──────────────────────────────────────────
        # Swipe hint
        swipe_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        swipe_box.set_halign(Gtk.Align.CENTER)
        swipe_chevron = Gtk.Label(label='⌃')
        swipe_chevron.add_css_class('lock-swipe-chevron')
        swipe_text = Gtk.Label(label='Swipe up or press any key to unlock')
        swipe_text.add_css_class('lock-swipe-text')
        swipe_box.append(swipe_chevron)
        swipe_box.append(swipe_text)
        main_box.append(swipe_box)

        bottom_bar = Gtk.CenterBox()
        bottom_bar.set_margin_bottom(24)
        bottom_bar.set_margin_start(48)
        bottom_bar.set_margin_end(48)
        bottom_bar.set_margin_top(12)

        # Left: Shut down
        shutdown_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        sd_icon = Gtk.Label(label='⏻')
        sd_icon.add_css_class('lock-bottom-icon')
        sd_text = Gtk.Label(label='Shut down')
        sd_text.add_css_class('lock-bottom-text')
        shutdown_box.append(sd_icon)
        shutdown_box.append(sd_text)
        bottom_bar.set_start_widget(shutdown_box)

        # Center: Beeta Adaptive Welcome
        welcome_pill = Gtk.Label(label='Beeta Adaptive Welcome™')
        welcome_pill.add_css_class('lock-welcome-pill')
        bottom_bar.set_center_widget(welcome_pill)

        # Right: Camera
        camera_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        cam_icon = Gtk.Label(label='📷')
        cam_icon.add_css_class('lock-bottom-icon')
        cam_text = Gtk.Label(label='Camera')
        cam_text.add_css_class('lock-bottom-text')
        camera_box.append(cam_text)
        camera_box.append(cam_icon)
        bottom_bar.set_end_widget(camera_box)

        main_box.append(bottom_bar)

        main_overlay.add_overlay(main_box)
        self.set_child(main_overlay)
        self._update_clock()

    # ── Helpers ───────────────────────────────────────────────────

    def _update_clock(self) -> bool:
        now = datetime.now()
        # Large clock: "09:42 AM" format
        self._clock_time.set_text(now.strftime('%I:%M') + now.strftime(' %p'))
        self._clock_date.set_text(now.strftime('%A, %d %B %Y'))
        self._topbar_time.set_text(now.strftime('%I:%M %p'))
        return GLib.SOURCE_CONTINUE

    def _on_login_submit(self, entry: Gtk.PasswordEntry) -> None:
        entry.set_text('')
        self._state_manager.set_state('desktop')

    def _on_state_changed(self, mgr: StateManager, state: str) -> None:
        if state == 'locked':
            self.set_visible(True)
            self._pwd_entry.grab_focus()
        else:
            self.set_visible(False)
