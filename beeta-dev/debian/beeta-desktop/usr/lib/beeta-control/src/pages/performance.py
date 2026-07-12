# -*- coding: utf-8 -*-
# Beeta Desktop Environment
# Copyright (C) 2023-2026 Beeta Technologies Inc.
# Licensed under GNU General Public License v3.0

"""Performance settings page — Adaptive Motion™ control center."""

from __future__ import annotations

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk


class PerformancePage(Gtk.Box):
    """Performance settings with motion tier selector and battery options."""

    def __init__(self, config) -> None:
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=0,
        )
        self._config = config
        self._build_page()

    def _build_page(self) -> None:
        title = Gtk.Label(label='Performance')
        title.add_css_class('page-title')
        title.set_halign(Gtk.Align.START)
        self.append(title)

        subtitle = Gtk.Label(
            label='Balance beauty with battery life'
        )
        subtitle.add_css_class('page-subtitle')
        subtitle.set_halign(Gtk.Align.START)
        self.append(subtitle)

        # ── Adaptive Motion Mode ──
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        card.add_css_class('settings-card')

        card_title = Gtk.Label(label='ADAPTIVE MOTION™')
        card_title.add_css_class('card-title')
        card_title.set_halign(Gtk.Align.START)
        card.append(card_title)

        desc = Gtk.Label(
            label='Controls animation quality, blur intensity, and visual effects'
        )
        desc.add_css_class('card-row-sublabel')
        desc.set_halign(Gtk.Align.START)
        desc.set_margin_bottom(16)
        card.append(desc)

        mode_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=0,
        )
        mode_box.add_css_class('mode-selector')
        mode_box.set_homogeneous(True)

        current_mode = self._config.performance_mode
        self._mode_buttons: dict[str, Gtk.Button] = {}

        modes = [
            ('power-saver', '🔋', 'Power Saver',
             '8px blur · Fast fades · No particles',
             '~2h extra battery'),
            ('balanced', '⚡', 'Balanced',
             '20px blur · Smooth animations',
             'Recommended'),
            ('performance', '🚀', 'Performance',
             '28px blur · Full effects · Particles',
             'Maximum visual quality'),
        ]

        for mode_id, icon, label, desc_text, badge_text in modes:
            btn = Gtk.Button()
            btn.add_css_class('mode-btn')
            if mode_id == current_mode:
                btn.add_css_class('active')

            content = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL,
                spacing=3,
                valign=Gtk.Align.CENTER,
                halign=Gtk.Align.CENTER,
            )

            icon_lbl = Gtk.Label(label=icon)
            icon_lbl.add_css_class('mode-btn-icon')
            content.append(icon_lbl)

            name_lbl = Gtk.Label(label=label)
            name_lbl.add_css_class('mode-btn-label')
            content.append(name_lbl)

            desc_lbl = Gtk.Label(label=desc_text)
            desc_lbl.add_css_class('mode-btn-desc')
            desc_lbl.set_max_width_chars(22)
            desc_lbl.set_wrap(True)
            desc_lbl.set_justify(Gtk.Justification.CENTER)
            content.append(desc_lbl)

            btn.set_child(content)
            btn.connect('clicked', self._on_mode_change, mode_id)
            mode_box.append(btn)
            self._mode_buttons[mode_id] = btn

        card.append(mode_box)
        self.append(card)

        # ── Smart Battery Card ──
        batt_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        batt_card.add_css_class('settings-card')

        batt_title = Gtk.Label(label='SMART BATTERY')
        batt_title.add_css_class('card-title')
        batt_title.set_halign(Gtk.Align.START)
        batt_card.append(batt_title)

        # Auto-downgrade toggle
        batt_card.append(self._make_switch_row(
            'Auto-downgrade on low battery',
            'Reduce animation tier when battery drops below 20%',
            True,
        ))

        sep = Gtk.Box()
        sep.add_css_class('card-separator')
        batt_card.append(sep)

        # Critical battery toggle
        batt_card.append(self._make_switch_row(
            'Minimal animations at critical level',
            'Disable most animations below 10% battery',
            True,
        ))

        sep2 = Gtk.Box()
        sep2.add_css_class('card-separator')
        batt_card.append(sep2)

        # Pause hidden animations
        batt_card.append(self._make_switch_row(
            'Pause hidden component animations',
            'Stop animations on hidden bars to save resources',
            True,
        ))

        self.append(batt_card)

        # ── Specs Card ──
        specs_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        specs_card.add_css_class('settings-card')

        specs_title = Gtk.Label(label='CURRENT TIER SPECS')
        specs_title.add_css_class('card-title')
        specs_title.set_halign(Gtk.Align.START)
        specs_card.append(specs_title)

        tier_specs = {
            'power-saver': [
                ('Blur Radius', '8px'),
                ('Transitions', '150ms'),
                ('Animations', 'Simple fades'),
                ('Particles', 'Disabled'),
                ('Shadows', 'Low quality'),
            ],
            'balanced': [
                ('Blur Radius', '20px'),
                ('Transitions', '300ms'),
                ('Animations', 'Standard Beeta'),
                ('Particles', 'Disabled'),
                ('Shadows', 'Medium quality'),
            ],
            'performance': [
                ('Blur Radius', '28px'),
                ('Transitions', '400ms'),
                ('Animations', 'Full + ambient'),
                ('Particles', 'Enabled'),
                ('Shadows', 'High quality'),
            ],
        }

        specs = tier_specs.get(current_mode, tier_specs['balanced'])
        for key, value in specs:
            row = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL,
                margin_top=6, margin_bottom=6,
            )
            key_lbl = Gtk.Label(label=key)
            key_lbl.add_css_class('card-row-sublabel')
            key_lbl.set_halign(Gtk.Align.START)
            key_lbl.set_hexpand(True)
            row.append(key_lbl)

            val_lbl = Gtk.Label(label=value)
            val_lbl.add_css_class('card-row-label')
            val_lbl.set_halign(Gtk.Align.END)
            row.append(val_lbl)

            specs_card.append(row)

        self.append(specs_card)

    def _make_switch_row(
        self, label: str, sublabel: str, default: bool
    ) -> Gtk.Box:
        """Create a setting row with label + switch."""
        row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
        )
        row.add_css_class('card-row')

        text_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=2,
        )
        text_box.set_hexpand(True)

        lbl = Gtk.Label(label=label)
        lbl.add_css_class('card-row-label')
        lbl.set_halign(Gtk.Align.START)
        text_box.append(lbl)

        sub = Gtk.Label(label=sublabel)
        sub.add_css_class('card-row-sublabel')
        sub.set_halign(Gtk.Align.START)
        sub.set_wrap(True)
        sub.set_max_width_chars(40)
        text_box.append(sub)

        row.append(text_box)

        switch = Gtk.Switch()
        switch.set_active(default)
        switch.set_valign(Gtk.Align.CENTER)
        row.append(switch)

        return row

    def _on_mode_change(self, button: Gtk.Button, mode: str) -> None:
        """Handle performance mode change."""
        for m, btn in self._mode_buttons.items():
            if m == mode:
                btn.add_css_class('active')
            else:
                btn.remove_css_class('active')
        self._config.set('Desktop', 'performance_mode', mode)
