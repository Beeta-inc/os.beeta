# -*- coding: utf-8 -*-
# Beeta Desktop Environment
# Copyright (C) 2023-2026 Beeta Technologies Inc.
# Licensed under GNU General Public License v3.0

"""Bottom bar panel for the Beeta Desktop Shell.

The bottom bar is a Wayland layer-shell surface anchored to the
bottom edge. It contains three sections:

    ┌──────────────────────────────────────────────────────┐
    │  🟣        📁 🖥 🌐 🧮 ⚙️            22°C ☀ 🤖  │
    └──────────────────────────────────────────────────────┘
    Left:   Beeta Orb (launcher trigger button)
    Center: Pinned Apps Dock (with hover magnification)
    Right:  Weather + AI Widget

In Focus State, the bar slides off-screen and can be revealed by:
    - Moving the mouse to the bottom edge for ~150ms
    - Pressing the Super key
"""

from __future__ import annotations

import json
import threading
from typing import TYPE_CHECKING, Optional
from urllib.request import urlopen, Request
from urllib.error import URLError

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gtk4LayerShell', '1.0')
from gi.repository import Gtk, Gtk4LayerShell, Gdk, GLib, GObject

if TYPE_CHECKING:
    from .config import BeetaConfig
    from .adaptive_motion import AdaptiveMotion
    from .adaptive_nature import AdaptiveNature
    from .states import StateManager

from .dock import Dock
from .launcher import Launcher
from .weather_renderer import PhysicsWeatherWidget


# Bottom bar height in pixels
_BAR_HEIGHT: int = 56

# Height of the invisible edge-hover detection zone
_EDGE_ZONE_HEIGHT: int = 4


class BottomBar:
    """Bottom bar panel using Wayland layer-shell.

    Contains the Beeta Orb launcher button, pinned apps dock, and
    weather+AI widget. Manages its own visibility state including
    Focus State auto-hide and edge-hover reveal.

    Args:
        app: The parent Gtk.Application.
        config: Beeta configuration instance.
        adaptive_motion: Adaptive Motion engine.
        adaptive_nature: Adaptive Nature engine.
        state_manager: Desktop/Focus state manager.
    """

    def __init__(
        self,
        app: Gtk.Application,
        config: BeetaConfig,
        adaptive_motion: AdaptiveMotion,
        adaptive_nature: AdaptiveNature,
        state_manager: StateManager,
    ) -> None:
        self._app = app
        self._config = config
        self._motion = adaptive_motion
        self._nature = adaptive_nature
        self._state_mgr = state_manager
        self._is_hidden: bool = False

        # Weather state
        self._temperature: Optional[float] = None
        self._weather_icon: str = '☀️'
        self._weather_condition: str = 'clear'

        # Create the layer-shell window for the bar
        self._window = Gtk.Window(application=app)
        self._window.set_title('Beeta Bottom Bar')
        self._window.set_decorated(False)

        Gtk4LayerShell.init_for_window(self._window)
        Gtk4LayerShell.set_layer(
            self._window, Gtk4LayerShell.Layer.TOP
        )
        Gtk4LayerShell.set_namespace(self._window, 'beeta-bottombar')

        # Anchor to bottom, left, right
        Gtk4LayerShell.set_anchor(
            self._window, Gtk4LayerShell.Edge.BOTTOM, True
        )
        Gtk4LayerShell.set_anchor(
            self._window, Gtk4LayerShell.Edge.LEFT, True
        )
        Gtk4LayerShell.set_anchor(
            self._window, Gtk4LayerShell.Edge.RIGHT, True
        )

        # Reserve space for the dock
        Gtk4LayerShell.set_exclusive_zone(self._window, _BAR_HEIGHT)

        # Force window to stretch to full width
        self._window.set_default_size(9999, _BAR_HEIGHT)

        # Initialize edge interaction zone window (invisible)
        self._edge_window = Gtk.Window(application=app)
        self._edge_window.set_title('Beeta Edge Zone')
        self._edge_window.set_decorated(False)

        Gtk4LayerShell.init_for_window(self._edge_window)
        Gtk4LayerShell.set_layer(
            self._edge_window, Gtk4LayerShell.Layer.TOP
        )
        Gtk4LayerShell.set_namespace(
            self._edge_window, 'beeta-edge-zone'
        )
        Gtk4LayerShell.set_anchor(
            self._edge_window, Gtk4LayerShell.Edge.BOTTOM, True
        )
        Gtk4LayerShell.set_anchor(
            self._edge_window, Gtk4LayerShell.Edge.LEFT, True
        )
        Gtk4LayerShell.set_anchor(
            self._edge_window, Gtk4LayerShell.Edge.RIGHT, True
        )
        Gtk4LayerShell.set_exclusive_zone(self._edge_window, 0)
        self._edge_window.set_default_size(-1, _EDGE_ZONE_HEIGHT)

        # Edge zone is transparent and just detects mouse
        edge_box = Gtk.Box()
        edge_box.set_opacity(0)
        self._edge_window.set_child(edge_box)

        # Edge hover detection
        edge_motion = Gtk.EventControllerMotion()
        edge_motion.connect('enter', self._on_edge_enter)
        edge_box.add_controller(edge_motion)

        # Bar leave detection
        bar_motion = Gtk.EventControllerMotion()
        bar_motion.connect('leave', self._on_bar_leave)
        self._window.add_controller(bar_motion)

        # Create launcher
        self._launcher = Launcher(app, adaptive_motion)

        # Build bar content
        self._build_content()

        # Connect state manager
        self._state_mgr.connect('state-changed', self._on_state_changed)
        self._state_mgr.connect(
            'bar-reveal-requested', self._on_bar_reveal
        )
        self._state_mgr.connect(
            'bar-dismiss-requested', self._on_bar_dismiss
        )

        # Apply motion tier CSS
        self._container.add_css_class(self._motion.css_class)
        self._motion.connect(
            'tier-changed', self._on_motion_tier_changed
        )

        # Start weather updates
        self._start_weather_updates()

        # Show the bar
        self._window.present()
        # Edge zone hidden by default (only shown in Focus State)
        self._edge_window.set_visible(False)

    @property
    def window(self) -> Gtk.Window:
        """The underlying Gtk.Window."""
        return self._window

    @property
    def launcher(self) -> Launcher:
        """The app launcher instance."""
        return self._launcher

    @property
    def dock(self) -> Dock:
        """The pinned apps dock."""
        return self._dock

    def show_bar(self) -> None:
        """Show the bottom bar (slide up)."""
        if not self._is_hidden:
            return
        self._is_hidden = False
        Gtk4LayerShell.set_exclusive_zone(self._window, _BAR_HEIGHT)
        Gtk4LayerShell.set_margin(
            self._window, Gtk4LayerShell.Edge.BOTTOM, 0
        )
        self._container.remove_css_class('hidden')
        self._window.set_visible(True)

        # Resume animations
        self._motion.resume_component('bottombar')
        self._motion.resume_component('dock')

    def hide_bar(self) -> None:
        """Hide the bottom bar (slide down)."""
        if self._is_hidden:
            return
        self._is_hidden = True
        Gtk4LayerShell.set_exclusive_zone(self._window, 0)
        Gtk4LayerShell.set_margin(
            self._window, Gtk4LayerShell.Edge.BOTTOM, -_BAR_HEIGHT
        )
        self._container.add_css_class('hidden')

        # Pause animations to save resources
        self._motion.pause_component('bottombar')
        self._motion.pause_component('dock')

    def set_focus_mode(self, is_focus: bool) -> None:
        """Transition between Desktop and Focus state.

        Args:
            is_focus: True for Focus State, False for Desktop State.
        """
        if is_focus:
            self.hide_bar()
            # Show the edge detection zone
            self._edge_window.set_visible(True)
            self._edge_window.present()
        else:
            self.show_bar()
            # Hide the edge detection zone
            self._edge_window.set_visible(False)

    # ── Internal: Build UI ───────────────────────────────────────

    def _build_content(self) -> None:
        """Build the three-section bottom bar layout."""
        self._container = Gtk.CenterBox()
        self._container.set_hexpand(True)
        self._container.set_halign(Gtk.Align.FILL)
        # Main background is transparent; the three boxes are the glass pills
        self._container.add_css_class('bottombar')

        # ── Left: Beeta Orb ──
        left_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            halign=Gtk.Align.START,
            valign=Gtk.Align.END,
            margin_start=24,
            margin_bottom=12,
        )
        
        left_pill = Gtk.Box()
        left_pill.add_css_class('glass-panel-rounded')
        left_pill.add_css_class('bottombar-pill')
        
        orb = Gtk.Button()
        orb.add_css_class('beeta-orb')
        orb.set_tooltip_text('Beeta Start Menu')

        # Mockup shows a glowing AI/Start ring for the orb, we'll use a custom icon
        orb_icon = Gtk.Image.new_from_icon_name('system-search-symbolic')
        orb_icon.set_pixel_size(24)
        orb.set_child(orb_icon)
        orb.connect('clicked', self._on_orb_clicked)

        left_pill.append(orb)
        left_box.append(left_pill)
        self._container.set_start_widget(left_box)

        # ── Center: Dock ──
        self._dock = Dock(self._config, self._motion)
        center_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.END,
            margin_bottom=12,
        )
        center_pill = Gtk.Box()
        center_pill.add_css_class('glass-panel-rounded')
        center_pill.add_css_class('bottombar-pill')
        center_pill.add_css_class('dock-pill')
        center_pill.append(self._dock)
        
        center_box.append(center_pill)
        self._container.set_center_widget(center_box)

        # ── Right: Weather + AI ──
        right_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            halign=Gtk.Align.END,
            valign=Gtk.Align.END,
            margin_end=24,
            margin_bottom=12,
        )
        
        right_pill = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        right_pill.add_css_class('glass-panel-rounded')
        right_pill.add_css_class('bottombar-pill')
        
        # Upper row for Weather, lower row for Ask AI, wait mockup has them side by side.
        right_content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)

        # Weather widget text col
        weather_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._weather_temp_label = Gtk.Label(label='--°C')
        self._weather_temp_label.add_css_class('bottombar-weather-temp')
        self._weather_temp_label.set_halign(Gtk.Align.END)
        self._weather_desc_label = Gtk.Label(label='Loading...')
        self._weather_desc_label.add_css_class('bottombar-weather-desc')
        self._weather_desc_label.set_halign(Gtk.Align.END)
        weather_text.append(self._weather_temp_label)
        weather_text.append(self._weather_desc_label)
        
        weather_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._weather_widget = PhysicsWeatherWidget(adaptive_motion=self._motion, width=28, height=28)
        weather_box.append(self._weather_widget)
        weather_box.append(weather_text)
        
        right_content.append(weather_box)

        # AI button
        ai_btn = Gtk.Button()
        ai_btn.add_css_class('ai-button')
        ai_btn_img = Gtk.Image.new_from_icon_name('preferences-system-symbolic') # AI icon placeholder
        ai_btn_img.set_pixel_size(24)
        ai_btn.set_child(ai_btn_img)
        ai_btn.set_tooltip_text('Ask Beeta AI')
        ai_btn.connect('clicked', self._on_ai_clicked)
        right_content.append(ai_btn)

        right_pill.append(right_content)
        right_box.append(right_pill)

        self._container.set_end_widget(right_box)
        self._window.set_child(self._container)

    # ── Internal: Weather ────────────────────────────────────────

    def _start_weather_updates(self) -> None:
        """Start periodic weather data fetching."""
        self._fetch_weather()
        interval = self._config.get_int(
            'Weather', 'update_interval_minutes', 30
        )
        GLib.timeout_add_seconds(
            interval * 60, self._periodic_weather_fetch
        )

    def _fetch_weather(self) -> None:
        """Fetch weather data from Open-Meteo in a background thread."""
        lat = self._config.weather_latitude
        lon = self._config.weather_longitude

        if lat is None or lon is None:
            return

        api_url = self._config.get(
            'Weather', 'api_url',
            'https://api.open-meteo.com/v1/forecast',
        )

        def _do_fetch() -> Optional[dict]:
            try:
                url = (
                    f'{api_url}?latitude={lat}&longitude={lon}'
                    f'&current=temperature_2m,weather_code'
                    f'&timezone=auto'
                )
                req = Request(url, headers={'User-Agent': 'BeetaOS/1.0'})
                with urlopen(req, timeout=10) as resp:
                    return json.loads(resp.read().decode('utf-8'))
            except (URLError, Exception):
                return None

        def _on_result(data: Optional[dict]) -> None:
            if data is None:
                return
            current = data.get('current', {})
            temp = current.get('temperature_2m')
            code = current.get('weather_code', 0)

            if temp is not None:
                self._temperature = float(temp)
                self._weather_temp_label.set_text(f'{int(temp)}°C')

            self._weather_condition = self._code_to_condition(code)
            self._weather_desc_label.set_text(self._weather_condition.title())
            
            # Feed condition to the physics widget
            if hasattr(self, '_weather_widget'):
                self._weather_widget.set_condition(self._weather_condition)

            # Feed weather data to Adaptive Nature
            if self._temperature is not None:
                self._nature.set_weather(
                    self._temperature, self._weather_condition
                )

        def _worker():
            result = _do_fetch()
            GLib.idle_add(lambda: _on_result(result) or False)

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()

    def _periodic_weather_fetch(self) -> bool:
        """Periodic weather fetch callback."""
        self._fetch_weather()
        return GLib.SOURCE_CONTINUE

    @staticmethod
    def _code_to_emoji(code: int) -> str:
        """Convert WMO weather code to emoji icon."""
        if code <= 1:
            return '☀️'
        elif code <= 3:
            return '⛅'
        elif code in (45, 48):
            return '🌫️'
        elif code in (51, 53, 55, 56, 57):
            return '🌦️'
        elif code in (61, 63, 65, 66, 67, 80, 81, 82):
            return '🌧️'
        elif code in (71, 73, 75, 77, 85, 86):
            return '❄️'
        elif code >= 95:
            return '⛈️'
        else:
            return '☁️'

    @staticmethod
    def _code_to_condition(code: int) -> str:
        """Convert WMO weather code to Beeta condition string."""
        if code <= 1:
            return 'clear'
        elif code <= 3:
            return 'cloudy'
        elif code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82):
            return 'rainy'
        elif code in (71, 73, 75, 77, 85, 86):
            return 'snowy'
        elif code >= 95:
            return 'rainy'
        else:
            return 'cloudy'

    # ── Internal: Event Handlers ─────────────────────────────────

    def _on_orb_clicked(self, button: Gtk.Button) -> None:
        """Handle Beeta Orb click — toggle launcher."""
        self._launcher.toggle()

    def _on_ai_clicked(self, button: Gtk.Button) -> None:
        """Handle AI button click — placeholder for Beeta AI panel."""
        # Future: open the Beeta AI chat panel
        pass

    def _on_state_changed(
        self, state_mgr: StateManager, state: str
    ) -> None:
        """React to Desktop/Focus state transitions."""
        self.set_focus_mode(state == 'focus')

    def _on_bar_reveal(self, state_mgr: StateManager) -> None:
        """Temporarily show the bar in Focus State."""
        self.show_bar()
        # Keep edge zone visible for leave detection
        self._edge_window.set_visible(True)

    def _on_bar_dismiss(self, state_mgr: StateManager) -> None:
        """Dismiss the temporarily revealed bar."""
        if self._state_mgr.current_state == 'focus':
            self.hide_bar()

    def _on_edge_enter(
        self,
        controller: Gtk.EventControllerMotion,
        x: float,
        y: float,
    ) -> None:
        """Mouse entered the bottom edge zone."""
        self._state_mgr.on_edge_hover_enter()

    def _on_bar_leave(
        self, controller: Gtk.EventControllerMotion
    ) -> None:
        """Mouse left the bottom bar."""
        self._state_mgr.on_edge_hover_leave()

    def _on_motion_tier_changed(
        self, motion: AdaptiveMotion, tier: str
    ) -> None:
        """Update CSS motion class when tier changes."""
        for cls in ('motion-saver', 'motion-balanced', 'motion-performance'):
            self._container.remove_css_class(cls)
        self._container.add_css_class(motion.css_class)

    def cleanup(self) -> None:
        """Clean up all child components. Call on shutdown."""
        self._dock.cleanup()
