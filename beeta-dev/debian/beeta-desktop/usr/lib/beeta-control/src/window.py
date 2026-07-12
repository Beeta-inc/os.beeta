# -*- coding: utf-8 -*-
# Beeta Desktop Environment
# Copyright (C) 2023-2026 Beeta Technologies Inc.
# Licensed under GNU General Public License v3.0

"""Main window for the Beeta Control Panel.

Features a sidebar navigation with icon + label items, smooth page
transitions, and a scrollable content area. The sidebar has a Beeta
logo header and grouped navigation sections.
"""

from __future__ import annotations

from typing import Optional

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, GLib

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'beeta-shell'))
from src.config import BeetaConfig

from .pages.appearance import AppearancePage
from .pages.performance import PerformancePage
from .pages.desktop import DesktopPage
from .pages.display import DisplayPage
from .pages.sound import SoundPage
from .pages.network import NetworkPage
from .pages.battery import BatteryPage
from .pages.about import AboutPage


# Navigation structure: (id, icon, label, section)
_NAV_ITEMS = [
    # Section: Personalize
    ('_section', '', 'PERSONALIZE', ''),
    ('appearance', '🎨', 'Appearance', 'personalize'),
    ('performance', '⚡', 'Performance', 'personalize'),
    ('desktop', '🖥', 'Desktop', 'personalize'),
    # Section: System
    ('_section', '', 'SYSTEM', ''),
    ('display', '🖵', 'Display', 'system'),
    ('sound', '🔊', 'Sound', 'system'),
    ('network', '📶', 'Network', 'system'),
    ('battery', '🔋', 'Battery', 'system'),
    # Section: Info
    ('_section', '', '', ''),
    ('about', 'ℹ️', 'About Beeta', 'info'),
]


class ControlWindow(Gtk.ApplicationWindow):
    """Main Control Panel window with sidebar navigation.

    The window is split into two panes:
        - Left sidebar: navigation with grouped sections
        - Right content: scrollable settings page

    Page transitions are handled by a Gtk.Stack with crossfade.

    Args:
        app: Parent Gtk.Application.
        config: Beeta configuration instance.
    """

    def __init__(self, app: Gtk.Application, config: BeetaConfig) -> None:
        super().__init__(
            application=app,
            title='Beeta Control',
            default_width=960,
            default_height=680,
        )
        self._config = config
        self._nav_buttons: dict[str, Gtk.Button] = {}
        self._active_page: str = 'appearance'

        # Build the UI
        self._build_layout()

        # Select initial page
        self._select_page('appearance')

    def _build_layout(self) -> None:
        """Build the two-pane layout with sidebar and content."""
        main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        # ── Sidebar ──
        sidebar = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=0,
        )
        sidebar.add_css_class('sidebar')

        # Logo header
        header = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=0,
        )
        header.add_css_class('sidebar-header')

        logo_text = Gtk.Label(label='Beeta')
        logo_text.add_css_class('sidebar-logo-text')
        logo_text.set_halign(Gtk.Align.START)
        header.append(logo_text)

        logo_sub = Gtk.Label(label='CONTROL PANEL')
        logo_sub.add_css_class('sidebar-logo-sub')
        logo_sub.set_halign(Gtk.Align.START)
        header.append(logo_sub)

        sidebar.append(header)

        # Navigation items in a scrollable area
        nav_scroll = Gtk.ScrolledWindow()
        nav_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        nav_scroll.set_vexpand(True)

        nav_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=0,
        )

        for item_id, icon, label, section in _NAV_ITEMS:
            if item_id == '_section':
                # Section label
                if label:
                    section_label = Gtk.Label(label=label)
                    section_label.add_css_class('nav-section-label')
                    section_label.set_halign(Gtk.Align.START)
                    nav_box.append(section_label)
                else:
                    # Spacer
                    spacer = Gtk.Box()
                    spacer.set_size_request(-1, 12)
                    nav_box.append(spacer)
            else:
                btn = self._create_nav_item(item_id, icon, label)
                nav_box.append(btn)
                self._nav_buttons[item_id] = btn

        nav_scroll.set_child(nav_box)
        sidebar.append(nav_scroll)

        # Version at bottom of sidebar
        version_label = Gtk.Label(label='v0.1.0')
        version_label.add_css_class('nav-section-label')
        version_label.set_halign(Gtk.Align.START)
        version_label.set_margin_bottom(16)
        version_label.set_margin_start(20)
        sidebar.append(version_label)

        main_box.append(sidebar)

        # ── Content Area ──
        content_wrapper = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            hexpand=True,
        )
        content_wrapper.add_css_class('content-area')

        # Page stack with crossfade transitions
        self._stack = Gtk.Stack()
        self._stack.set_transition_type(
            Gtk.StackTransitionType.CROSSFADE
        )
        self._stack.set_transition_duration(200)
        self._stack.set_vexpand(True)
        self._stack.set_hexpand(True)

        # Create all pages
        self._create_pages()

        content_wrapper.append(self._stack)
        main_box.append(content_wrapper)

        self.set_child(main_box)

    def _create_nav_item(
        self, item_id: str, icon: str, label: str
    ) -> Gtk.Button:
        """Create a sidebar navigation button.

        Args:
            item_id: Unique identifier for the page.
            icon: Emoji icon.
            label: Display label.

        Returns:
            Styled navigation button.
        """
        btn = Gtk.Button()
        btn.add_css_class('nav-item')

        row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=0,
            valign=Gtk.Align.CENTER,
        )

        icon_label = Gtk.Label(label=icon)
        icon_label.add_css_class('nav-icon')
        row.append(icon_label)

        text_label = Gtk.Label(label=label)
        text_label.add_css_class('nav-label')
        text_label.set_halign(Gtk.Align.START)
        row.append(text_label)

        btn.set_child(row)
        btn.connect('clicked', self._on_nav_clicked, item_id)

        return btn

    def _create_pages(self) -> None:
        """Instantiate all settings pages and add to the stack."""
        pages = {
            'appearance': AppearancePage(self._config),
            'performance': PerformancePage(self._config),
            'desktop': DesktopPage(self._config),
            'display': DisplayPage(self._config),
            'sound': SoundPage(self._config),
            'network': NetworkPage(self._config),
            'battery': BatteryPage(self._config),
            'about': AboutPage(self._config),
        }

        for page_id, page_widget in pages.items():
            scroll = Gtk.ScrolledWindow()
            scroll.set_policy(
                Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC
            )
            scroll.set_child(page_widget)
            self._stack.add_named(scroll, page_id)

    def _select_page(self, page_id: str) -> None:
        """Switch to the specified settings page.

        Args:
            page_id: The page identifier to display.
        """
        self._active_page = page_id
        self._stack.set_visible_child_name(page_id)

        # Update nav button active states
        for nav_id, btn in self._nav_buttons.items():
            if nav_id == page_id:
                btn.add_css_class('active')
            else:
                btn.remove_css_class('active')

    def _on_nav_clicked(
        self, button: Gtk.Button, page_id: str
    ) -> None:
        """Handle sidebar navigation click."""
        self._select_page(page_id)
