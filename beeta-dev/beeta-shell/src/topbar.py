# -*- coding: utf-8 -*-
# Beeta Desktop Environment
# Copyright (C) 2023-2026 Beeta Technologies Inc.
# Licensed under GNU General Public License v3.0

"""Top bar panel for the Beeta Desktop Shell.

The top bar is a Wayland layer-shell surface anchored to the top
edge of the screen. It contains three sections:

    ┌──────────────────────────────────────────────────────┐
    │  ● ○ ○        10:42 · Tuesday              🔋 92%  │
    └──────────────────────────────────────────────────────┘
    Left:   Workspace Switcher (dots with pill-morph animation)
    Center: Live Center (dynamic status hub)
    Right:  System Tray (battery, Wi-Fi, BT, volume)

In Focus State, workspace dots fade out and only the Live Center
and battery indicator remain visible.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gtk4LayerShell', '1.0')
from gi.repository import Gtk, Gtk4LayerShell, Gdk

if TYPE_CHECKING:
    from .config import BeetaConfig
    from .adaptive_motion import AdaptiveMotion
    from .adaptive_nature import AdaptiveNature
    from .states import StateManager

from .workspace import WorkspaceSwitcher
from .live_center import LiveCenter
from .system_tray import SystemTray


# Top bar height in pixels
_BAR_HEIGHT: int = 36


class TopBar:
    """Top bar panel using Wayland layer-shell.

    Creates a transparent window anchored to the top of the screen
    with exclusive zone reservation. Contains the workspace switcher,
    Live Center, and system tray.

    The top bar adapts to Desktop/Focus state transitions by hiding
    workspace dots and non-essential tray icons in Focus State.

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

        # Create the layer-shell window
        self._window = Gtk.Window(application=app)
        self._window.set_title('Beeta Top Bar')
        self._window.set_decorated(False)

        # Initialize layer shell
        Gtk4LayerShell.init_for_window(self._window)
        Gtk4LayerShell.set_layer(
            self._window, Gtk4LayerShell.Layer.TOP
        )
        Gtk4LayerShell.set_namespace(self._window, 'beeta-topbar')

        # Anchor to top, left, right edges
        Gtk4LayerShell.set_anchor(
            self._window, Gtk4LayerShell.Edge.TOP, True
        )
        Gtk4LayerShell.set_anchor(
            self._window, Gtk4LayerShell.Edge.LEFT, True
        )
        Gtk4LayerShell.set_anchor(
            self._window, Gtk4LayerShell.Edge.RIGHT, True
        )

        # Reserve space for the bar
        Gtk4LayerShell.set_exclusive_zone(self._window, _BAR_HEIGHT)

        # Force window to stretch to full width
        self._window.set_default_size(9999, _BAR_HEIGHT)

        # Build content
        self._build_content()

        # Connect state manager
        self._state_mgr.connect('state-changed', self._on_state_changed)

        # Connect battery changes to engines
        self._system_tray.connect(
            'battery-changed', self._on_battery_changed
        )

        # Show the window
        self._window.present()

    @property
    def window(self) -> Gtk.Window:
        """The underlying Gtk.Window."""
        return self._window

    @property
    def system_tray(self) -> SystemTray:
        """The system tray widget (for external battery signal access)."""
        return self._system_tray

    @property
    def live_center(self) -> LiveCenter:
        """The Live Center widget (for external activity management)."""
        return self._live_center

    @property
    def workspace_switcher(self) -> WorkspaceSwitcher:
        """The workspace switcher widget."""
        return self._workspace_switcher

    def set_focus_mode(self, is_focus: bool) -> None:
        """Transition between Desktop and Focus state visuals.

        Args:
            is_focus: True for Focus State, False for Desktop State.
        """
        if is_focus:
            self._container.add_css_class('focus-mode')
            if not self._state_mgr.is_laptop:
                self._container.add_css_class('desktop-mode')
        else:
            self._container.remove_css_class('focus-mode')
            self._container.remove_css_class('desktop-mode')

        # Animate workspace dots
        self._workspace_switcher.set_visible_animated(not is_focus)

        # Adjust system tray
        self._system_tray.set_focus_mode(
            is_focus, self._state_mgr.is_laptop
        )

    # ── Internal ─────────────────────────────────────────────────

    def _build_content(self) -> None:
        """Build the three-section top bar layout."""
        # Main container
        self._container = Gtk.CenterBox()
        self._container.set_hexpand(True)
        self._container.set_halign(Gtk.Align.FILL)
        # Background intentionally transparent to allow floating elements
        self._container.add_css_class('topbar')

        # Apply motion tier CSS class
        self._container.add_css_class(self._motion.css_class)
        self._motion.connect(
            'tier-changed', self._on_motion_tier_changed
        )

        # ── Left: Workspace Switcher ──
        self._workspace_switcher = WorkspaceSwitcher(
            self._config, self._motion
        )
        left_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            halign=Gtk.Align.START,
            valign=Gtk.Align.CENTER,
            margin_start=12,
        )
        left_box.add_css_class('topbar-left')
        left_box.append(self._workspace_switcher)
        self._container.set_start_widget(left_box)

        # ── Center: Live Center ──
        self._live_center = LiveCenter(self._motion)
        center_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
        )
        center_box.add_css_class('topbar-center')
        center_box.append(self._live_center)
        self._container.set_center_widget(center_box)

        # ── Right: System Tray ──
        self._system_tray = SystemTray(
            self._config, self._motion
        )
        right_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            halign=Gtk.Align.END,
            valign=Gtk.Align.CENTER,
            margin_end=12,
        )
        right_box.add_css_class('topbar-right')
        right_box.append(self._system_tray)
        self._container.set_end_widget(right_box)

        self._window.set_child(self._container)

    def _on_state_changed(
        self, state_mgr: StateManager, state: str
    ) -> None:
        """React to Desktop/Focus state transitions."""
        self.set_focus_mode(state == 'focus')

    def _on_battery_changed(
        self,
        tray: SystemTray,
        level: int,
        charging: bool,
        rate: float,
    ) -> None:
        """Forward battery state to Adaptive engines."""
        self._nature.set_battery(level, charging)
        self._motion.check_battery(level, charging)

    def _on_motion_tier_changed(
        self, motion: AdaptiveMotion, tier: str
    ) -> None:
        """Update CSS motion class when tier changes."""
        for cls in ('motion-saver', 'motion-balanced', 'motion-performance'):
            self._container.remove_css_class(cls)
        self._container.add_css_class(motion.css_class)

    def cleanup(self) -> None:
        """Clean up all child components. Call on shutdown."""
        self._workspace_switcher.cleanup()
        self._live_center.cleanup()
        self._system_tray.cleanup()
