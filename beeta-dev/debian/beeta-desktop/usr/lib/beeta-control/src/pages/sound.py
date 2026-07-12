# -*- coding: utf-8 -*-
# Beeta Desktop Environment
# Copyright (C) 2023-2026 Beeta Technologies Inc.
# Licensed under GNU General Public License v3.0

"""Sound settings page — volume, output devices, alert sounds."""

from __future__ import annotations

import subprocess
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk


class SoundPage(Gtk.Box):
    """Sound settings with volume control and device selection."""

    def __init__(self, config) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._config = config
        self._build_page()

    def _build_page(self) -> None:
        title = Gtk.Label(label='Sound')
        title.add_css_class('page-title')
        title.set_halign(Gtk.Align.START)
        self.append(title)

        subtitle = Gtk.Label(label='Audio output, input, and system sounds')
        subtitle.add_css_class('page-subtitle')
        subtitle.set_halign(Gtk.Align.START)
        self.append(subtitle)

        # ── Output Volume ──
        out_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        out_card.add_css_class('settings-card')
        out_title = Gtk.Label(label='OUTPUT')
        out_title.add_css_class('card-title')
        out_title.set_halign(Gtk.Align.START)
        out_card.append(out_title)

        vol_row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        vol_row.add_css_class('card-row')
        vol_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        vol_icon = Gtk.Label(label='🔊')
        vol_icon.set_margin_end(8)
        vol_header.append(vol_icon)
        vol_lbl = Gtk.Label(label='Volume')
        vol_lbl.add_css_class('card-row-label')
        vol_lbl.set_halign(Gtk.Align.START)
        vol_lbl.set_hexpand(True)
        vol_header.append(vol_lbl)
        self._vol_val = Gtk.Label(label='50%')
        self._vol_val.add_css_class('slider-value')
        vol_header.append(self._vol_val)
        vol_row.append(vol_header)

        vol_slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 150, 1)
        vol_slider.set_value(50)
        vol_slider.set_draw_value(False)
        vol_slider.add_css_class('beeta-slider')
        vol_slider.connect('value-changed', self._on_volume_changed)

        # Read current volume
        self._read_volume(vol_slider)
        vol_row.append(vol_slider)
        out_card.append(vol_row)
        self.append(out_card)

        # ── Input ──
        in_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        in_card.add_css_class('settings-card')
        in_title = Gtk.Label(label='INPUT')
        in_title.add_css_class('card-title')
        in_title.set_halign(Gtk.Align.START)
        in_card.append(in_title)

        mic_row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        mic_row.add_css_class('card-row')
        mic_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        mic_icon = Gtk.Label(label='🎤')
        mic_icon.set_margin_end(8)
        mic_header.append(mic_icon)
        mic_lbl = Gtk.Label(label='Microphone Volume')
        mic_lbl.add_css_class('card-row-label')
        mic_lbl.set_halign(Gtk.Align.START)
        mic_lbl.set_hexpand(True)
        mic_header.append(mic_lbl)
        self._mic_val = Gtk.Label(label='100%')
        self._mic_val.add_css_class('slider-value')
        mic_header.append(self._mic_val)
        mic_row.append(mic_header)

        mic_slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        mic_slider.set_value(100)
        mic_slider.set_draw_value(False)
        mic_slider.add_css_class('beeta-slider')
        mic_slider.connect('value-changed', lambda s: self._mic_val.set_text(f'{int(s.get_value())}%'))
        mic_row.append(mic_slider)
        in_card.append(mic_row)
        self.append(in_card)

        # ── System Sounds ──
        sys_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        sys_card.add_css_class('settings-card')
        sys_title = Gtk.Label(label='SYSTEM SOUNDS')
        sys_title.add_css_class('card-title')
        sys_title.set_halign(Gtk.Align.START)
        sys_card.append(sys_title)

        for label, sublabel, default in [
            ('Alert sounds', 'Play sounds for notifications and alerts', True),
            ('UI feedback sounds', 'Subtle clicks and taps for interactions', False),
            ('Startup sound', 'Play a sound when Beeta OS starts', True),
        ]:
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
            sw = Gtk.Switch()
            sw.set_active(default)
            sw.set_valign(Gtk.Align.CENTER)
            row.append(sw)
            sys_card.append(row)
            sep = Gtk.Box()
            sep.add_css_class('card-separator')
            sys_card.append(sep)

        self.append(sys_card)

    def _read_volume(self, slider: Gtk.Scale) -> None:
        try:
            result = subprocess.run(
                ['pactl', 'get-sink-volume', '@DEFAULT_SINK@'],
                capture_output=True, text=True, timeout=2,
            )
            if result.returncode == 0:
                for part in result.stdout.split('/'):
                    part = part.strip()
                    if part.endswith('%'):
                        vol = int(part.rstrip('%').strip())
                        slider.set_value(vol)
                        self._vol_val.set_text(f'{vol}%')
                        break
        except Exception:
            pass

    def _on_volume_changed(self, slider: Gtk.Scale) -> None:
        vol = int(slider.get_value())
        self._vol_val.set_text(f'{vol}%')
        try:
            subprocess.Popen(
                ['pactl', 'set-sink-volume', '@DEFAULT_SINK@', f'{vol}%'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass
