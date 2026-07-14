import sys
from unittest.mock import MagicMock
sys.modules['gi'] = MagicMock()
sys.modules['gi.repository'] = MagicMock()
sys.modules['gi.repository.Gtk'] = MagicMock()
sys.modules['gi.repository.Gdk'] = MagicMock()
sys.modules['gi.repository.GLib'] = MagicMock()
sys.modules['gi.repository.Gio'] = MagicMock()
sys.modules['gi.repository.Gtk4LayerShell'] = MagicMock()
sys.modules['gi.repository.GObject'] = MagicMock()
sys.modules['cairo'] = MagicMock()

import src.main

app = MagicMock()
app.config.get_bool.return_value = True

try:
    src.main.BeetaShell.do_activate(app)
    print("do_activate SUCCESS")
except Exception as e:
    import traceback
    traceback.print_exc()

