# -*- coding: utf-8 -*-
# Beeta Desktop Environment
# Copyright (C) 2023-2026 Beeta Technologies Inc.
# Licensed under GNU General Public License v3.0

"""Adaptive Nature Theme for Lock Screen."""

import sys
import os
from pathlib import Path

# Resolve import paths for beeta-shell modules (config, adaptive_nature)
_script_dir = Path(__file__).resolve().parent
_dev_shell = _script_dir.parent.parent / 'beeta-shell'
_installed_shell = Path('/usr/lib/beeta-shell')

if _dev_shell.exists() and (_dev_shell / 'src' / 'config.py').exists():
    sys.path.insert(0, str(_dev_shell))
elif _installed_shell.exists():
    sys.path.insert(0, str(_installed_shell))

from src.adaptive_nature import AdaptiveNature
from src.config import BeetaConfig


class LockTheme:
    def __init__(self):
        self.config = BeetaConfig()
        self.nature = AdaptiveNature(self.config)
        # Force an initial computation so cached values are populated
        self.nature.update_theme()

    def get_lock_css(self) -> str:
        """Returns the CSS string for the lock screen glass."""
        # Read the computed colors from AdaptiveNature's cached properties
        glass_bg = self.nature.glass_bg or 'rgba(12, 14, 32, 0.75)'
        glass_border = self.nature.glass_border or 'rgba(255, 255, 255, 0.12)'
        accent = self.nature.accent_color or 'rgba(94, 231, 255, 1.0)'

        # Derive dimmed variants by simple string manipulation
        accent_dim = accent.replace('1.000)', '0.300)')
        glass_bg_dim = glass_bg.replace('0.750)', '0.300)').replace('0.720)', '0.300)').replace('0.780)', '0.300)').replace('0.750)', '0.300)')

        css = f"""
        window {{
            background-color: transparent;
        }}

        #overlay {{
            background-color: rgba(0, 0, 0, 0.3);
            transition: all 600ms cubic-bezier(0.2, 0.8, 0.2, 1.0);
        }}

        #user-card {{
            background-color: {glass_bg};
            border: 1px solid {glass_border};
            border-radius: 24px;
            padding: 32px;
            transition: all 400ms cubic-bezier(0.2, 0.8, 0.2, 1.0);
        }}

        #welcome-text {{
            color: rgba(238, 241, 255, 0.95);
            font-size: 20px;
            font-weight: 500;
        }}

        #clock-label {{
            color: white;
            font-size: 82px;
            font-weight: 200;
        }}

        #date-label {{
            color: rgba(255, 255, 255, 0.8);
            font-size: 24px;
            font-weight: 400;
        }}

        #password-entry {{
            background-color: rgba(0, 0, 0, 0.2);
            border: 1px solid {glass_border};
            border-radius: 12px;
            color: white;
            padding: 12px 16px;
            font-size: 16px;
            caret-color: {accent};
        }}

        #password-entry:focus {{
            border-color: {accent};
        }}

        #unlock-button {{
            background-color: {accent};
            color: rgba(0, 0, 0, 0.9);
            font-weight: 700;
            border-radius: 12px;
            padding: 12px;
            border: none;
        }}

        .widget-box {{
            background-color: {glass_bg};
            border: 1px solid {glass_border};
            border-radius: 16px;
            padding: 16px;
        }}

        .title {{
            color: rgba(238, 241, 255, 0.95);
            font-size: 18px;
            font-weight: 600;
        }}

        .dim-label {{
            color: rgba(255, 255, 255, 0.6);
            font-size: 14px;
        }}
        """
        return css

    def get_welcome_message(self, name: str) -> str:
        """Returns the Beeta Adaptive Welcome™ message."""
        import datetime
        now = datetime.datetime.now()
        hour = now.hour

        if 5 <= hour < 12:
            greeting = f"Good Morning, {name}."
        elif 12 <= hour < 18:
            greeting = f"Good Afternoon, {name}."
        elif 18 <= hour < 22:
            greeting = f"Good Evening, {name}."
        else:
            greeting = f"Good Night, {name}."

        return greeting
