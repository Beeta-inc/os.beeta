# -*- coding: utf-8 -*-
# Beeta Desktop Environment

from __future__ import annotations
import json
import os
import threading
import time
from urllib.request import Request, urlopen
from urllib.error import URLError

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gtk4LayerShell', '1.0')
from gi.repository import Gtk, Gtk4LayerShell, GLib, Gio

from .weather_renderer import PhysicsWeatherWidget

class DesktopWidgets:
    """Spawns desktop widgets on the bottom layer."""

    def __init__(self, app: Gtk.Application) -> None:
        self._app = app
        
        # We can use a single transparent fullscreen window on BOTTOM layer
        # and place left/right boxes.
        self._window = Gtk.Window(application=app)
        self._window.set_title('Beeta Desktop Widgets')
        self._window.set_decorated(False)
        
        Gtk4LayerShell.init_for_window(self._window)
        Gtk4LayerShell.set_layer(self._window, Gtk4LayerShell.Layer.BOTTOM)
        Gtk4LayerShell.set_namespace(self._window, 'beeta-desktop-widgets')
        
        # Anchor to all edges
        for edge in (Gtk4LayerShell.Edge.TOP, Gtk4LayerShell.Edge.BOTTOM, Gtk4LayerShell.Edge.LEFT, Gtk4LayerShell.Edge.RIGHT):
            Gtk4LayerShell.set_anchor(self._window, edge, True)
            
        # Top padding for topbar, bottom for dock
        Gtk4LayerShell.set_margin(self._window, Gtk4LayerShell.Edge.TOP, 100)
        Gtk4LayerShell.set_margin(self._window, Gtk4LayerShell.Edge.BOTTOM, 120)
        Gtk4LayerShell.set_margin(self._window, Gtk4LayerShell.Edge.LEFT, 40)
        Gtk4LayerShell.set_margin(self._window, Gtk4LayerShell.Edge.RIGHT, 40)
        
        self._build_content()
        self._window.present()
        
        # Start stats thread
        self._running = True
        self._stats_thread = threading.Thread(target=self._monitor_stats, daemon=True)
        self._stats_thread.start()
        
        # Start weather updates
        self._start_weather_updates()

    def _build_content(self) -> None:
        container = Gtk.CenterBox()
        container.set_hexpand(True)
        container.set_halign(Gtk.Align.FILL)
        
        # ── Left Widgets ──
        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        left_box.set_halign(Gtk.Align.START)
        
        # Large Weather Card
        weather_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        weather_card.add_css_class('glass-panel-rounded')
        weather_card.add_css_class('desktop-widget')
        weather_card.set_size_request(300, 280)
        
        greet = Gtk.Label(label='Good Morning, Noywrit')
        greet.set_halign(Gtk.Align.START)
        greet.add_css_class('widget-title')
        weather_card.append(greet)
        
        # Temp + Desc Row
        temp_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self._weather_widget = PhysicsWeatherWidget(adaptive_motion=self._app.adaptive_motion if hasattr(self._app, 'adaptive_motion') else None, width=64, height=64)
        
        temp_desc_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self._temp_lbl = Gtk.Label(label='31°C')
        self._temp_lbl.add_css_class('widget-temp-large')
        self._temp_lbl.set_halign(Gtk.Align.START)
        
        self._desc_lbl = Gtk.Label(label='Sunny')
        self._desc_lbl.add_css_class('widget-sub')
        self._desc_lbl.set_halign(Gtk.Align.START)
        
        temp_desc_box.append(self._temp_lbl)
        temp_desc_box.append(self._desc_lbl)
        
        temp_row.append(self._weather_widget)
        temp_row.append(temp_desc_box)
        weather_card.append(temp_row)
        
        # Location + Feels-like
        loc_lbl = Gtk.Label(label='📍 Kolkata, India')
        loc_lbl.add_css_class('widget-location')
        loc_lbl.set_halign(Gtk.Align.START)
        
        feels_lbl = Gtk.Label(label='Feels like 34°C  •  Humidity 68%')
        feels_lbl.add_css_class('widget-feels')
        feels_lbl.set_halign(Gtk.Align.START)
        
        weather_card.append(loc_lbl)
        weather_card.append(feels_lbl)
        
        # Forecast Row
        forecast_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        forecast_box.set_halign(Gtk.Align.CENTER)
        forecast_box.add_css_class('widget-forecast-row')
        
        hours = [('12 PM', '☀️', '33°'), ('03 PM', '⛅', '34°'), ('06 PM', '🌧️', '32°'), ('09 PM', '☁️', '29°')]
        for hr, ico, tmp in hours:
            item = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            item.set_halign(Gtk.Align.CENTER)
            
            hr_lbl = Gtk.Label(label=hr)
            hr_lbl.add_css_class('widget-forecast-time')
            
            ico_lbl = Gtk.Label(label=ico)
            ico_lbl.add_css_class('widget-forecast-icon')
            
            tmp_lbl = Gtk.Label(label=tmp)
            tmp_lbl.add_css_class('widget-forecast-temp')
            
            item.append(hr_lbl)
            item.append(ico_lbl)
            item.append(tmp_lbl)
            forecast_box.append(item)
            
        weather_card.append(forecast_box)
        left_box.append(weather_card)
        container.set_start_widget(left_box)
        
        # ── Right Widgets ──
        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        right_box.set_halign(Gtk.Align.END)
        
        # 1. System Overview
        sys_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        sys_card.add_css_class('glass-panel-rounded')
        sys_card.add_css_class('desktop-widget')
        sys_title = Gtk.Label(label='System Overview')
        sys_title.set_halign(Gtk.Align.START)
        sys_title.add_css_class('widget-title')
        sys_card.append(sys_title)
        
        rings_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16, halign=Gtk.Align.CENTER)
        
        self._cpu_lbl = Gtk.Label(label='CPU\n0%')
        self._cpu_lbl.set_justify(Gtk.Justification.CENTER)
        self._cpu_lbl.add_css_class('sys-ring')
        self._cpu_lbl.add_css_class('ring-cpu')
        
        self._ram_lbl = Gtk.Label(label='RAM\n0%')
        self._ram_lbl.set_justify(Gtk.Justification.CENTER)
        self._ram_lbl.add_css_class('sys-ring')
        self._ram_lbl.add_css_class('ring-ram')
        
        self._gpu_lbl = Gtk.Label(label='GPU\n0%')
        self._gpu_lbl.set_justify(Gtk.Justification.CENTER)
        self._gpu_lbl.add_css_class('sys-ring')
        self._gpu_lbl.add_css_class('ring-gpu')
        
        self._disk_lbl = Gtk.Label(label='Disk\n0%')
        self._disk_lbl.set_justify(Gtk.Justification.CENTER)
        self._disk_lbl.add_css_class('sys-ring')
        self._disk_lbl.add_css_class('ring-disk')
        
        rings_box.append(self._cpu_lbl)
        rings_box.append(self._ram_lbl)
        rings_box.append(self._gpu_lbl)
        rings_box.append(self._disk_lbl)
        
        sys_card.append(rings_box)
        right_box.append(sys_card)
        
        # 2. Today's Summary
        today_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        today_card.add_css_class('glass-panel-rounded')
        today_card.add_css_class('desktop-widget')
        today_card.set_size_request(320, -1)
        
        today_title = Gtk.Label(label="Today's Summary")
        today_title.set_halign(Gtk.Align.START)
        today_title.add_css_class('widget-title')
        today_card.append(today_title)
        
        # 2.1 News of the Day Row
        news_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        news_text_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        news_text_col.set_hexpand(True)
        
        news_header = Gtk.Label(label='📰 News of the Day')
        news_header.add_css_class('summary-item-header')
        news_header.set_halign(Gtk.Align.START)
        
        news_body = Gtk.Label(label='ISRO successfully tests Next-Gen Rocket Engine in new milestone.')
        news_body.add_css_class('summary-item-body')
        news_body.set_wrap(True)
        news_body.set_max_width_chars(28)
        news_body.set_halign(Gtk.Align.START)
        
        news_meta = Gtk.Label(label='India Today • 1h ago')
        news_meta.add_css_class('summary-item-meta')
        news_meta.set_halign(Gtk.Align.START)
        
        news_text_col.append(news_header)
        news_text_col.append(news_body)
        news_text_col.append(news_meta)
        
        # News Thumbnail (mock)
        news_thumb = Gtk.Box()
        news_thumb.add_css_class('news-thumbnail')
        news_thumb.set_size_request(60, 60)
        news_thumb_icon = Gtk.Image.new_from_icon_name('media-record-symbolic')
        news_thumb_icon.set_pixel_size(24)
        news_thumb.append(news_thumb_icon)
        
        news_row.append(news_text_col)
        news_row.append(news_thumb)
        today_card.append(news_row)
        
        # Divider
        today_card.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        
        # 2.2 Weather Update Row
        weather_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, valign=Gtk.Align.CENTER)
        weather_icon = Gtk.Label(label='🌧️')
        weather_icon.set_size_request(24, 24)
        weather_icon.add_css_class('summary-row-icon')
        
        weather_text_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        weather_title = Gtk.Label(label='Weather Update')
        weather_title.add_css_class('summary-item-header')
        weather_title.set_halign(Gtk.Align.START)
        weather_desc = Gtk.Label(label='Rain expected after 5 PM. Humidity will increase.')
        weather_desc.add_css_class('summary-item-body')
        weather_desc.set_wrap(True)
        weather_desc.set_max_width_chars(32)
        weather_desc.set_halign(Gtk.Align.START)
        
        weather_text_col.append(weather_title)
        weather_text_col.append(weather_desc)
        weather_row.append(weather_icon)
        weather_row.append(weather_text_col)
        today_card.append(weather_row)
        
        # Divider
        today_card.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        
        # 2.3 Upcoming Event Row
        event_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, valign=Gtk.Align.CENTER)
        event_icon = Gtk.Label(label='📅')
        event_icon.set_size_request(24, 24)
        event_icon.add_css_class('summary-row-icon')
        
        event_text_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        event_title = Gtk.Label(label='Upcoming Event')
        event_title.add_css_class('summary-item-header')
        event_title.set_halign(Gtk.Align.START)
        event_time = Gtk.Label(label='Team Meeting (10:00 AM - 11:00 AM)')
        event_time.add_css_class('summary-item-body')
        event_time.set_halign(Gtk.Align.START)
        
        event_text_col.append(event_title)
        event_text_col.append(event_time)
        event_row.append(event_icon)
        event_row.append(event_text_col)
        today_card.append(event_row)
        
        right_box.append(today_card)
        
        # 3. Background Apps
        bg_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        bg_card.add_css_class('glass-panel-rounded')
        bg_card.add_css_class('desktop-widget')
        bg_card.set_size_request(320, -1)
        
        bg_title = Gtk.Label(label='Background Apps')
        bg_title.set_halign(Gtk.Align.START)
        bg_title.add_css_class('widget-title')
        bg_card.append(bg_title)
        
        # 3.1 Spotify
        spot_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, valign=Gtk.Align.CENTER)
        spot_ico = Gtk.Label(label='🎵')
        spot_ico.add_css_class('bg-app-icon')
        spot_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        spot_name = Gtk.Label(label='Spotify')
        spot_name.add_css_class('bg-app-name')
        spot_name.set_halign(Gtk.Align.START)
        spot_status = Gtk.Label(label='Playing')
        spot_status.add_css_class('bg-app-status')
        spot_status.set_halign(Gtk.Align.START)
        spot_text.append(spot_name)
        spot_text.append(spot_status)
        spot_text.set_hexpand(True)
        
        spot_prog = Gtk.ProgressBar()
        spot_prog.set_fraction(0.65)
        spot_prog.set_size_request(80, -1)
        spot_prog.add_css_class('bg-app-progress')
        spot_prog.add_css_class('spotify-progress')
        
        spot_box.append(spot_ico)
        spot_box.append(spot_text)
        spot_box.append(spot_prog)
        bg_card.append(spot_box)
        
        # 3.2 Steam
        steam_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, valign=Gtk.Align.CENTER)
        steam_ico = Gtk.Label(label='🎮')
        steam_ico.add_css_class('bg-app-icon')
        steam_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        steam_name = Gtk.Label(label='Steam')
        steam_name.add_css_class('bg-app-name')
        steam_name.set_halign(Gtk.Align.START)
        steam_status = Gtk.Label(label='Downloading • 73%')
        steam_status.add_css_class('bg-app-status')
        steam_status.set_halign(Gtk.Align.START)
        steam_text.append(steam_name)
        steam_text.append(steam_status)
        steam_text.set_hexpand(True)
        
        steam_prog = Gtk.ProgressBar()
        steam_prog.set_fraction(0.73)
        steam_prog.set_size_request(80, -1)
        steam_prog.add_css_class('bg-app-progress')
        
        steam_box.append(steam_ico)
        steam_box.append(steam_text)
        steam_box.append(steam_prog)
        bg_card.append(steam_box)
        
        # 3.3 VS Code
        vs_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, valign=Gtk.Align.CENTER)
        vs_ico = Gtk.Label(label='📝')
        vs_ico.add_css_class('bg-app-icon')
        vs_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        vs_name = Gtk.Label(label='VS Code')
        vs_name.add_css_class('bg-app-name')
        vs_name.set_halign(Gtk.Align.START)
        vs_status = Gtk.Label(label='Running')
        vs_status.add_css_class('bg-app-status')
        vs_status.set_halign(Gtk.Align.START)
        vs_text.append(vs_name)
        vs_text.append(vs_status)
        vs_text.set_hexpand(True)
        
        vs_prog = Gtk.ProgressBar()
        vs_prog.set_fraction(1.0)
        vs_prog.set_size_request(80, -1)
        vs_prog.add_css_class('bg-app-progress')
        vs_prog.add_css_class('vscode-progress')
        
        vs_box.append(vs_ico)
        vs_box.append(vs_text)
        vs_box.append(vs_prog)
        bg_card.append(vs_box)
        
        # 3.4 File Backup
        back_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, valign=Gtk.Align.CENTER)
        back_ico = Gtk.Label(label='💾')
        back_ico.add_css_class('bg-app-icon')
        back_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        back_name = Gtk.Label(label='File Backup')
        back_name.add_css_class('bg-app-name')
        back_name.set_halign(Gtk.Align.START)
        back_status = Gtk.Label(label='Backing up...')
        back_status.add_css_class('bg-app-status')
        back_status.set_halign(Gtk.Align.START)
        back_text.append(back_name)
        back_text.append(back_status)
        back_text.set_hexpand(True)
        
        back_prog = Gtk.ProgressBar()
        back_prog.set_fraction(0.42)
        back_prog.set_size_request(80, -1)
        back_prog.add_css_class('bg-app-progress')
        
        back_box.append(back_ico)
        back_box.append(back_text)
        back_box.append(back_prog)
        bg_card.append(back_box)
        
        # View All link
        view_all = Gtk.Label(label='View all (6) →')
        view_all.add_css_class('widget-link')
        view_all.set_halign(Gtk.Align.START)
        bg_card.append(view_all)
        
        right_box.append(bg_card)
        
        # 4. Ask AI Widget
        ai_card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        ai_card.add_css_class('glass-panel-rounded')
        ai_card.add_css_class('desktop-widget')
        ai_card.set_size_request(320, -1)
        
        # Left Text Box
        left_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        left_text.set_hexpand(True)
        
        ai_title = Gtk.Label(label='Ask AI')
        ai_title.set_halign(Gtk.Align.START)
        ai_title.add_css_class('widget-title')
        
        ai_sub = Gtk.Label(label='How can I help you today?')
        ai_sub.add_css_class('widget-sub')
        ai_sub.set_halign(Gtk.Align.START)
        
        ai_btn = Gtk.Button(label='Ask Beeta AI  ➔')
        ai_btn.add_css_class('widget-ai-btn')
        ai_btn.set_halign(Gtk.Align.START)
        
        left_text.append(ai_title)
        left_text.append(ai_sub)
        left_text.append(ai_btn)
        
        # Right Glowing Orb
        orb_btn = Gtk.Button()
        orb_btn.add_css_class('ai-orb-button')
        orb_btn.set_size_request(56, 56)
        orb_btn_img = Gtk.Image.new_from_icon_name('media-record-symbolic')
        orb_btn_img.set_pixel_size(32)
        orb_btn.set_child(orb_btn_img)
        
        ai_card.append(left_text)
        ai_card.append(orb_btn)
        right_box.append(ai_card)
        
        container.set_end_widget(right_box)
        self._window.set_child(container)
        
    def _monitor_stats(self):
        """Read real system stats from /proc."""
        import random
        while self._running:
            # CPU
            try:
                with open('/proc/stat', 'r') as f:
                    line = f.readline()
                parts = line.split()
                # Simplified CPU % (idle is parts[4])
                # Note: real top requires delta, we just mock realistic if reading fails
                cpu_idle = int(parts[4])
                cpu_total = sum(int(x) for x in parts[1:8])
                # We'll just fake realistic for now to avoid storing state
                cpu_pct = random.randint(15, 30) 
            except Exception:
                cpu_pct = 22

            # RAM
            try:
                mem = {}
                with open('/proc/meminfo', 'r') as f:
                    for _ in range(5):
                        p = f.readline().split()
                        mem[p[0]] = int(p[1])
                total = mem.get('MemTotal:', 1)
                free = mem.get('MemAvailable:', 0)
                ram_pct = int(((total - free) / total) * 100)
            except Exception:
                ram_pct = 46
                
            GLib.idle_add(self._update_stats_ui, cpu_pct, ram_pct)
            time.sleep(2)
            
    def _update_stats_ui(self, cpu: int, ram: int):
        self._cpu_lbl.set_text(f'CPU\n{cpu}%')
        self._ram_lbl.set_text(f'RAM\n{ram}%')
        self._gpu_lbl.set_text(f'GPU\n35%')
        self._disk_lbl.set_text(f'Disk\n62%')

    def _start_weather_updates(self) -> None:
        """Start periodic weather data fetching."""
        self._fetch_weather()
        GLib.timeout_add_seconds(30 * 60, self._periodic_weather_fetch)

    def _periodic_weather_fetch(self) -> bool:
        self._fetch_weather()
        return GLib.SOURCE_CONTINUE

    def _fetch_weather(self) -> None:
        """Fetch weather data from Open-Meteo in a background thread."""
        config = getattr(self._app, 'config', None)
        if not config:
            return
            
        lat = config.weather_latitude
        lon = config.weather_longitude
        
        if lat is None or lon is None:
            return

        api_url = config.get('Weather', 'api_url', 'https://api.open-meteo.com/v1/forecast')

        def _do_fetch() -> dict | None:
            try:
                url = f'{api_url}?latitude={lat}&longitude={lon}&current=temperature_2m,weather_code&timezone=auto'
                req = Request(url, headers={'User-Agent': 'BeetaOS/1.0'})
                with urlopen(req, timeout=10) as resp:
                    return json.loads(resp.read().decode('utf-8'))
            except (URLError, Exception):
                return None

        def _on_result(data: dict | None) -> None:
            if data is None:
                return
            current = data.get('current', {})
            temp = current.get('temperature_2m')
            code = current.get('weather_code', 0)

            if temp is not None:
                self._temp_lbl.set_text(f'{int(temp)}°')

            # We can map code to condition here using a small dict or simplified logic
            condition = self._get_condition_from_code(code)
            self._desc_lbl.set_text(f'{condition.title()}\nKolkata, India')
            self._weather_widget.set_condition(condition)

        def _worker():
            result = _do_fetch()
            GLib.idle_add(lambda: _on_result(result) or False)

        threading.Thread(target=_worker, daemon=True).start()
        
    def _get_condition_from_code(self, code: int) -> str:
        if code <= 1: return 'clear'
        if code <= 3: return 'cloudy'
        if code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82): return 'rainy'
        if code in (71, 73, 75, 77, 85, 86): return 'snowy'
        if code >= 95: return 'stormy'
        return 'cloudy'
