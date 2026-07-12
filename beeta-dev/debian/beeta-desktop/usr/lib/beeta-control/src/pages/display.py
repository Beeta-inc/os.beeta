# -*- coding: utf-8 -*-
# Beeta Desktop Environment
# Copyright (C) 2023-2026 Beeta Technologies Inc.
# Licensed under GNU General Public License v3.0

"""Display settings page — resolution, scaling, night light."""

from __future__ import annotations

import subprocess
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk


class DisplayPage(Gtk.Box):
    """Display settings with resolution, scale, and night light."""

    def __init__(self, config) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._config = config
        self._build_page()

    def _build_page(self) -> None:
        title = Gtk.Label(label='Display')
        title.add_css_class('page-title')
        title.set_halign(Gtk.Align.START)
        self.append(title)

        subtitle = Gtk.Label(label='Screen resolution, scaling, and color temperature')
        subtitle.add_css_class('page-subtitle')
        subtitle.set_halign(Gtk.Align.START)
        self.append(subtitle)

        # ── Monitor Info ──
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        card.add_css_class('settings-card')
        ct = Gtk.Label(label='DISPLAY')
        ct.add_css_class('card-title')
        ct.set_halign(Gtk.Align.START)
        card.append(ct)

        display = Gdk.Display.get_default()
        monitors = display.get_monitors() if display else None
        if monitors and monitors.get_n_items() > 0:
            monitor = monitors.get_item(0)
            geo = monitor.get_geometry()
            info_text = f'{geo.width}×{geo.height}'
            refresh = monitor.get_refresh_rate()
            if refresh > 0:
                info_text += f' @ {refresh / 1000:.0f}Hz'
            mfg = monitor.get_manufacturer() or ''
            model = monitor.get_model() or ''
            if mfg or model:
                info_text = f'{mfg} {model} — {info_text}'.strip()
        else:
            info_text = 'Display information unavailable'

        info_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        info_row.add_css_class('card-row')
        info_icon = Gtk.Label(label='🖵')
        info_icon.set_markup('<span size="xx-large">🖵</span>')
        info_row.append(info_icon)
        info_lbl = Gtk.Label(label=info_text)
        info_lbl.add_css_class('card-row-label')
        info_lbl.set_halign(Gtk.Align.START)
        info_row.append(info_lbl)
        card.append(info_row)
        self.append(card)

        # ── Scaling ──
        scale_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        scale_card.add_css_class('settings-card')
        st = Gtk.Label(label='SCALING')
        st.add_css_class('card-title')
        st.set_halign(Gtk.Align.START)
        scale_card.append(st)

        scale_row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        scale_row.add_css_class('card-row')
        scale_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        sl = Gtk.Label(label='Interface Scale')
        sl.add_css_class('card-row-label')
        sl.set_halign(Gtk.Align.START)
        sl.set_hexpand(True)
        scale_header.append(sl)
        self._scale_val = Gtk.Label(label='100%')
        self._scale_val.add_css_class('slider-value')
        scale_header.append(self._scale_val)
        scale_row.append(scale_header)

        scale_slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 100, 200, 25)
        scale_slider.set_value(100)
        scale_slider.set_draw_value(False)
        scale_slider.add_css_class('beeta-slider')
        scale_slider.connect('value-changed', lambda s: self._scale_val.set_text(f'{int(s.get_value())}%'))
        scale_row.append(scale_slider)
        scale_card.append(scale_row)
        self.append(scale_card)

        # ── Night Light ──
        nl_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        nl_card.add_css_class('settings-card')
        nt = Gtk.Label(label='NIGHT LIGHT')
        nt.add_css_class('card-title')
        nt.set_halign(Gtk.Align.START)
        nl_card.append(nt)

        nl_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        nl_row.add_css_class('card-row')
        nl_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        nl_text.set_hexpand(True)
        nl_lbl = Gtk.Label(label='Enable Night Light')
        nl_lbl.add_css_class('card-row-label')
        nl_lbl.set_halign(Gtk.Align.START)
        nl_text.append(nl_lbl)
        nl_sub = Gtk.Label(label='Reduce blue light in the evening to help you sleep')
        nl_sub.add_css_class('card-row-sublabel')
        nl_sub.set_halign(Gtk.Align.START)
        nl_sub.set_wrap(True)
        nl_sub.set_max_width_chars(40)
        nl_text.append(nl_sub)
        nl_row.append(nl_text)
        nl_switch = Gtk.Switch()
        nl_switch.set_valign(Gtk.Align.CENTER)
        nl_row.append(nl_switch)
        nl_card.append(nl_row)

        sep = Gtk.Box()
        sep.add_css_class('card-separator')
        nl_card.append(sep)

        # Color temperature slider
        temp_row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        temp_row.add_css_class('card-row')
        temp_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        temp_lbl = Gtk.Label(label='Color Temperature')
        temp_lbl.add_css_class('card-row-label')
        temp_lbl.set_halign(Gtk.Align.START)
        temp_lbl.set_hexpand(True)
        temp_header.append(temp_lbl)
        self._temp_val = Gtk.Label(label='4500K')
        self._temp_val.add_css_class('slider-value')
        temp_header.append(self._temp_val)
        temp_row.append(temp_header)

        temp_slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 2700, 6500, 100)
        temp_slider.set_value(4500)
        temp_slider.set_draw_value(False)
        temp_slider.add_css_class('beeta-slider')
        temp_slider.connect('value-changed', lambda s: self._temp_val.set_text(f'{int(s.get_value())}K'))
        temp_row.append(temp_slider)
        nl_card.append(temp_row)

        self.append(nl_card)
