# -*- coding: utf-8 -*-
# Beeta Desktop Environment
# Copyright (C) 2023-2026 Beeta Technologies Inc.
# Licensed under GNU General Public License v3.0

"""Main entry point for the Beeta Desktop Shell.

Initializes the GTK4 application, loads the glass CSS theme, sets up
Wayland layer-shell panels (top bar + bottom bar), starts the Adaptive
Nature™ and Adaptive Motion™ engines, and handles global keyboard
shortcuts.

Usage:
    python3 -m beeta_shell.main
    # or via the launcher script:
    beeta-shell
"""

from __future__ import annotations

import os
import signal
import sys
from pathlib import Path
from typing import Optional

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gtk4LayerShell', '1.0')
from gi.repository import Gtk, Gtk4LayerShell, Gdk, GLib, Gio

from .config import BeetaConfig
from .states import StateManager
from .adaptive_nature import AdaptiveNature
from .adaptive_motion import AdaptiveMotion
from .topbar import TopBar
from .bottombar import BottomBar


# Application metadata
_APP_ID = 'com.beetaos.shell'
_APP_NAME = 'Beeta Shell'
_APP_VERSION = '0.1.0'


def _find_data_dir() -> Path:
    """Locate the beeta-shell data directory.

    Search order:
        1. Source tree (for development): ./data/
        2. XDG data home: ~/.local/share/beeta-shell/
        3. System install: /usr/share/beeta-shell/

    Returns:
        Path to the data directory containing style.css and beeta.conf.
    """
    # Development: relative to this source file
    src_dir = Path(__file__).parent.parent / 'data'
    if src_dir.exists() and (src_dir / 'style.css').exists():
        return src_dir

    # XDG data home
    xdg_data = os.environ.get('XDG_DATA_HOME', '')
    if not xdg_data:
        xdg_data = str(Path.home() / '.local' / 'share')
    local_data = Path(xdg_data) / 'beeta-shell'
    if local_data.exists() and (local_data / 'style.css').exists():
        return local_data

    # System install
    system_data = Path('/usr/share/beeta-shell')
    if system_data.exists():
        return system_data

    # Fallback to source dir even if it doesn't exist
    return src_dir


class BeetaShell(Gtk.Application):
    """Main Beeta Desktop Shell application.

    Orchestrates all shell components: top bar, bottom bar, adaptive
    engines, and global keyboard shortcuts. This is the central object
    that all components reference via the `app` parameter.

    Attributes:
        config: BeetaConfig instance for reading/writing settings.
        state_manager: StateManager for Desktop/Focus state transitions.
        adaptive_nature: AdaptiveNature™ context-aware theming engine.
        adaptive_motion: AdaptiveMotion™ performance-aware animation engine.
        topbar: TopBar panel instance.
        bottombar: BottomBar panel instance.
    """

    def __init__(self) -> None:
        super().__init__(
            application_id=_APP_ID,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )

        self.config: Optional[BeetaConfig] = None
        self.state_manager: Optional[StateManager] = None
        self.adaptive_nature: Optional[AdaptiveNature] = None
        self.adaptive_motion: Optional[AdaptiveMotion] = None
        self.topbar: Optional[TopBar] = None
        self.bottombar: Optional[BottomBar] = None

        self._data_dir: Optional[Path] = None

    def do_startup(self) -> None:
        """Application startup — load config, CSS theme, init engines."""
        Gtk.Application.do_startup(self)

        # Find data directory
        self._data_dir = _find_data_dir()

        # Initialize configuration
        self.config = BeetaConfig()

        # Initialize state manager
        self.state_manager = StateManager(self.config)

        # Initialize adaptive engines
        self.adaptive_nature = AdaptiveNature(self.config)
        self.adaptive_motion = AdaptiveMotion(self.config)

        # Load CSS theme
        self._load_css_theme()

        # Start Adaptive Nature (applies dynamic CSS on top of base)
        display = Gdk.Display.get_default()
        if display:
            self.adaptive_nature.apply_css(display)
            self.adaptive_nature.start()

        # Set up global keyboard shortcut actions
        self._setup_actions()

    def do_activate(self) -> None:
        """Application activation — create and show the shell panels."""
        # Create top bar
        self.topbar = TopBar(
            app=self,
            config=self.config,
            adaptive_motion=self.adaptive_motion,
            adaptive_nature=self.adaptive_nature,
            state_manager=self.state_manager,
        )

        # Create bottom bar
        self.bottombar = BottomBar(
            app=self,
            config=self.config,
            adaptive_motion=self.adaptive_motion,
            adaptive_nature=self.adaptive_nature,
            state_manager=self.state_manager,
        )

        # Wire up cross-component connections
        self._connect_components()

        print(f'[{_APP_NAME}] v{_APP_VERSION} — Desktop environment started')
        print(f'[{_APP_NAME}] Data directory: {self._data_dir}')
        print(f'[{_APP_NAME}] Performance mode: {self.config.performance_mode}')
        print(f'[{_APP_NAME}] Adaptive mode: {self.config.adaptive_mode}')
        print(f'[{_APP_NAME}] Laptop: {self.config.is_laptop}')

    def do_shutdown(self) -> None:
        """Application shutdown — clean up all components."""
        print(f'[{_APP_NAME}] Shutting down...')

        if self.topbar:
            self.topbar.cleanup()
        if self.bottombar:
            self.bottombar.cleanup()
        if self.state_manager:
            self.state_manager.cleanup()
        if self.adaptive_nature:
            self.adaptive_nature.stop()

        Gtk.Application.do_shutdown(self)

    # ── Internal: CSS Loading ────────────────────────────────────

    def _load_css_theme(self) -> None:
        """Load the base glass CSS theme from the data directory."""
        css_path = self._data_dir / 'style.css'

        if not css_path.exists():
            print(
                f'[{_APP_NAME}] Warning: CSS theme not found at {css_path}'
            )
            return

        css_provider = Gtk.CssProvider()

        try:
            css_provider.load_from_path(str(css_path))
        except GLib.Error as e:
            print(f'[{_APP_NAME}] Warning: Failed to load CSS: {e.message}')
            return

        display = Gdk.Display.get_default()
        if display:
            Gtk.StyleContext.add_provider_for_display(
                display,
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )

        print(f'[{_APP_NAME}] Loaded CSS theme from {css_path}')

    # ── Internal: Actions & Keyboard Shortcuts ───────────────────

    def _setup_actions(self) -> None:
        """Set up application-wide keyboard shortcut actions."""
        # Super key → Toggle launcher
        action_launcher = Gio.SimpleAction.new('toggle-launcher', None)
        action_launcher.connect('activate', self._on_toggle_launcher)
        self.add_action(action_launcher)
        self.set_accels_for_action('app.toggle-launcher', ['<Super_L>'])

        # Alt+Space → Toggle launcher (alternative)
        action_launcher_alt = Gio.SimpleAction.new(
            'toggle-launcher-alt', None
        )
        action_launcher_alt.connect('activate', self._on_toggle_launcher)
        self.add_action(action_launcher_alt)
        self.set_accels_for_action(
            'app.toggle-launcher-alt', ['<Alt>space']
        )

        # Escape → Close overlays / exit Focus State
        action_escape = Gio.SimpleAction.new('escape', None)
        action_escape.connect('activate', self._on_escape)
        self.add_action(action_escape)
        self.set_accels_for_action('app.escape', ['Escape'])

        # Ctrl+Alt+D → Toggle Desktop/Focus State (debug)
        action_toggle_state = Gio.SimpleAction.new('toggle-state', None)
        action_toggle_state.connect('activate', self._on_toggle_state)
        self.add_action(action_toggle_state)
        self.set_accels_for_action(
            'app.toggle-state', ['<Ctrl><Alt>d']
        )

    def _on_toggle_launcher(
        self, action: Gio.SimpleAction, parameter: Optional[GLib.Variant]
    ) -> None:
        """Handle Super / Alt+Space — toggle the launcher."""
        if self.bottombar:
            self.bottombar.launcher.toggle()

            # In Focus State, also reveal the bottom bar
            if (
                self.state_manager
                and self.state_manager.current_state == 'focus'
            ):
                self.state_manager.request_bar_reveal()

    def _on_escape(
        self, action: Gio.SimpleAction, parameter: Optional[GLib.Variant]
    ) -> None:
        """Handle Escape — close launcher or exit Focus State."""
        # First, close any open launcher
        if self.bottombar and self.bottombar.launcher.is_visible:
            self.bottombar.launcher.hide()
            return

        # Close Live Center if expanded
        if self.topbar and self.topbar.live_center._is_expanded:
            self.topbar.live_center.set_expanded(False)
            return

        # Exit Focus State
        if (
            self.state_manager
            and self.state_manager.current_state == 'focus'
        ):
            self.state_manager.set_state('desktop')

    def _on_toggle_state(
        self, action: Gio.SimpleAction, parameter: Optional[GLib.Variant]
    ) -> None:
        """Handle Ctrl+Alt+D — toggle Desktop/Focus state (debug)."""
        if self.state_manager:
            self.state_manager.toggle_state()

    # ── Internal: Cross-component Wiring ─────────────────────────

    def _connect_components(self) -> None:
        """Wire up signals between components that need each other."""
        if not self.config or not self.adaptive_motion:
            return

        # Config changes → Adaptive Motion mode updates
        self.config.connect(
            'config-changed', self._on_config_changed
        )

    def _on_config_changed(
        self, config: BeetaConfig, section: str, key: str
    ) -> None:
        """React to configuration changes for cross-component effects."""
        if section == 'Desktop' and key == 'adaptive_nature_mode':
            # Adaptive Nature mode changed → re-apply theme
            if self.adaptive_nature:
                self.adaptive_nature.update_theme()

        elif section == 'Dock' and key == 'pinned_apps':
            # Pinned apps changed → rebuild dock
            if self.bottombar:
                self.bottombar.dock.refresh_apps()


def main() -> int:
    """Entry point for the Beeta Desktop Shell.

    Returns:
        Exit code (0 for success).
    """
    # Handle SIGINT gracefully
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    # Set environment for Wayland
    os.environ.setdefault('XDG_CURRENT_DESKTOP', 'Beeta')
    os.environ.setdefault('XDG_SESSION_TYPE', 'wayland')
    os.environ.setdefault('GDK_BACKEND', 'wayland')

    app = BeetaShell()
    return app.run(sys.argv)


if __name__ == '__main__':
    sys.exit(main())
