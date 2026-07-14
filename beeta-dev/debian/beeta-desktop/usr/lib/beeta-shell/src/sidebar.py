# -*- coding: utf-8 -*-
# Beeta Desktop Environment

from __future__ import annotations
import subprocess

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gtk4LayerShell', '1.0')
from gi.repository import Gtk, Gtk4LayerShell

class Sidebar(Gtk.Window):
    """Floating sidebar with desktop icons (Home, Projects, Trash)."""

    def __init__(self, app: Gtk.Application) -> None:
        super().__init__(application=app)
        self.set_title('Beeta Sidebar')
        self.set_decorated(False)
        
        Gtk4LayerShell.init_for_window(self)
        Gtk4LayerShell.set_layer(self, Gtk4LayerShell.Layer.BOTTOM)
        Gtk4LayerShell.set_namespace(self, 'beeta-sidebar')
        
        # Anchor to the left side
        Gtk4LayerShell.set_anchor(self, Gtk4LayerShell.Edge.LEFT, True)
        
        # Center vertically (we could anchor top and bottom, but let's just margin top)
        Gtk4LayerShell.set_margin(self, Gtk4LayerShell.Edge.LEFT, 24)
        Gtk4LayerShell.set_margin(self, Gtk4LayerShell.Edge.TOP, 100) # Below topbar
        
        self.add_css_class('sidebar-panel')
        
        # Build UI
        self._build_content()
        self.present()

    def _build_content(self) -> None:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        
        # Home
        btn_home = self._create_icon_btn('user-home-symbolic', 'Home', self._on_home_clicked)
        box.append(btn_home)
        
        # Projects
        btn_projects = self._create_icon_btn('folder-symbolic', 'Projects', self._on_projects_clicked)
        box.append(btn_projects)
        
        # Trash
        btn_trash = self._create_icon_btn('user-trash-symbolic', 'Trash', self._on_trash_clicked)
        box.append(btn_trash)
        
        self.set_child(box)

    def _create_icon_btn(self, icon_name: str, label_text: str, callback) -> Gtk.Button:
        btn = Gtk.Button()
        btn.add_css_class('sidebar-icon-btn')
        
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        
        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_pixel_size(32)
        icon.add_css_class('sidebar-icon')
        vbox.append(icon)
        
        lbl = Gtk.Label(label=label_text)
        lbl.add_css_class('sidebar-label')
        vbox.append(lbl)
        
        btn.set_child(vbox)
        btn.connect('clicked', callback)
        return btn

    def _on_home_clicked(self, button: Gtk.Button) -> None:
        subprocess.Popen(['nautilus', '/home/noywrit'], start_new_session=True)

    def _on_projects_clicked(self, button: Gtk.Button) -> None:
        subprocess.Popen(['nautilus', '/home/noywrit/Projects'], start_new_session=True)

    def _on_trash_clicked(self, button: Gtk.Button) -> None:
        subprocess.Popen(['nautilus', 'trash:///'], start_new_session=True)

    def cleanup(self) -> None:
        self.destroy()
