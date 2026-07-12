# -*- coding: utf-8 -*-
# Beeta Desktop Environment
# Copyright (C) 2023-2026 Beeta Technologies Inc.
# Licensed under GNU General Public License v3.0

"""Desktop settings page — workspace, bar, and dock configuration."""

from __future__ import annotations

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk


class DesktopPage(Gtk.Box):
    """Desktop settings — workspaces, bar behavior, dock customization."""

    def __init__(self, config) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._config = config
        self._build_page()

    def _build_page(self) -> None:
        title = Gtk.Label(label='Desktop')
        title.add_css_class('page-title')
        title.set_halign(Gtk.Align.START)
        self.append(title)

        subtitle = Gtk.Label(label='Configure your workspace and panels')
        subtitle.add_css_class('page-subtitle')
        subtitle.set_halign(Gtk.Align.START)
        self.append(subtitle)

        # ── Workspaces ──
        ws_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        ws_card.add_css_class('settings-card')

        ws_title = Gtk.Label(label='WORKSPACES')
        ws_title.add_css_class('card-title')
        ws_title.set_halign(Gtk.Align.START)
        ws_card.append(ws_title)

        ws_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        ws_row.add_css_class('card-row')
        ws_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        ws_text.set_hexpand(True)
        lbl = Gtk.Label(label='Number of workspaces')
        lbl.add_css_class('card-row-label')
        lbl.set_halign(Gtk.Align.START)
        ws_text.append(lbl)
        sub = Gtk.Label(label='Virtual desktop spaces accessible via top bar dots')
        sub.add_css_class('card-row-sublabel')
        sub.set_halign(Gtk.Align.START)
        ws_text.append(sub)
        ws_row.append(ws_text)

        ws_spin = Gtk.SpinButton.new_with_range(1, 10, 1)
        ws_spin.set_value(self._config.workspaces)
        ws_spin.set_valign(Gtk.Align.CENTER)
        ws_spin.connect('value-changed', lambda s: self._config.set('Desktop', 'workspaces', str(int(s.get_value()))))
        ws_row.append(ws_spin)
        ws_card.append(ws_row)
        self.append(ws_card)

        # ── Top Bar ──
        tb_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        tb_card.add_css_class('settings-card')
        tb_title = Gtk.Label(label='TOP BAR')
        tb_title.add_css_class('card-title')
        tb_title.set_halign(Gtk.Align.START)
        tb_card.append(tb_title)

        tb_card.append(self._make_switch_row('Show workspace dots', 'Display workspace indicator dots on the left', True))
        tb_card.append(self._make_sep())
        tb_card.append(self._make_switch_row('Show Live Center', 'Dynamic status hub in the center', True))
        tb_card.append(self._make_sep())
        tb_card.append(self._make_switch_row('Show media in Live Center', 'Display currently playing media info', self._config.get_bool('LiveCenter', 'show_media', True)))
        tb_card.append(self._make_sep())
        tb_card.append(self._make_switch_row('Show downloads in Live Center', 'Display active download progress', self._config.get_bool('LiveCenter', 'show_downloads', True)))
        self.append(tb_card)

        # ── Bottom Bar ──
        bb_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        bb_card.add_css_class('settings-card')
        bb_title = Gtk.Label(label='BOTTOM BAR')
        bb_title.add_css_class('card-title')
        bb_title.set_halign(Gtk.Align.START)
        bb_card.append(bb_title)

        bb_card.append(self._make_switch_row('Auto-hide in Focus State', 'Hide bottom bar when an app is maximized', True))
        bb_card.append(self._make_sep())
        bb_card.append(self._make_switch_row('Edge-hover reveal', 'Show bar when mouse hovers at bottom edge', True))
        self.append(bb_card)

        # ── Dock ──
        dock_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        dock_card.add_css_class('settings-card')
        dock_title = Gtk.Label(label='DOCK')
        dock_title.add_css_class('card-title')
        dock_title.set_halign(Gtk.Align.START)
        dock_card.append(dock_title)

        # Icon size slider
        size_row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        size_row.add_css_class('card-row')
        size_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        size_lbl = Gtk.Label(label='Icon Size')
        size_lbl.add_css_class('card-row-label')
        size_lbl.set_halign(Gtk.Align.START)
        size_lbl.set_hexpand(True)
        size_header.append(size_lbl)
        self._size_val = Gtk.Label(label=f'{self._config.icon_size}px')
        self._size_val.add_css_class('slider-value')
        size_header.append(self._size_val)
        size_row.append(size_header)

        size_slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 24, 96, 4)
        size_slider.set_value(self._config.icon_size)
        size_slider.set_draw_value(False)
        size_slider.add_css_class('beeta-slider')
        size_slider.connect('value-changed', self._on_icon_size)
        size_row.append(size_slider)
        dock_card.append(size_row)

        dock_card.append(self._make_sep())

        # Hover magnification slider
        mag_row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        mag_row.add_css_class('card-row')
        mag_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        mag_lbl = Gtk.Label(label='Hover Magnification')
        mag_lbl.add_css_class('card-row-label')
        mag_lbl.set_halign(Gtk.Align.START)
        mag_lbl.set_hexpand(True)
        mag_header.append(mag_lbl)
        self._mag_val = Gtk.Label(label=f'{self._config.hover_magnification:.2f}×')
        self._mag_val.add_css_class('slider-value')
        mag_header.append(self._mag_val)
        mag_row.append(mag_header)

        mag_slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1.0, 1.5, 0.05)
        mag_slider.set_value(self._config.hover_magnification)
        mag_slider.set_draw_value(False)
        mag_slider.add_css_class('beeta-slider')
        mag_slider.connect('value-changed', self._on_magnification)
        mag_row.append(mag_slider)
        dock_card.append(mag_row)

        self.append(dock_card)

    def _make_switch_row(self, label: str, sublabel: str, default: bool) -> Gtk.Box:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        row.add_css_class('card-row')
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        text.set_hexpand(True)
        l = Gtk.Label(label=label)
        l.add_css_class('card-row-label')
        l.set_halign(Gtk.Align.START)
        text.append(l)
        s = Gtk.Label(label=sublabel)
        s.add_css_class('card-row-sublabel')
        s.set_halign(Gtk.Align.START)
        s.set_wrap(True)
        s.set_max_width_chars(40)
        text.append(s)
        row.append(text)
        switch = Gtk.Switch()
        switch.set_active(default)
        switch.set_valign(Gtk.Align.CENTER)
        row.append(switch)
        return row

    @staticmethod
    def _make_sep() -> Gtk.Box:
        s = Gtk.Box()
        s.add_css_class('card-separator')
        return s

    def _on_icon_size(self, slider: Gtk.Scale) -> None:
        val = int(slider.get_value())
        self._size_val.set_text(f'{val}px')
        self._config.set('Dock', 'icon_size', str(val))

    def _on_magnification(self, slider: Gtk.Scale) -> None:
        val = slider.get_value()
        self._mag_val.set_text(f'{val:.2f}×')
        self._config.set('Dock', 'hover_magnification', str(val))
