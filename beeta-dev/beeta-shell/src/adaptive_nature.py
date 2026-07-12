# -*- coding: utf-8 -*-
# Beeta Desktop Environment
# Copyright (C) 2023-2026 Beeta Technologies Inc.
# Licensed under GNU General Public License v3.0

"""Beeta Adaptive Nature™ — Context-aware theming engine.

Instead of asking "What color is the wallpaper?", Beeta OS asks
"What's happening around the user?" and adapts the UI accordingly.

Inputs:
    - Time of day (sunrise, afternoon, sunset, night)
    - Local temperature (from Open-Meteo API)
    - Weather condition (clear, cloudy, rainy, snowy)
    - Battery level and charging state
    - Performance mode
    - Wallpaper dominant color (from tint-engine)

Output:
    - Dynamically generated GTK4 CSS custom properties that shift
      accent colors, glass tint, border intensity, and ambient overlays.

All transitions are gradual (2-4 seconds) so users *feel* the
change rather than consciously notice it.

Three user modes:
    - Static:     Fixed theme, no adaptation.
    - Adaptive:   Subtly responds to environment (recommended).
    - Expressive: Bolder transitions and richer ambient effects.
"""

from __future__ import annotations

import json
import math
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from urllib.request import urlopen, Request
from urllib.error import URLError

from gi.repository import Gdk, GLib, GObject, Gtk

if TYPE_CHECKING:
    from .config import BeetaConfig


def _lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation between a and b by factor t (0.0 - 1.0)."""
    return a + (b - a) * max(0.0, min(1.0, t))


def _lerp_color(
    c1: tuple[float, ...], c2: tuple[float, ...], t: float
) -> tuple[float, ...]:
    """Linearly interpolate between two RGBA color tuples."""
    return tuple(_lerp(a, b, t) for a, b in zip(c1, c2))


def _rgba_str(r: float, g: float, b: float, a: float = 1.0) -> str:
    """Format RGBA values (0-255 for RGB, 0-1 for A) as CSS rgba()."""
    return f'rgba({int(r)}, {int(g)}, {int(b)}, {a:.3f})'


# ── Time-of-day color palettes ───────────────────────────────────

# Each palette defines: accent_primary, glass_bg, ambient_tint
_PALETTE_MORNING = {
    'accent_primary':   (255, 200, 120, 1.0),   # warm golden
    'accent_secondary': (255, 160, 100, 1.0),    # soft orange
    'glass_bg':         (25, 20, 15, 0.75),       # warm dark
    'glass_border':     (255, 255, 255, 0.12),
    'ambient_tint':     (255, 200, 120, 0.04),   # faint warm glow
}

_PALETTE_AFTERNOON = {
    'accent_primary':   (94, 200, 255, 1.0),     # clean blue
    'accent_secondary': (120, 140, 255, 1.0),    # bright purple-blue
    'glass_bg':         (18, 18, 28, 0.72),       # neutral dark
    'glass_border':     (255, 255, 255, 0.14),
    'ambient_tint':     (255, 255, 255, 0.02),   # neutral
}

_PALETTE_EVENING = {
    'accent_primary':   (255, 170, 80, 1.0),     # amber/sunset
    'accent_secondary': (200, 120, 255, 1.0),    # purple
    'glass_bg':         (20, 15, 22, 0.78),       # warm dark
    'glass_border':     (255, 255, 255, 0.10),
    'ambient_tint':     (255, 160, 80, 0.04),    # warm amber
}

_PALETTE_NIGHT = {
    'accent_primary':   (94, 231, 255, 1.0),     # cool cyan
    'accent_secondary': (155, 108, 255, 1.0),    # purple
    'glass_bg':         (12, 14, 32, 0.75),       # deep blue-dark
    'glass_border':     (255, 255, 255, 0.12),
    'ambient_tint':     (94, 180, 255, 0.03),    # cool blue
}

# ── Weather color modifiers ──────────────────────────────────────
# Applied as subtle tint adjustments on top of time-of-day palette

_WEATHER_MODIFIERS = {
    'clear': {
        'tint': (0, 0, 0, 0.0),          # no modification
        'border_boost': 0.02,
    },
    'cloudy': {
        'tint': (150, 160, 180, 0.02),   # slight grey-blue
        'border_boost': -0.02,
    },
    'rainy': {
        'tint': (80, 120, 180, 0.04),    # cooler blue
        'border_boost': -0.03,
    },
    'snowy': {
        'tint': (200, 220, 255, 0.05),   # frosted white-blue
        'border_boost': 0.03,
    },
}

# ── Temperature color adjustments ────────────────────────────────
# Hot days get warm amber, cold days get icy blue

_TEMP_HOT_TINT = (255, 180, 80, 0.03)    # warm amber at >35°C
_TEMP_COLD_TINT = (120, 180, 255, 0.03)  # icy blue at <10°C


class AdaptiveNature(GObject.Object):
    """Context-aware theming engine for the Beeta Desktop Shell.

    Monitors environmental context (time, weather, battery) and
    dynamically generates GTK4 CSS custom properties that give the
    entire shell a context-appropriate look and feel.

    Signals:
        theme-updated():
            Emitted after CSS custom properties have been recalculated
            and applied. UI components can use this to trigger redraws
            if needed.

    Example:
        >>> nature = AdaptiveNature(config)
        >>> nature.apply_css(Gdk.Display.get_default())
        >>> nature.start()
        >>> nature.connect('theme-updated', lambda _: print('Theme updated'))
    """

    __gsignals__ = {
        'theme-updated': (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    # Update interval in seconds for periodic theme recalculation
    _UPDATE_INTERVAL_S: int = 60

    # Weather fetch interval in seconds
    _WEATHER_INTERVAL_S: int = 1800  # 30 minutes

    def __init__(self, config: BeetaConfig) -> None:
        """Initialize the Adaptive Nature engine.

        Args:
            config: Beeta configuration instance.
        """
        super().__init__()
        self._config = config
        self._css_provider: Optional[Gtk.CssProvider] = None
        self._display: Optional[Gdk.Display] = None
        self._update_source: int = 0
        self._weather_source: int = 0

        # Current environmental state
        self._temperature: Optional[float] = None
        self._weather_condition: str = 'clear'
        self._battery_level: int = 100
        self._is_charging: bool = False
        self._wallpaper_color: Optional[tuple[int, int, int]] = None

        # Computed theme values (cached for property access)
        self._current_accent_primary: str = ''
        self._current_accent_secondary: str = ''
        self._current_glass_bg: str = ''
        self._current_glass_border: str = ''
        self._current_ambient_tint: str = ''
        self._current_time_period: str = 'night'

    @property
    def mode(self) -> str:
        """Current Adaptive Nature mode from config."""
        return self._config.adaptive_mode

    @property
    def time_period(self) -> str:
        """Current time period: 'morning', 'afternoon', 'evening', 'night'."""
        return self._current_time_period

    @property
    def accent_color(self) -> str:
        """Current primary accent color as CSS rgba()."""
        return self._current_accent_primary

    @property
    def glass_bg(self) -> str:
        """Current glass background color as CSS rgba()."""
        return self._current_glass_bg

    @property
    def glass_border(self) -> str:
        """Current glass border color as CSS rgba()."""
        return self._current_glass_border

    @property
    def ambient_tint(self) -> str:
        """Current ambient tint overlay as CSS rgba()."""
        return self._current_ambient_tint

    # ── Public API ───────────────────────────────────────────────

    def apply_css(self, display: Gdk.Display) -> None:
        """Attach the CSS provider to the given display.

        Args:
            display: The Gdk.Display to apply styles to.
        """
        self._display = display
        self._css_provider = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(
            display,
            self._css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 100,
        )
        self.update_theme()

    def start(self) -> None:
        """Start periodic theme updates and weather fetching."""
        self.update_theme()

        # Periodic theme recalculation (every 60 seconds for time changes)
        if self._update_source:
            GLib.source_remove(self._update_source)
        self._update_source = GLib.timeout_add_seconds(
            self._UPDATE_INTERVAL_S, self._periodic_update
        )

        # Initial weather fetch, then periodic
        self._fetch_weather_async()
        if self._weather_source:
            GLib.source_remove(self._weather_source)
        self._weather_source = GLib.timeout_add_seconds(
            self._WEATHER_INTERVAL_S, self._periodic_weather_fetch
        )

    def stop(self) -> None:
        """Stop all periodic updates."""
        if self._update_source:
            GLib.source_remove(self._update_source)
            self._update_source = 0
        if self._weather_source:
            GLib.source_remove(self._weather_source)
            self._weather_source = 0

    def set_weather(self, temperature: float, condition: str) -> None:
        """Manually set weather data (useful for testing).

        Args:
            temperature: Temperature in Celsius.
            condition: Weather condition ('clear', 'cloudy', 'rainy', 'snowy').
        """
        self._temperature = temperature
        if condition in _WEATHER_MODIFIERS:
            self._weather_condition = condition
        self.update_theme()

    def set_battery(self, level: int, charging: bool) -> None:
        """Update battery state for theme adaptation.

        Args:
            level: Battery percentage (0-100).
            charging: Whether the battery is currently charging.
        """
        self._battery_level = max(0, min(100, level))
        self._is_charging = charging
        # Battery state affects glass opacity in power-save scenarios
        self.update_theme()

    def set_wallpaper_color(self, r: int, g: int, b: int) -> None:
        """Set the wallpaper dominant color for tinting.

        Args:
            r: Red component (0-255).
            g: Green component (0-255).
            b: Blue component (0-255).
        """
        self._wallpaper_color = (r, g, b)
        self.update_theme()

    def update_theme(self) -> None:
        """Recalculate theme colors and apply CSS.

        This is the core method that blends all environmental inputs
        into a final set of CSS custom properties.
        """
        if self._css_provider is None:
            return

        if self.mode == 'static':
            # Static mode: use night palette always, no adaptation
            palette = _PALETTE_NIGHT
            css = self._generate_css(palette, apply_weather=False)
        else:
            # Determine time-of-day palette with smooth blending
            palette = self._compute_time_palette()

            # Apply weather and temperature modifiers
            css = self._generate_css(palette, apply_weather=True)

        self._css_provider.load_from_string(css)
        self.emit('theme-updated')

    # ── Internal: Time-of-day Blending ───────────────────────────

    def _get_time_period(self) -> str:
        """Determine current time period from system clock."""
        hour = datetime.now().hour

        if 6 <= hour < 11:
            return 'morning'
        elif 11 <= hour < 17:
            return 'afternoon'
        elif 17 <= hour < 20:
            return 'evening'
        else:
            return 'night'

    def _compute_time_palette(self) -> dict[str, tuple[float, ...]]:
        """Compute blended color palette based on current time.

        Uses smooth sinusoidal interpolation between adjacent time
        periods to avoid abrupt color shifts.
        """
        hour = datetime.now().hour
        minute = datetime.now().minute
        time_frac = hour + minute / 60.0

        self._current_time_period = self._get_time_period()

        # Define transition zones with smooth blending
        if 5.0 <= time_frac < 8.0:
            # Night → Morning transition
            t = (time_frac - 5.0) / 3.0
            t = self._smooth_step(t)
            return self._blend_palettes(_PALETTE_NIGHT, _PALETTE_MORNING, t)
        elif 8.0 <= time_frac < 11.0:
            # Morning → Afternoon transition
            t = (time_frac - 8.0) / 3.0
            t = self._smooth_step(t)
            return self._blend_palettes(
                _PALETTE_MORNING, _PALETTE_AFTERNOON, t
            )
        elif 11.0 <= time_frac < 16.0:
            # Solid afternoon
            return dict(_PALETTE_AFTERNOON)
        elif 16.0 <= time_frac < 18.0:
            # Afternoon → Evening transition
            t = (time_frac - 16.0) / 2.0
            t = self._smooth_step(t)
            return self._blend_palettes(
                _PALETTE_AFTERNOON, _PALETTE_EVENING, t
            )
        elif 18.0 <= time_frac < 21.0:
            # Evening → Night transition
            t = (time_frac - 18.0) / 3.0
            t = self._smooth_step(t)
            return self._blend_palettes(_PALETTE_EVENING, _PALETTE_NIGHT, t)
        else:
            # Solid night
            return dict(_PALETTE_NIGHT)

    @staticmethod
    def _smooth_step(t: float) -> float:
        """Smoothstep function for natural-feeling transitions."""
        t = max(0.0, min(1.0, t))
        return t * t * (3.0 - 2.0 * t)

    @staticmethod
    def _blend_palettes(
        p1: dict[str, tuple[float, ...]],
        p2: dict[str, tuple[float, ...]],
        t: float,
    ) -> dict[str, tuple[float, ...]]:
        """Blend two color palettes by interpolation factor t."""
        result = {}
        for key in p1:
            result[key] = _lerp_color(p1[key], p2[key], t)
        return result

    # ── Internal: CSS Generation ─────────────────────────────────

    def _generate_css(
        self,
        palette: dict[str, tuple[float, ...]],
        apply_weather: bool,
    ) -> str:
        """Generate CSS custom property definitions from palette.

        Args:
            palette: Color palette with named color tuples.
            apply_weather: Whether to apply weather/temp modifiers.

        Returns:
            CSS string with @define-color directives.
        """
        # Start with the time-of-day palette colors
        accent_p = palette['accent_primary']
        accent_s = palette['accent_secondary']
        glass_bg = palette['glass_bg']
        glass_border = palette['glass_border']
        ambient = palette['ambient_tint']

        if apply_weather:
            # Apply weather condition modifier
            weather_mod = _WEATHER_MODIFIERS.get(
                self._weather_condition,
                _WEATHER_MODIFIERS['clear'],
            )
            weather_tint = weather_mod['tint']
            border_boost = weather_mod['border_boost']

            # Blend weather tint into ambient
            if weather_tint[3] > 0:
                ambient = _lerp_color(ambient, weather_tint, 0.5)

            # Adjust border opacity
            glass_border = (
                glass_border[0],
                glass_border[1],
                glass_border[2],
                max(0.05, min(0.25, glass_border[3] + border_boost)),
            )

            # Apply temperature modifier
            if self._temperature is not None:
                if self._temperature > 35:
                    # Hot: blend warm amber tint
                    intensity = min(1.0, (self._temperature - 35) / 15.0)
                    if self.mode == 'expressive':
                        intensity *= 1.5
                    ambient = _lerp_color(
                        ambient, _TEMP_HOT_TINT, intensity * 0.4
                    )
                elif self._temperature < 10:
                    # Cold: blend icy blue tint
                    intensity = min(1.0, (10 - self._temperature) / 15.0)
                    if self.mode == 'expressive':
                        intensity *= 1.5
                    ambient = _lerp_color(
                        ambient, _TEMP_COLD_TINT, intensity * 0.4
                    )

            # Wallpaper color contribution (subtle)
            if self._wallpaper_color is not None:
                wr, wg, wb = self._wallpaper_color
                wp_tint = (wr, wg, wb, 0.02)
                # Wallpaper contributes a very subtle tint to the ambient
                blend_factor = 0.15 if self.mode == 'expressive' else 0.08
                ambient = _lerp_color(ambient, wp_tint, blend_factor)

        # Adjust glass opacity based on battery / performance mode
        glass_opacity = glass_bg[3]
        perf_mode = self._config.performance_mode
        if perf_mode == 'power-saver' or self._battery_level < 20:
            # Increase opacity (reduce transparency) to save GPU
            glass_opacity = min(1.0, glass_opacity + 0.15)
        elif perf_mode == 'performance':
            # Slightly more transparent for richer glass effect
            glass_opacity = max(0.5, glass_opacity - 0.05)

        glass_bg = (glass_bg[0], glass_bg[1], glass_bg[2], glass_opacity)

        # Cache computed values for property access
        self._current_accent_primary = _rgba_str(*accent_p)
        self._current_accent_secondary = _rgba_str(*accent_s)
        self._current_glass_bg = _rgba_str(*glass_bg)
        self._current_glass_border = _rgba_str(*glass_border)
        self._current_ambient_tint = _rgba_str(*ambient)

        # Expressive mode: boost accent saturation and ambient intensity
        if self.mode == 'expressive':
            ambient = (
                ambient[0], ambient[1], ambient[2],
                min(0.1, ambient[3] * 2.0),
            )
            self._current_ambient_tint = _rgba_str(*ambient)

        # Generate the CSS
        css = f"""
@define-color beeta_accent_primary   {self._current_accent_primary};
@define-color beeta_accent_secondary {self._current_accent_secondary};
@define-color beeta_accent_tertiary  rgba(255, 107, 214, 1.0);

@define-color beeta_glass_bg         {self._current_glass_bg};
@define-color beeta_glass_border     {self._current_glass_border};
@define-color beeta_glass_shadow     rgba(0, 0, 0, {glass_opacity * 0.5:.3f});
@define-color beeta_ambient_tint     {self._current_ambient_tint};

@define-color beeta_text_primary     rgba(238, 241, 255, 1.0);
@define-color beeta_text_secondary   rgba(238, 241, 255, 0.7);
@define-color beeta_text_muted       rgba(238, 241, 255, 0.45);

@define-color beeta_success          rgba(6, 214, 160, 1.0);
@define-color beeta_warning          rgba(255, 209, 102, 1.0);
@define-color beeta_danger           rgba(255, 107, 107, 1.0);
"""
        return css

    # ── Internal: Weather Fetching ───────────────────────────────

    def _fetch_weather_async(self) -> None:
        """Fetch weather data from Open-Meteo API in a background thread."""
        lat = self._config.weather_latitude
        lon = self._config.weather_longitude

        if lat is None or lon is None:
            # Try GeoClue for location, or skip weather
            self._try_geoclue_location()
            return

        def _do_fetch() -> Optional[dict]:
            """Run the HTTP request in a thread."""
            try:
                api_url = self._config.get(
                    'Weather', 'api_url',
                    'https://api.open-meteo.com/v1/forecast',
                )
                url = (
                    f'{api_url}?latitude={lat}&longitude={lon}'
                    f'&current=temperature_2m,weather_code'
                    f'&timezone=auto'
                )
                req = Request(url, headers={'User-Agent': 'BeetaOS/1.0'})
                with urlopen(req, timeout=10) as resp:
                    return json.loads(resp.read().decode('utf-8'))
            except (URLError, json.JSONDecodeError, OSError):
                return None

        def _on_result(data: Optional[dict]) -> None:
            """Process weather result on the main thread."""
            if data is None:
                return

            current = data.get('current', {})
            temp = current.get('temperature_2m')
            weather_code = current.get('weather_code', 0)

            if temp is not None:
                self._temperature = float(temp)

            # Map WMO weather codes to conditions
            self._weather_condition = self._wmo_to_condition(weather_code)
            self.update_theme()

        # Run fetch in thread pool
        import threading
        def _thread_worker():
            result = _do_fetch()
            GLib.idle_add(lambda: _on_result(result) or False)

        thread = threading.Thread(target=_thread_worker, daemon=True)
        thread.start()

    def _try_geoclue_location(self) -> None:
        """Attempt to get location from GeoClue D-Bus service."""
        try:
            from gi.repository import Gio
            bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
            proxy = Gio.DBusProxy.new_sync(
                bus, Gio.DBusProxyFlags.NONE, None,
                'org.freedesktop.GeoClue2',
                '/org/freedesktop/GeoClue2/Manager',
                'org.freedesktop.GeoClue2.Manager',
                None,
            )
            # GeoClue requires a client — for now just log and skip
            # Full GeoClue integration can be added later
        except Exception:
            pass  # GeoClue not available; weather will use defaults

    @staticmethod
    def _wmo_to_condition(code: int) -> str:
        """Convert WMO weather code to Beeta condition string.

        Args:
            code: WMO weather interpretation code.

        Returns:
            One of 'clear', 'cloudy', 'rainy', 'snowy'.
        """
        if code <= 1:
            return 'clear'
        elif code <= 3:
            return 'cloudy'
        elif code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82):
            return 'rainy'
        elif code in (71, 73, 75, 77, 85, 86):
            return 'snowy'
        elif code in (45, 48):
            return 'cloudy'  # fog
        elif code >= 95:
            return 'rainy'   # thunderstorm
        else:
            return 'clear'

    # ── Internal: Periodic Callbacks ─────────────────────────────

    def _periodic_update(self) -> bool:
        """Called every 60 seconds to update theme for time changes."""
        self.update_theme()
        return GLib.SOURCE_CONTINUE

    def _periodic_weather_fetch(self) -> bool:
        """Called every 30 minutes to refresh weather data."""
        self._fetch_weather_async()
        return GLib.SOURCE_CONTINUE
