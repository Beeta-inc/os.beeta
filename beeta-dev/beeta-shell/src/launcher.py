# -*- coding: utf-8 -*-
# Beeta Desktop Environment
# Copyright (C) 2023-2026 Beeta Technologies Inc.
# Licensed under GNU General Public License v3.0

"""Fullscreen app launcher for the Beeta Desktop Shell.

Opens as a glass overlay covering the screen with:
    - Search bar at top (filters installed apps in real time)
    - Categorized grid of application icons
    - Smooth scale-up entrance animation
    - Closes with Escape key or clicking outside

Reads installed .desktop files from standard XDG paths and
presents them in a searchable, categorized grid.
"""

from __future__ import annotations

from dataclasses import dataclass
import shlex
import subprocess
from typing import TYPE_CHECKING, Dict, List, Optional

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gtk4LayerShell', '1.0')
from gi.repository import Gtk, Gtk4LayerShell, Gdk, Gio, GLib, GObject, Pango

if TYPE_CHECKING:
    from .adaptive_motion import AdaptiveMotion


# Category mapping from .desktop Categories field
_CATEGORY_MAP = {
    'Development': 'Development',
    'IDE': 'Development',
    'TextEditor': 'Development',
    'WebBrowser': 'Internet',
    'Network': 'Internet',
    'Email': 'Internet',
    'Chat': 'Internet',
    'AudioVideo': 'Media',
    'Audio': 'Media',
    'Video': 'Media',
    'Graphics': 'Media',
    'Photography': 'Media',
    'Office': 'Office',
    'WordProcessor': 'Office',
    'Spreadsheet': 'Office',
    'Presentation': 'Office',
    'System': 'System',
    'Settings': 'System',
    'Monitor': 'System',
    'TerminalEmulator': 'System',
    'FileManager': 'System',
    'Game': 'Games',
    'Utility': 'Utilities',
    'Calculator': 'Utilities',
    'Archiving': 'Utilities',
}

# Display order for categories
_CATEGORY_ORDER = [
    'All', 'Development', 'Internet', 'Media',
    'Office', 'System', 'Games', 'Utilities', 'Other',
]


class _AppEntry:
    """Metadata for a single installed application."""

    __slots__ = ('app_info', 'name', 'icon', 'category', 'keywords')

    def __init__(
        self,
        app_info: Gio.DesktopAppInfo,
        name: str,
        icon: Optional[Gio.Icon],
        category: str,
        keywords: str,
    ) -> None:
        self.app_info = app_info
        self.name = name
        self.icon = icon
        self.category = category
        self.keywords = keywords


class Launcher:
    """Fullscreen application launcher overlay.

    Uses a layer-shell window in the OVERLAY layer to cover the
    entire screen with a glass-styled app grid and search.

    Args:
        app: The parent Gtk.Application.
        adaptive_motion: Adaptive Motion engine.
    """

    def __init__(
        self,
        app: Gtk.Application,
        adaptive_motion: AdaptiveMotion,
    ) -> None:
        self._app = app
        self._motion = adaptive_motion
        self._visible: bool = False
        self._all_apps: list[_AppEntry] = []
        self._current_category: str = 'All'

        # Create the overlay window
        self._window = Gtk.Window(application=app)
        self._window.set_title('Beeta Launcher')
        self._window.set_decorated(False)

        Gtk4LayerShell.init_for_window(self._window)
        Gtk4LayerShell.set_layer(
            self._window, Gtk4LayerShell.Layer.OVERLAY
        )
        Gtk4LayerShell.set_namespace(self._window, 'beeta-launcher')
        Gtk4LayerShell.set_keyboard_mode(
            self._window, Gtk4LayerShell.KeyboardMode.EXCLUSIVE
        )

        # Position above the start menu orb (bottom-left)
        Gtk4LayerShell.set_anchor(self._window, Gtk4LayerShell.Edge.BOTTOM, True)
        Gtk4LayerShell.set_anchor(self._window, Gtk4LayerShell.Edge.LEFT, True)
        Gtk4LayerShell.set_margin(self._window, Gtk4LayerShell.Edge.BOTTOM, 80)
        Gtk4LayerShell.set_margin(self._window, Gtk4LayerShell.Edge.LEFT, 24)

        # Don't reserve space
        Gtk4LayerShell.set_exclusive_zone(self._window, 0)

        # Build content
        self._build_content()

        # Load installed apps
        self._load_apps()

        # Keyboard handler
        key_ctrl = Gtk.EventControllerKey()
        key_ctrl.connect('key-pressed', self._on_key_pressed)
        self._window.add_controller(key_ctrl)

    @property
    def is_visible(self) -> bool:
        """Whether the launcher is currently visible."""
        return self._visible

    def show(self) -> None:
        """Show the launcher overlay."""
        if self._visible:
            return
        self._visible = True
        self._current_category = 'All'
        self._filter_and_display()
        self._window.present()

    def hide(self) -> None:
        """Hide the launcher overlay."""
        if not self._visible:
            return
        self._visible = False
        self._window.set_visible(False)

    def toggle(self) -> None:
        """Toggle launcher visibility."""
        if self._visible:
            self.hide()
        else:
            self.show()

    # ── Internal: Build UI ───────────────────────────────────────

    def _build_content(self) -> None:
        """Build the launcher layout."""
        # Main launcher panel
        panel = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=24,
        )
        panel.add_css_class('glass-panel-rounded')
        panel.add_css_class('launcher-panel')
        panel.set_size_request(600, 400)
        
        # ── Left Pane: Most Used ──
        left_pane = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        left_pane.set_size_request(200, -1)
        left_title = Gtk.Label(label='Most Used')
        left_title.add_css_class('launcher-section-title')
        left_title.set_halign(Gtk.Align.START)
        left_pane.append(left_title)
        
        # We will populate this in _filter_and_display or just grab the first 6 apps
        self._most_used_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        left_pane.append(self._most_used_box)
        
        # All Apps link
        all_apps_btn = Gtk.Button(label='All Applications →')
        all_apps_btn.add_css_class('launcher-all-btn')
        all_apps_btn.set_halign(Gtk.Align.START)
        left_pane.append(all_apps_btn)
        
        # ── Right Pane: Categories ──
        right_pane = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        right_pane.set_hexpand(True)
        
        right_title = Gtk.Label(label='Categories')
        right_title.add_css_class('launcher-section-title')
        right_title.set_halign(Gtk.Align.START)
        right_pane.append(right_title)
        
        self._category_grid = Gtk.FlowBox()
        self._category_grid.set_valign(Gtk.Align.START)
        self._category_grid.set_max_children_per_line(2)
        self._category_grid.set_min_children_per_line(2)
        self._category_grid.set_column_spacing(12)
        self._category_grid.set_row_spacing(12)
        self._category_grid.set_homogeneous(True)
        self._category_grid.set_selection_mode(Gtk.SelectionMode.NONE)
        
        right_pane.append(self._category_grid)
        
        panel.append(left_pane)
        # Separator line
        sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        sep.add_css_class('launcher-separator')
        panel.append(sep)
        panel.append(right_pane)

        self._window.set_child(panel)

    # ── Internal: App Loading ────────────────────────────────────

    def _load_apps(self) -> None:
        """Load all installed .desktop applications."""
        self._all_apps.clear()

        all_app_infos = Gio.AppInfo.get_all()
        for info in all_app_infos:
            if not isinstance(info, Gio.DesktopAppInfo):
                continue

            # Skip hidden / no-display apps
            if info.get_nodisplay() or info.get_is_hidden():
                continue

            name = info.get_display_name() or ''
            if not name:
                continue

            icon = info.get_icon()
            categories_str = info.get_categories() or ''

            # Determine primary category
            category = 'Other'
            for cat in categories_str.split(';'):
                cat = cat.strip()
                if cat in _CATEGORY_MAP:
                    category = _CATEGORY_MAP[cat]
                    break

            # Build searchable keywords
            keywords_parts = [
                name.lower(),
                (info.get_generic_name() or '').lower(),
                (info.get_description() or '').lower(),
                categories_str.lower(),
            ]
            keywords = ' '.join(keywords_parts)

            self._all_apps.append(_AppEntry(
                app_info=info,
                name=name,
                icon=icon,
                category=category,
                keywords=keywords,
            ))

        # Sort alphabetically
        self._all_apps.sort(key=lambda a: a.name.lower())

    def _filter_and_display(self) -> None:
        """Populate the two-section layout."""
        # 1. Populate Most Used (just grab top 8 for now)
        child = self._most_used_box.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self._most_used_box.remove(child)
            child = next_child
            
        for app in self._all_apps[:8]:
            btn = self._create_most_used_widget(app)
            self._most_used_box.append(btn)
            
        # 2. Populate Categories or Apps
        child = self._category_grid.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self._category_grid.remove(child)
            child = next_child
            
        if getattr(self, '_current_category', 'All') == 'All':
            # Show Categories
            cat_counts = {c: 0 for c in _CATEGORY_ORDER if c != 'All'}
            for app in self._all_apps:
                if app.category in cat_counts:
                    cat_counts[app.category] += 1
                    
            icons = {
                'Development': 'applications-development-symbolic',
                'Internet': 'applications-internet-symbolic',
                'Media': 'applications-multimedia-symbolic',
                'Office': 'applications-office-symbolic',
                'System': 'applications-system-symbolic',
                'Games': 'applications-games-symbolic',
                'Utilities': 'applications-utilities-symbolic',
                'Other': 'applications-other-symbolic'
            }
                    
            for cat, count in cat_counts.items():
                if count > 0:
                    btn = self._create_category_widget(cat, count, icons.get(cat, 'folder-symbolic'))
                    self._category_grid.append(btn)
        else:
            # Show Apps for the selected category + Back button
            back_btn = Gtk.Button(label='← Back to Categories')
            back_btn.add_css_class('launcher-cat-btn')
            back_btn.connect('clicked', lambda b: self._on_category_clicked(b, 'All'))
            self._category_grid.append(back_btn)
            
            for app in self._all_apps:
                if app.category == self._current_category:
                    # We can reuse _create_most_used_widget for the grid item for now
                    btn = self._create_most_used_widget(app)
                    btn.add_css_class('launcher-cat-btn')
                    self._category_grid.append(btn)

    def _create_most_used_widget(self, app: _AppEntry) -> Gtk.Button:
        btn = Gtk.Button()
        btn.add_css_class('launcher-mu-btn')
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        if app.icon:
            img = Gtk.Image.new_from_gicon(app.icon)
            img.set_pixel_size(24)
            box.append(img)
        lbl = Gtk.Label(label=app.name)
        lbl.set_ellipsize(Pango.EllipsizeMode.END)
        box.append(lbl)
        btn.set_child(box)
        btn.connect('clicked', self._on_app_clicked, app)
        return btn
        
    def _create_category_widget(self, name: str, count: int, icon_name: str) -> Gtk.Button:
        btn = Gtk.Button()
        btn.add_css_class('launcher-cat-btn')
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, valign=Gtk.Align.CENTER)
        
        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_pixel_size(32)
        box.append(icon)
        
        text_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        title = Gtk.Label(label=name)
        title.set_halign(Gtk.Align.START)
        title.add_css_class('launcher-cat-title')
        sub = Gtk.Label(label=f'{count} Apps')
        sub.set_halign(Gtk.Align.START)
        sub.add_css_class('launcher-cat-sub')
        text_col.append(title)
        text_col.append(sub)
        
        box.append(text_col)
        btn.set_child(box)
        btn.connect('clicked', lambda b: self._on_category_clicked(b, name))
        return btn

    # ── Internal: Event Handlers ─────────────────────────────────

    def _on_category_clicked(
        self, button: Gtk.Button, category: str
    ) -> None:
        """Handle category tab click."""
        self._current_category = category
        self._filter_and_display()

    def _on_app_clicked(
        self, button: Gtk.Button, app: _AppEntry
    ) -> None:
        """Launch the clicked application and close the launcher."""
        try:
            cmd = app.app_info.get_commandline()
            if cmd:
                # Strip desktop file placeholders like %U, %u, %F, %f
                for ph in ['%U', '%u', '%F', '%f', '%c', '%k']:
                    cmd = cmd.replace(ph, '')
                # Split and spawn safely
                args = shlex.split(cmd.strip())
                if args:
                    subprocess.Popen(args, start_new_session=True)
                    print(f'[Launcher] Launched: {app.name}')
            else:
                # Fallback to standard context if no explicit commandline is provided
                context = Gdk.Display.get_default().get_app_launch_context()
                app.app_info.launch([], context)
        except Exception as e:
            print(f'[Launcher] Failed to launch {app.name}: {e}')
        self.hide()



    def _on_key_pressed(
        self,
        controller: Gtk.EventControllerKey,
        keyval: int,
        keycode: int,
        state: Gdk.ModifierType,
    ) -> bool:
        """Handle keyboard events — Escape to close."""
        if keyval == Gdk.KEY_Escape:
            self.hide()
            return True
        return False
