# -*- coding: utf-8 -*-
# Beeta Desktop Environment
# Copyright (C) 2023-2026 Beeta Technologies Inc.
# Licensed under GNU General Public License v3.0

"""Appearance settings page — the crown jewel of the Control Panel.

Features:
    - Adaptive Nature™ mode selector with live preview
    - Glass opacity, blur radius, and border opacity sliders
    - Accent color palette picker
    - Live mini-desktop preview that updates in real time
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib

if TYPE_CHECKING:
    from beeta_shell.config import BeetaConfig


# Accent color presets
_ACCENT_COLORS = [
    ('Cyan',    '94, 231, 255'),
    ('Purple',  '155, 108, 255'),
    ('Pink',    '255, 107, 214'),
    ('Amber',   '255, 191, 71'),
    ('Green',   '6, 214, 160'),
    ('Red',     '255, 107, 107'),
    ('Blue',    '80, 140, 255'),
    ('Teal',    '0, 200, 180'),
]


class AppearancePage(Gtk.Box):
    """Appearance settings with live preview and glass controls.

    This is the most visual page — changes are immediately reflected
    in a live mini-desktop preview at the top.
    """

    def __init__(self, config) -> None:
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=0,
        )
        self._config = config
        self._build_page()

    def _build_page(self) -> None:
        """Build the appearance settings layout."""
        # Page header
        title = Gtk.Label(label='Appearance')
        title.add_css_class('page-title')
        title.set_halign(Gtk.Align.START)
        self.append(title)

        subtitle = Gtk.Label(
            label='Make your desktop uniquely yours'
        )
        subtitle.add_css_class('page-subtitle')
        subtitle.set_halign(Gtk.Align.START)
        self.append(subtitle)

        # ── Live Preview ──
        self._build_preview()

        # ── Adaptive Nature Mode ──
        self._build_nature_card()

        # ── Glass Customization ──
        self._build_glass_card()

        # ── Accent Color ──
        self._build_accent_card()

    def _build_preview(self) -> None:
        """Build a live mini-desktop preview."""
        preview = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=6,
        )
        preview.add_css_class('preview-panel')
        preview.set_margin_bottom(20)

        # Mini top bar
        top_bar = Gtk.CenterBox()
        top_bar.add_css_class('preview-bar')

        # Workspace dots
        dots_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=0,
            margin_start=6,
        )
        for i in range(3):
            dot = Gtk.Box()
            dot.add_css_class('preview-dot')
            if i == 0:
                dot.add_css_class('active')
            dots_box.append(dot)
        top_bar.set_start_widget(dots_box)

        # Time
        time_label = Gtk.Label(label='10:42')
        time_label.add_css_class('preview-time')
        top_bar.set_center_widget(time_label)

        # Battery
        battery_label = Gtk.Label(label='🔋 92%')
        battery_label.add_css_class('preview-time')
        battery_label.set_margin_end(6)
        top_bar.set_end_widget(battery_label)

        preview.append(top_bar)

        # Desktop area (spacer)
        desktop = Gtk.Box()
        desktop.set_vexpand(True)
        desktop.set_size_request(-1, 60)
        preview.append(desktop)

        # Mini bottom bar
        bottom_bar = Gtk.CenterBox()
        bottom_bar.add_css_class('preview-bar')

        orb = Gtk.Box()
        orb.add_css_class('preview-orb')
        orb.set_margin_start(6)
        bottom_bar.set_start_widget(orb)

        dock_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=0,
        )
        for _ in range(5):
            icon = Gtk.Box()
            icon.add_css_class('preview-dock-icon')
            dock_box.append(icon)
        bottom_bar.set_center_widget(dock_box)

        weather = Gtk.Label(label='22°C ☀️')
        weather.add_css_class('preview-time')
        weather.set_margin_end(6)
        bottom_bar.set_end_widget(weather)

        preview.append(bottom_bar)

        self._preview = preview
        self.append(preview)

    def _build_nature_card(self) -> None:
        """Build the Adaptive Nature mode selector card."""
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        card.add_css_class('settings-card')

        card_title = Gtk.Label(label='ADAPTIVE NATURE™')
        card_title.add_css_class('card-title')
        card_title.set_halign(Gtk.Align.START)
        card.append(card_title)

        # Mode description
        desc = Gtk.Label(
            label='How your desktop responds to the world around you'
        )
        desc.add_css_class('card-row-sublabel')
        desc.set_halign(Gtk.Align.START)
        desc.set_margin_bottom(16)
        card.append(desc)

        # Mode selector pills
        mode_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=0,
        )
        mode_box.add_css_class('mode-selector')
        mode_box.set_homogeneous(True)

        current_mode = self._config.adaptive_mode
        self._nature_buttons: dict[str, Gtk.Button] = {}

        modes = [
            ('static', '🎨', 'Static', 'Fixed colors, no adaptation'),
            ('adaptive', '🌤', 'Adaptive', 'Responds to time & weather'),
            ('expressive', '✨', 'Expressive', 'Bold, vivid transitions'),
        ]

        for mode_id, icon, label, description in modes:
            btn = Gtk.Button()
            btn.add_css_class('mode-btn')
            if mode_id == current_mode:
                btn.add_css_class('active')

            content = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL,
                spacing=2,
                valign=Gtk.Align.CENTER,
                halign=Gtk.Align.CENTER,
            )

            icon_lbl = Gtk.Label(label=icon)
            icon_lbl.add_css_class('mode-btn-icon')
            content.append(icon_lbl)

            name_lbl = Gtk.Label(label=label)
            name_lbl.add_css_class('mode-btn-label')
            content.append(name_lbl)

            desc_lbl = Gtk.Label(label=description)
            desc_lbl.add_css_class('mode-btn-desc')
            desc_lbl.set_max_width_chars(20)
            desc_lbl.set_wrap(True)
            desc_lbl.set_justify(Gtk.Justification.CENTER)
            content.append(desc_lbl)

            btn.set_child(content)
            btn.connect('clicked', self._on_nature_mode, mode_id)
            mode_box.append(btn)
            self._nature_buttons[mode_id] = btn

        card.append(mode_box)
        self.append(card)

    def _build_glass_card(self) -> None:
        """Build the glass customization card with sliders."""
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        card.add_css_class('settings-card')

        card_title = Gtk.Label(label='GLASS CUSTOMIZATION')
        card_title.add_css_class('card-title')
        card_title.set_halign(Gtk.Align.START)
        card.append(card_title)

        # Opacity slider
        card.append(self._make_slider_row(
            'Panel Opacity',
            'Transparency of the top and bottom bars',
            'Glass', 'opacity',
            0.3, 1.0, 0.01,
            lambda v: f'{int(v * 100)}%',
        ))

        card.append(self._make_separator())

        # Blur radius slider
        card.append(self._make_slider_row(
            'Blur Radius',
            'Intensity of the backdrop blur effect',
            'Glass', 'blur_radius',
            0, 40, 1,
            lambda v: f'{int(v)}px',
        ))

        card.append(self._make_separator())

        # Border opacity slider
        card.append(self._make_slider_row(
            'Border Glow',
            'Visibility of glass panel borders',
            'Glass', 'border_opacity',
            0.0, 0.4, 0.01,
            lambda v: f'{int(v * 100)}%',
        ))

        card.append(self._make_separator())

        # Shadow opacity slider
        card.append(self._make_slider_row(
            'Shadow Depth',
            'Intensity of panel drop shadows',
            'Glass', 'shadow_opacity',
            0.0, 0.8, 0.01,
            lambda v: f'{int(v * 100)}%',
        ))

        self.append(card)

    def _build_accent_card(self) -> None:
        """Build the accent color picker card."""
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        card.add_css_class('settings-card')

        card_title = Gtk.Label(label='ACCENT COLOR')
        card_title.add_css_class('card-title')
        card_title.set_halign(Gtk.Align.START)
        card.append(card_title)

        desc = Gtk.Label(
            label='Primary color used across the entire desktop'
        )
        desc.add_css_class('card-row-sublabel')
        desc.set_halign(Gtk.Align.START)
        desc.set_margin_bottom(16)
        card.append(desc)

        # Color swatches grid
        swatch_box = Gtk.FlowBox()
        swatch_box.set_max_children_per_line(8)
        swatch_box.set_min_children_per_line(4)
        swatch_box.set_column_spacing(8)
        swatch_box.set_row_spacing(8)
        swatch_box.set_selection_mode(Gtk.SelectionMode.NONE)

        self._swatch_buttons: list[Gtk.Button] = []

        for name, rgb in _ACCENT_COLORS:
            btn = Gtk.Button()
            btn.add_css_class('color-swatch')
            btn.set_tooltip_text(name)

            # Apply inline CSS for the color
            provider = Gtk.CssProvider()
            provider.load_from_string(
                f'button {{ background-color: rgba({rgb}, 1.0); }}'
            )
            btn.get_style_context().add_provider(
                provider, Gtk.STYLE_PROVIDER_PRIORITY_USER
            )

            # Mark current selection
            if rgb == '94, 231, 255':  # default cyan
                btn.add_css_class('selected')

            btn.connect('clicked', self._on_accent_clicked, name, rgb)
            swatch_box.append(btn)
            self._swatch_buttons.append(btn)

        card.append(swatch_box)
        self.append(card)

    # ── Helpers ──────────────────────────────────────────────────

    def _make_slider_row(
        self,
        label: str,
        sublabel: str,
        config_section: str,
        config_key: str,
        min_val: float,
        max_val: float,
        step: float,
        format_fn,
    ) -> Gtk.Box:
        """Create a labeled slider row with value display.

        Args:
            label: Primary label.
            sublabel: Description text.
            config_section: Config section to read/write.
            config_key: Config key to read/write.
            min_val: Slider minimum.
            max_val: Slider maximum.
            step: Slider step increment.
            format_fn: Function to format the value for display.

        Returns:
            Complete slider row widget.
        """
        row = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
        )
        row.add_css_class('card-row')

        # Label row
        label_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
        )

        text_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=2,
        )
        lbl = Gtk.Label(label=label)
        lbl.add_css_class('card-row-label')
        lbl.set_halign(Gtk.Align.START)
        text_box.append(lbl)

        sub = Gtk.Label(label=sublabel)
        sub.add_css_class('card-row-sublabel')
        sub.set_halign(Gtk.Align.START)
        text_box.append(sub)

        label_row.append(text_box)
        text_box.set_hexpand(True)

        # Current value
        current = self._config.get_float(
            config_section, config_key, (min_val + max_val) / 2
        )
        value_label = Gtk.Label(label=format_fn(current))
        value_label.add_css_class('slider-value')
        value_label.set_halign(Gtk.Align.END)
        label_row.append(value_label)

        row.append(label_row)

        # Slider
        slider = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, min_val, max_val, step
        )
        slider.set_value(current)
        slider.set_draw_value(False)
        slider.add_css_class('beeta-slider')
        slider.set_hexpand(True)

        def on_change(scale: Gtk.Scale) -> None:
            val = scale.get_value()
            value_label.set_text(format_fn(val))
            self._config.set(config_section, config_key, str(val))

        slider.connect('value-changed', on_change)
        row.append(slider)

        return row

    @staticmethod
    def _make_separator() -> Gtk.Box:
        """Create a thin separator line."""
        sep = Gtk.Box()
        sep.add_css_class('card-separator')
        return sep

    # ── Event Handlers ───────────────────────────────────────────

    def _on_nature_mode(
        self, button: Gtk.Button, mode: str
    ) -> None:
        """Handle Adaptive Nature mode change."""
        for m, btn in self._nature_buttons.items():
            if m == mode:
                btn.add_css_class('active')
            else:
                btn.remove_css_class('active')
        self._config.set('Desktop', 'adaptive_nature_mode', mode)

    def _on_accent_clicked(
        self, button: Gtk.Button, name: str, rgb: str
    ) -> None:
        """Handle accent color swatch click."""
        for btn in self._swatch_buttons:
            btn.remove_css_class('selected')
        button.add_css_class('selected')
        # Store accent color in config (future: apply via AdaptiveNature)
        self._config.set('Desktop', 'accent_color', rgb)
