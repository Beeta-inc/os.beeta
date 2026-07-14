import sys
import os

sys.path.insert(0, os.path.abspath('src'))
files_to_check = ['main', 'lock_screen', 'launcher', 'desktop_widgets', 'sidebar', 'topbar', 'bottombar', 'dock', 'weather_renderer']

for f in files_to_check:
    try:
        __import__(f)
        print(f"Successfully imported {f}")
    except Exception as e:
        print(f"Failed to import {f}: {e}")
