import sys
from unittest.mock import MagicMock
sys.modules['gi'] = MagicMock()
sys.modules['gi.repository'] = MagicMock()
sys.modules['cairo'] = MagicMock()

import os
files = [f[:-3] for f in os.listdir('src') if f.endswith('.py') and f != '__init__.py']
for f in files:
    try:
        __import__(f"src.{f}")
        print(f"{f}: OK")
    except Exception as e:
        print(f"{f}: ERROR - {e}")
