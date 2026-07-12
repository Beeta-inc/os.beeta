# -*- coding: utf-8 -*-
# Beeta Desktop Environment
# Copyright (C) 2023-2026 Beeta Technologies Inc.
# Licensed under GNU General Public License v3.0

"""Pinned apps dock for the Beeta Shell bottom bar.

A row of application icons with hover magnification and active
app indicators. Icons are loaded from the system icon theme
via .desktop file entries.

Features:
    - Pinned apps from user configuration
    - Subtle hover magnification (1.15× scale, macOS-like but gentler)
    - Active app indicator: glowing dot below running apps
    - Tooltips on hover showing app name
    - Click to launch (or focus if already running)
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING, Optional

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gio, GLib, GObject, Gdk

if TYPE_CHECKING:
    from .config import BeetaConfig
    from .adaptive_motion import AdaptiveMotion


class Dock(Gtk.Box):
    """Pinned application dock with hover effects and indicators.

    Reads pinned app list from config and creates icon buttons for each.
    Active app detection checks running processes to show indicator dots.

    Args:
        config: Beeta configuration instance.
        adaptive_motion: Adaptive Motion engine for animation control.
    """

    __gsignals__ = {
        'app-launched': (
            GObject.SignalFlags.RUN_FIRST, None, (str,)
        ),
    }

    # Poll interval for running apps detection (seconds)
    _POLL_INTERVAL_S: int = 3

    def __init__(
        self,
        config: BeetaConfig,
        adaptive_motion: AdaptiveMotion,
    ) -> None:
        super().__init__(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=0,
            valign=Gtk.Align.CENTER,
            halign=Gtk.Align.CENTER,
        )
        self.add_css_class('dock')

        self._config = config
        self._motion = adaptive_motion
        self._items: list[_DockItem] = []
        self._running_apps: set[str] = set()
        self._poll_source: int = 0

        # Build dock items from config
        self._build_dock()

        # Start running-app detection
        self._update_running_apps()
        self._poll_source = GLib.timeout_add_seconds(
            self._POLL_INTERVAL_S, self._poll_running_apps
        )

    def refresh_apps(self) -> None:
        """Rebuild the dock from current configuration."""
        # Clear existing items
        for item in self._items:
            self.remove(item.container)
        self._items.clear()
        self._build_dock()

    # ── Internal: Build UI ───────────────────────────────────────

    def _build_dock(self) -> None:
        """Create dock items for each pinned app."""
        pinned = self._config.pinned_apps
        icon_theme = Gtk.IconTheme.get_for_display(
            Gdk.Display.get_default()
        )

        for app_id in pinned:
            item = self._create_dock_item(app_id, icon_theme)
            if item:
                self._items.append(item)
                self.append(item.container)

    def _create_dock_item(
        self, app_id: str, icon_theme: Gtk.IconTheme
    ) -> Optional[_DockItem]:
        """Create a single dock item from a .desktop file ID.

        Args:
            app_id: Application .desktop file ID (e.g., 'firefox').
            icon_theme: GTK icon theme for icon lookup.

        Returns:
            A _DockItem or None if the app couldn't be found.
        """
        # Try to load the .desktop file
        desktop_id = app_id
        if not desktop_id.endswith('.desktop'):
            desktop_id = app_id + '.desktop'

        app_info: Optional[Gio.DesktopAppInfo] = None
        try:
            app_info = Gio.DesktopAppInfo.new(desktop_id)
        except Exception:
            pass

        if app_info is None:
            # Try with common prefixes
            for prefix in ('org.gnome.', 'org.kde.', 'com.', ''):
                try:
                    app_info = Gio.DesktopAppInfo.new(
                        f'{prefix}{app_id}.desktop'
                    )
                    if app_info:
                        break
                except Exception:
                    continue

        if app_info is None:
            return None

        app_name = app_info.get_display_name() or app_id
        app_icon = app_info.get_icon()
        executable = app_info.get_executable() or ''

        # Create container (button + indicator)
        container = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=0,
            valign=Gtk.Align.CENTER,
            halign=Gtk.Align.CENTER,
        )

        # Icon button
        button = Gtk.Button()
        button.add_css_class('dock-item')
        button.set_tooltip_text(app_name)

        if app_icon:
            image = Gtk.Image.new_from_gicon(app_icon)
            image.set_pixel_size(self._config.icon_size)
            button.set_child(image)
        else:
            # Fallback: use text label
            label = Gtk.Label(label=app_name[:3])
            button.set_child(label)

        container.append(button)

        # Active indicator dot
        indicator = Gtk.Box()
        indicator.add_css_class('dock-indicator')
        indicator.set_halign(Gtk.Align.CENTER)
        container.append(indicator)

        # Click to launch/focus
        button.connect(
            'clicked', self._on_app_clicked, app_info, app_id
        )

        item = _DockItem(
            app_id=app_id,
            app_name=app_name,
            app_info=app_info,
            executable=executable,
            container=container,
            button=button,
            indicator=indicator,
        )

        return item

    # ── Internal: Running App Detection ──────────────────────────

    def _update_running_apps(self) -> None:
        """Detect which pinned apps are currently running."""
        try:
            result = subprocess.run(
                ['ps', '-eo', 'comm'],
                capture_output=True, text=True, timeout=2,
            )
            if result.returncode == 0:
                running = set(result.stdout.strip().split('\n'))
                self._running_apps = running
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pass

        # Update indicator dots
        for item in self._items:
            exe_name = item.executable.split('/')[-1] if item.executable else ''
            is_running = exe_name in self._running_apps

            if is_running:
                item.indicator.add_css_class('active')
            else:
                item.indicator.remove_css_class('active')

    def _poll_running_apps(self) -> bool:
        """Periodic poll for running app detection."""
        if not self._motion.is_component_paused('dock'):
            self._update_running_apps()
        return GLib.SOURCE_CONTINUE

    # ── Internal: Event Handlers ─────────────────────────────────

    def _on_app_clicked(
        self,
        button: Gtk.Button,
        app_info: Gio.DesktopAppInfo,
        app_id: str,
    ) -> None:
        """Handle click on a dock icon — launch or focus the app.

        Args:
            button: The clicked button.
            app_info: The app's desktop info.
            app_id: The app's ID string.
        """
        try:
            context = Gdk.Display.get_default().get_app_launch_context()
            app_info.launch([], context)
            self.emit('app-launched', app_id)
        except Exception as e:
            print(f'[Dock] Failed to launch {app_id}: {e}')

    def cleanup(self) -> None:
        """Cancel polling. Call on shutdown."""
        if self._poll_source:
            GLib.source_remove(self._poll_source)
            self._poll_source = 0


class _DockItem:
    """Data class for a single dock item."""

    __slots__ = (
        'app_id', 'app_name', 'app_info', 'executable',
        'container', 'button', 'indicator',
    )

    def __init__(
        self,
        app_id: str,
        app_name: str,
        app_info: Gio.DesktopAppInfo,
        executable: str,
        container: Gtk.Box,
        button: Gtk.Button,
        indicator: Gtk.Box,
    ) -> None:
        self.app_id = app_id
        self.app_name = app_name
        self.app_info = app_info
        self.executable = executable
        self.container = container
        self.button = button
        self.indicator = indicator
