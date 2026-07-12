# -*- coding: utf-8 -*-
# Beeta Desktop Environment
# Copyright (C) 2023-2026 Beeta Technologies Inc.
# Licensed under GNU General Public License v3.0

"""Adaptive Nature Theme for Lock Screen."""

import sys
import os
from pathlib import Path

_src_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_src_dir / 'beeta-shell'))
from src.adaptive_nature import AdaptiveNature, NatureState
from src.config import BeetaConfig

class LockTheme:
    def __init__(self):
        self.config = BeetaConfig()
        self.nature = AdaptiveNature(self.config)

    def get_lock_css(self) -> str:
        """Returns the CSS string for the lock screen glass based on weather/time."""
        state = self.nature.get_current_state()
        
        # We'll use the background colors and glass settings from AdaptiveNature
        # The user requested:
        # Sunny -> Golden tint
        # Rain -> Cooler blue
        # Night -> Deep navy
        # Winter -> Frosted white
        
        # We can map the state values to our lock screen CSS
        glass_rgba = state.glass_bg
        border_rgba = state.glass_border
        accent = state.accent_rgba
        
        css = f"""
        window {{
            background-color: transparent;
        }}
        
        #overlay {{
            background-color: {state.bg_deep.replace('1.0)', '0.3)')};
            transition: all 600ms cubic-bezier(0.2, 0.8, 0.2, 1.0);
        }}
        
        #user-card {{
            background-color: {glass_rgba};
            border: 1px solid {border_rgba};
            border-radius: 24px;
            box-shadow: 0 24px 64px rgba(0,0,0,0.4);
            padding: 32px;
            transition: all 400ms cubic-bezier(0.2, 0.8, 0.2, 1.0);
        }}
        
        #welcome-text {{
            color: rgba(238, 241, 255, 0.95);
            font-size: 20px;
            font-weight: 500;
            text-shadow: 0 2px 8px rgba(0,0,0,0.5);
        }}
        
        #clock-label {{
            color: white;
            font-size: 82px;
            font-weight: 200;
            text-shadow: 0 4px 16px rgba(0,0,0,0.5);
        }}
        
        #date-label {{
            color: rgba(255, 255, 255, 0.8);
            font-size: 24px;
            font-weight: 400;
            text-shadow: 0 2px 8px rgba(0,0,0,0.5);
        }}
        
        #password-entry {{
            background-color: rgba(0, 0, 0, 0.2);
            border: 1px solid {border_rgba};
            border-radius: 12px;
            color: white;
            padding: 12px 16px;
            font-size: 16px;
            caret-color: {accent};
        }}
        
        #password-entry:focus {{
            border-color: {accent};
            box-shadow: 0 0 0 2px {accent.replace('1.0)', '0.3)')};
        }}
        
        #unlock-button {{
            background: linear-gradient(135deg, {accent}, {accent.replace('1.0)', '0.8)')});
            color: black;
            font-weight: 700;
            border-radius: 12px;
            padding: 12px;
            border: none;
        }}
        
        #unlock-button:hover {{
            box-shadow: 0 4px 16px {accent.replace('1.0)', '0.4)')};
        }}
        
        .widget-box {{
            background-color: {glass_rgba};
            border: 1px solid {border_rgba};
            border-radius: 16px;
            padding: 16px;
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
            
        weather = self.config.get("weather.condition", "Sunny")
        temp = self.config.get("weather.temperature", "24°C")
        
        if "Rain" in weather:
            context = f"It's {temp} today. Grab an umbrella."
        elif "Snow" in weather:
            context = f"It's {temp} outside. Stay warm."
        else:
            if hour >= 20:
                context = f"{temp} outside. Rest well."
            else:
                context = f"It's {temp} today. Have a great day."
                
        return f"{greeting}\n{context}"
