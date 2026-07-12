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

from typing import TYPE_CHECKING, Optional

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

        # Cover entire screen
        for edge in (
            Gtk4LayerShell.Edge.TOP,
            Gtk4LayerShell.Edge.BOTTOM,
            Gtk4LayerShell.Edge.LEFT,
            Gtk4LayerShell.Edge.RIGHT,
        ):
            Gtk4LayerShell.set_anchor(self._window, edge, True)

        # Don't reserve space
        Gtk4LayerShell.set_exclusive_zone(self._window, -1)

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
        self._search_entry.set_text('')
        self._search_entry.grab_focus()
        self._current_category = 'All'
        self._update_category_buttons()
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
        # Semi-transparent backdrop
        backdrop = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            valign=Gtk.Align.CENTER,
            halign=Gtk.Align.CENTER,
        )
        backdrop.add_css_class('launcher-backdrop')

        # Main launcher panel
        panel = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=0,
        )
        panel.add_css_class('launcher')
        panel.set_size_request(650, 520)

        # ── Search Bar ──
        self._search_entry = Gtk.SearchEntry()
        self._search_entry.set_placeholder_text(
            'Search applications...'
        )
        self._search_entry.add_css_class('launcher-search')
        self._search_entry.connect(
            'search-changed', self._on_search_changed
        )
        panel.append(self._search_entry)

        # ── Category Tabs ──
        category_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=6,
            margin_bottom=12,
        )
        self._category_buttons: dict[str, Gtk.Button] = {}

        for cat in _CATEGORY_ORDER:
            btn = Gtk.Button(label=cat)
            btn.add_css_class('qs-mode-btn')
            if cat == 'All':
                btn.add_css_class('active')
            btn.connect('clicked', self._on_category_clicked, cat)
            category_box.append(btn)
            self._category_buttons[cat] = btn

        panel.append(category_box)

        # ── App Grid (scrollable) ──
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(
            Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC
        )
        scroll.set_vexpand(True)
        scroll.set_min_content_height(380)

        self._app_grid = Gtk.FlowBox()
        self._app_grid.set_valign(Gtk.Align.START)
        self._app_grid.set_max_children_per_line(6)
        self._app_grid.set_min_children_per_line(4)
        self._app_grid.set_column_spacing(8)
        self._app_grid.set_row_spacing(8)
        self._app_grid.set_homogeneous(True)
        self._app_grid.set_selection_mode(Gtk.SelectionMode.NONE)

        scroll.set_child(self._app_grid)
        panel.append(scroll)

        backdrop.append(panel)

        # Click outside to close
        click_ctrl = Gtk.GestureClick()
        click_ctrl.connect('released', self._on_backdrop_clicked)
        backdrop.add_controller(click_ctrl)

        self._window.set_child(backdrop)

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
        """Filter apps by current category and search, then display."""
        search_text = self._search_entry.get_text().strip().lower()

        # Clear current grid
        child = self._app_grid.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self._app_grid.remove(child)
            child = next_child

        # Filter
        filtered: list[_AppEntry] = []
        for app in self._all_apps:
            # Category filter
            if (
                self._current_category != 'All'
                and app.category != self._current_category
            ):
                continue

            # Search filter
            if search_text and search_text not in app.keywords:
                continue

            filtered.append(app)

        # Display
        for app in filtered:
            widget = self._create_app_widget(app)
            self._app_grid.append(widget)

    def _create_app_widget(self, app: _AppEntry) -> Gtk.Button:
        """Create a single app icon button for the grid.

        Args:
            app: The app entry to display.

        Returns:
            Styled button widget.
        """
        button = Gtk.Button()
        button.add_css_class('launcher-app')

        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=4,
            valign=Gtk.Align.CENTER,
            halign=Gtk.Align.CENTER,
        )

        if app.icon:
            image = Gtk.Image.new_from_gicon(app.icon)
            image.set_pixel_size(48)
            box.append(image)
        else:
            # Fallback icon
            image = Gtk.Image.new_from_icon_name(
                'application-x-executable'
            )
            image.set_pixel_size(48)
            box.append(image)

        name_label = Gtk.Label(label=app.name)
        name_label.add_css_class('launcher-app-name')
        name_label.set_ellipsize(Pango.EllipsizeMode.END)
        name_label.set_max_width_chars(12)
        name_label.set_halign(Gtk.Align.CENTER)
        box.append(name_label)

        button.set_child(box)
        button.set_tooltip_text(app.name)

        # Click to launch
        button.connect('clicked', self._on_app_clicked, app)

        return button

    # ── Internal: Event Handlers ─────────────────────────────────

    def _on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        """Handle search text changes — filter apps in real time."""
        self._filter_and_display()

    def _on_category_clicked(
        self, button: Gtk.Button, category: str
    ) -> None:
        """Handle category tab click."""
        self._current_category = category
        self._update_category_buttons()
        self._filter_and_display()

    def _update_category_buttons(self) -> None:
        """Update active state of category buttons."""
        for cat, btn in self._category_buttons.items():
            if cat == self._current_category:
                btn.add_css_class('active')
            else:
                btn.remove_css_class('active')

    def _on_app_clicked(
        self, button: Gtk.Button, app: _AppEntry
    ) -> None:
        """Launch the clicked application and close the launcher."""
        try:
            context = Gdk.Display.get_default().get_app_launch_context()
            app.app_info.launch([], context)
        except Exception as e:
            print(f'[Launcher] Failed to launch {app.name}: {e}')
        self.hide()

    def _on_backdrop_clicked(
        self,
        gesture: Gtk.GestureClick,
        n_press: int,
        x: float,
        y: float,
    ) -> None:
        """Close launcher when clicking the backdrop."""
        # Only close if click is outside the panel
        # (the panel handles its own clicks)
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
