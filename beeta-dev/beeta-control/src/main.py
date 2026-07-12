# -*- coding: utf-8 -*-
# Beeta Desktop Environment
# Copyright (C) 2023-2026 Beeta Technologies Inc.
# Licensed under GNU General Public License v3.0

"""Main entry point for the Beeta Control Panel application."""

from __future__ import annotations

import os
import signal
import sys
from pathlib import Path
from typing import Optional

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, GLib, Gio

# Add beeta-shell to path for shared config
_src_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_src_dir / 'beeta-shell'))
from src.config import BeetaConfig

from .window import ControlWindow

_APP_ID = 'com.beetaos.control'


def _find_data_dir() -> Path:
    """Locate the beeta-control data directory."""
    src_dir = Path(__file__).parent.parent / 'data'
    if src_dir.exists() and (src_dir / 'style.css').exists():
        return src_dir
    local_data = Path(
        os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local' / 'share'))
    ) / 'beeta-control'
    if local_data.exists():
        return local_data
    system_data = Path('/usr/share/beeta-control')
    if system_data.exists():
        return system_data
    return src_dir


class BeetaControl(Gtk.Application):
    """Beeta Control Panel application.

    A visually stunning settings application that uses the same
    glass design language as the Beeta Desktop Shell.
    """

    def __init__(self) -> None:
        super().__init__(
            application_id=_APP_ID,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        self._config: Optional[BeetaConfig] = None
        self._data_dir: Optional[Path] = None

    def do_startup(self) -> None:
        """Load CSS theme and configuration."""
        Gtk.Application.do_startup(self)

        self._data_dir = _find_data_dir()
        self._config = BeetaConfig()

        # Load CSS
        css_path = self._data_dir / 'style.css'
        if css_path.exists():
            provider = Gtk.CssProvider()
            try:
                provider.load_from_path(str(css_path))
                display = Gdk.Display.get_default()
                if display:
                    Gtk.StyleContext.add_provider_for_display(
                        display, provider,
                        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
                    )
            except GLib.Error as e:
                print(f'[BeetaControl] CSS load warning: {e.message}')

    def do_activate(self) -> None:
        """Create and show the main window."""
        win = ControlWindow(self, self._config)
        win.present()


def main() -> int:
    """Entry point for the Beeta Control Panel."""
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = BeetaControl()
    return app.run(sys.argv)


if __name__ == '__main__':
    sys.exit(main())
