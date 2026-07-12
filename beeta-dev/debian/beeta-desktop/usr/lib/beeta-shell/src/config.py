# -*- coding: utf-8 -*-
# Beeta Desktop Environment
# Copyright (C) 2023-2026 Beeta Technologies Inc.
# Licensed under GNU General Public License v3.0

"""Configuration manager for the Beeta Desktop Shell.

Reads configuration from XDG-compliant paths with fallback to system defaults.
Supports live reload via file monitoring and provides typed accessors for
all shell settings including dock pinned apps, workspace count, and
Adaptive Nature / Adaptive Motion preferences.

Config search order:
    1. ~/.config/beeta/beeta.conf  (user overrides)
    2. /etc/beeta/beeta.conf       (system defaults)
    3. Built-in defaults           (hardcoded fallbacks)
"""

from __future__ import annotations

import configparser
import os
from pathlib import Path
from typing import Optional

from gi.repository import GLib, Gio, GObject


# Default configuration values
_DEFAULTS: dict[str, dict[str, str]] = {
    'Desktop': {
        'workspaces': '3',
        'adaptive_nature_mode': 'adaptive',
        'performance_mode': 'balanced',
        'is_laptop': 'auto',
    },
    'Dock': {
        'pinned_apps': 'org.gnome.Nautilus;org.gnome.Terminal;firefox;org.gnome.Calculator;gnome-control-center',
        'icon_size': '48',
        'hover_magnification': '1.15',
    },
    'LiveCenter': {
        'show_media': 'true',
        'show_downloads': 'true',
        'show_timers': 'true',
        'show_recording': 'true',
        'show_sharing': 'true',
    },
    'Charging': {
        'turbo_charge_min_watts': '45',
        'fast_charge_min_watts': '15',
    },
    'Glass': {
        'opacity': '0.75',
        'blur_radius': '20',
        'border_opacity': '0.12',
        'shadow_opacity': '0.4',
    },
    'Weather': {
        'api_url': 'https://api.open-meteo.com/v1/forecast',
        'update_interval_minutes': '30',
        'latitude': '',
        'longitude': '',
    },
}

# System-wide config path
_SYSTEM_CONFIG = Path('/etc/beeta/beeta.conf')


def _get_user_config_path() -> Path:
    """Return the XDG-compliant user configuration file path."""
    xdg_config = os.environ.get('XDG_CONFIG_HOME', '')
    if not xdg_config:
        xdg_config = str(Path.home() / '.config')
    return Path(xdg_config) / 'beeta' / 'beeta.conf'


class BeetaConfig(GObject.Object):
    """Configuration manager for the Beeta Desktop Shell.

    Provides typed accessors for all configuration values with automatic
    fallback to defaults. Supports file monitoring for live reload and
    emits 'config-changed' when values are updated.

    Signals:
        config-changed(section: str, key: str):
            Emitted when a configuration value changes.

    Example:
        >>> config = BeetaConfig()
        >>> config.workspaces
        3
        >>> config.pinned_apps
        ['org.gnome.Nautilus', 'org.gnome.Terminal', ...]
        >>> config.set('Desktop', 'workspaces', '4')
    """

    __gsignals__ = {
        'config-changed': (
            GObject.SignalFlags.RUN_FIRST, None, (str, str)
        ),
    }

    def __init__(self) -> None:
        super().__init__()
        self._parser = configparser.ConfigParser()
        self._user_config_path = _get_user_config_path()
        self._monitor: Optional[Gio.FileMonitor] = None
        self._reload_source_id: int = 0

        # Load defaults first
        self._parser.read_dict(_DEFAULTS)

        # Load system config, then user config (user overrides system)
        config_files: list[str] = []
        if _SYSTEM_CONFIG.exists():
            config_files.append(str(_SYSTEM_CONFIG))
        if self._user_config_path.exists():
            config_files.append(str(self._user_config_path))
        if config_files:
            self._parser.read(config_files)

        # Start file monitoring for live reload
        self._setup_file_monitor()

    def _setup_file_monitor(self) -> None:
        """Set up inotify-based monitoring on the user config file."""
        config_dir = self._user_config_path.parent
        if not config_dir.exists():
            try:
                config_dir.mkdir(parents=True, exist_ok=True)
            except OSError:
                return

        gfile = Gio.File.new_for_path(str(self._user_config_path))
        try:
            self._monitor = gfile.monitor_file(
                Gio.FileMonitorFlags.NONE, None
            )
            self._monitor.connect('changed', self._on_config_file_changed)
        except GLib.Error:
            pass  # File monitoring not available; graceful degradation

    def _on_config_file_changed(
        self,
        monitor: Gio.FileMonitor,
        file: Gio.File,
        other_file: Optional[Gio.File],
        event_type: Gio.FileMonitorEvent,
    ) -> None:
        """Handle config file changes with debouncing."""
        if event_type not in (
            Gio.FileMonitorEvent.CHANGED,
            Gio.FileMonitorEvent.CREATED,
        ):
            return

        # Debounce: wait 500ms before reloading to coalesce rapid writes
        if self._reload_source_id:
            GLib.source_remove(self._reload_source_id)
        self._reload_source_id = GLib.timeout_add(500, self._reload_config)

    def _reload_config(self) -> bool:
        """Reload configuration from disk and emit change signals."""
        self._reload_source_id = 0

        old_values: dict[str, dict[str, str]] = {}
        for section in self._parser.sections():
            old_values[section] = dict(self._parser[section])

        # Re-read from defaults + files
        self._parser = configparser.ConfigParser()
        self._parser.read_dict(_DEFAULTS)
        config_files: list[str] = []
        if _SYSTEM_CONFIG.exists():
            config_files.append(str(_SYSTEM_CONFIG))
        if self._user_config_path.exists():
            config_files.append(str(self._user_config_path))
        if config_files:
            self._parser.read(config_files)

        # Detect and emit changes
        for section in self._parser.sections():
            for key, value in self._parser[section].items():
                old_val = old_values.get(section, {}).get(key)
                if old_val != value:
                    self.emit('config-changed', section, key)

        return GLib.SOURCE_REMOVE

    # ── Typed Accessors ──────────────────────────────────────────────

    def get(self, section: str, key: str, fallback: str = '') -> str:
        """Get a string configuration value.

        Args:
            section: Configuration section name.
            key: Configuration key within the section.
            fallback: Default value if key is not found.

        Returns:
            The configuration value as a string.
        """
        return self._parser.get(section, key, fallback=fallback)

    def get_int(self, section: str, key: str, fallback: int = 0) -> int:
        """Get an integer configuration value.

        Args:
            section: Configuration section name.
            key: Configuration key within the section.
            fallback: Default value if key is not found or invalid.

        Returns:
            The configuration value as an integer.
        """
        try:
            return self._parser.getint(section, key, fallback=fallback)
        except (ValueError, configparser.Error):
            return fallback

    def get_float(
        self, section: str, key: str, fallback: float = 0.0
    ) -> float:
        """Get a float configuration value.

        Args:
            section: Configuration section name.
            key: Configuration key within the section.
            fallback: Default value if key is not found or invalid.

        Returns:
            The configuration value as a float.
        """
        try:
            return self._parser.getfloat(section, key, fallback=fallback)
        except (ValueError, configparser.Error):
            return fallback

    def get_bool(
        self, section: str, key: str, fallback: bool = False
    ) -> bool:
        """Get a boolean configuration value.

        Args:
            section: Configuration section name.
            key: Configuration key within the section.
            fallback: Default value if key is not found or invalid.

        Returns:
            The configuration value as a boolean.
        """
        try:
            return self._parser.getboolean(section, key, fallback=fallback)
        except (ValueError, configparser.Error):
            return fallback

    def set(self, section: str, key: str, value: str) -> None:
        """Set a configuration value and persist to user config file.

        Args:
            section: Configuration section name.
            key: Configuration key within the section.
            value: The value to set.
        """
        if not self._parser.has_section(section):
            self._parser.add_section(section)

        old_value = self._parser.get(section, key, fallback=None)
        self._parser.set(section, key, value)

        if old_value != value:
            self._save_user_config()
            self.emit('config-changed', section, key)

    def _save_user_config(self) -> None:
        """Persist current configuration to the user config file."""
        config_dir = self._user_config_path.parent
        try:
            config_dir.mkdir(parents=True, exist_ok=True)
            with open(self._user_config_path, 'w', encoding='utf-8') as f:
                self._parser.write(f)
        except OSError as e:
            print(f'[BeetaConfig] Warning: Could not save config: {e}')

    # ── Convenience Properties ───────────────────────────────────────

    @property
    def pinned_apps(self) -> list[str]:
        """List of pinned application .desktop file IDs."""
        raw = self.get('Dock', 'pinned_apps', '')
        return [app.strip() for app in raw.split(';') if app.strip()]

    @property
    def workspaces(self) -> int:
        """Number of virtual workspaces."""
        return max(1, min(10, self.get_int('Desktop', 'workspaces', 3)))

    @property
    def adaptive_mode(self) -> str:
        """Adaptive Nature mode: 'static', 'adaptive', or 'expressive'."""
        mode = self.get('Desktop', 'adaptive_nature_mode', 'adaptive')
        if mode not in ('static', 'adaptive', 'expressive'):
            return 'adaptive'
        return mode

    @property
    def performance_mode(self) -> str:
        """Performance mode: 'power-saver', 'balanced', or 'performance'."""
        mode = self.get('Desktop', 'performance_mode', 'balanced')
        if mode not in ('power-saver', 'balanced', 'performance'):
            return 'balanced'
        return mode

    @property
    def is_laptop(self) -> bool:
        """Whether the device is a laptop (auto-detected or manual)."""
        val = self.get('Desktop', 'is_laptop', 'auto')
        if val == 'auto':
            return self._detect_laptop()
        return val.lower() in ('true', 'yes', '1')

    @property
    def icon_size(self) -> int:
        """Dock icon size in pixels."""
        return max(24, min(96, self.get_int('Dock', 'icon_size', 48)))

    @property
    def hover_magnification(self) -> float:
        """Dock icon hover magnification factor."""
        return max(1.0, min(1.5, self.get_float(
            'Dock', 'hover_magnification', 1.15
        )))

    @property
    def glass_opacity(self) -> float:
        """Glass panel background opacity (0.0 - 1.0)."""
        return max(0.3, min(1.0, self.get_float('Glass', 'opacity', 0.75)))

    @property
    def turbo_charge_min_watts(self) -> float:
        """Minimum wattage to display 'Beeta Turbo Charge' label."""
        return self.get_float('Charging', 'turbo_charge_min_watts', 45.0)

    @property
    def fast_charge_min_watts(self) -> float:
        """Minimum wattage to display 'Fast Charging' label."""
        return self.get_float('Charging', 'fast_charge_min_watts', 15.0)

    @property
    def weather_latitude(self) -> Optional[float]:
        """Weather location latitude, or None if not set."""
        val = self.get('Weather', 'latitude', '')
        if not val:
            return None
        try:
            return float(val)
        except ValueError:
            return None

    @property
    def weather_longitude(self) -> Optional[float]:
        """Weather location longitude, or None if not set."""
        val = self.get('Weather', 'longitude', '')
        if not val:
            return None
        try:
            return float(val)
        except ValueError:
            return None

    @staticmethod
    def _detect_laptop() -> bool:
        """Auto-detect whether running on a laptop by checking for battery."""
        battery_paths = [
            Path('/sys/class/power_supply/BAT0'),
            Path('/sys/class/power_supply/BAT1'),
            Path('/sys/class/power_supply/BATT'),
        ]
        return any(p.exists() for p in battery_paths)
