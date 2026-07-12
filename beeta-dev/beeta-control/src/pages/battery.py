# -*- coding: utf-8 -*-
# Beeta Desktop Environment
# Copyright (C) 2023-2026 Beeta Technologies Inc.
# Licensed under GNU General Public License v3.0

"""Battery settings page — power profiles and charging configuration."""

from __future__ import annotations

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gio, GLib


class BatteryPage(Gtk.Box):
    """Battery settings with live level display, charging config, and power profiles."""

    def __init__(self, config) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._config = config
        self._battery_level = 100
        self._is_charging = False
        self._charge_rate = 0.0
        self._build_page()
        self._start_battery_monitor()

    def _build_page(self) -> None:
        title = Gtk.Label(label='Battery')
        title.add_css_class('page-title')
        title.set_halign(Gtk.Align.START)
        self.append(title)

        subtitle = Gtk.Label(label='Power management and charging')
        subtitle.add_css_class('page-subtitle')
        subtitle.set_halign(Gtk.Align.START)
        self.append(subtitle)

        # ── Battery Status Card ──
        status_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        status_card.add_css_class('settings-card')

        status_title = Gtk.Label(label='BATTERY STATUS')
        status_title.add_css_class('card-title')
        status_title.set_halign(Gtk.Align.START)
        status_card.append(status_title)

        status_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=24,
            margin_top=8,
        )

        # Battery gauge (large text display)
        gauge_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=4,
            valign=Gtk.Align.CENTER,
        )
        gauge_box.add_css_class('battery-gauge')

        self._level_label = Gtk.Label(label='100%')
        self._level_label.add_css_class('battery-level-text')
        gauge_box.append(self._level_label)

        self._status_label = Gtk.Label(label='Fully charged')
        self._status_label.add_css_class('battery-status-text')
        gauge_box.append(self._status_label)

        status_row.append(gauge_box)

        # Battery info
        info_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
            valign=Gtk.Align.CENTER,
        )
        info_box.set_hexpand(True)

        for key, val_id in [
            ('Charge Rate', '_rate_lbl'),
            ('Time Remaining', '_time_lbl'),
            ('Battery Health', '_health_lbl'),
            ('Cycle Count', '_cycle_lbl'),
        ]:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            k = Gtk.Label(label=key)
            k.add_css_class('about-info-key')
            k.set_halign(Gtk.Align.START)
            k.set_hexpand(True)
            row.append(k)

            v = Gtk.Label(label='—')
            v.add_css_class('about-info-value')
            v.set_halign(Gtk.Align.END)
            row.append(v)
            setattr(self, val_id, v)

            info_box.append(row)

        status_row.append(info_box)
        status_card.append(status_row)

        # Progress bar
        self._progress = Gtk.ProgressBar()
        self._progress.set_fraction(1.0)
        self._progress.add_css_class('beeta-slider')
        self._progress.set_margin_top(16)
        status_card.append(self._progress)

        self.append(status_card)

        # ── Charging Preferences ──
        charge_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        charge_card.add_css_class('settings-card')
        charge_title = Gtk.Label(label='CHARGING')
        charge_title.add_css_class('card-title')
        charge_title.set_halign(Gtk.Align.START)
        charge_card.append(charge_title)

        # Turbo Charge threshold
        turbo_row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        turbo_row.add_css_class('card-row')
        turbo_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        turbo_lbl = Gtk.Label(label='Turbo Charge™ Threshold')
        turbo_lbl.add_css_class('card-row-label')
        turbo_lbl.set_halign(Gtk.Align.START)
        turbo_lbl.set_hexpand(True)
        turbo_header.append(turbo_lbl)
        self._turbo_val = Gtk.Label(label=f'{self._config.turbo_charge_min_watts}W')
        self._turbo_val.add_css_class('slider-value')
        turbo_header.append(self._turbo_val)
        turbo_row.append(turbo_header)

        turbo_sub = Gtk.Label(label='Minimum wattage to display Beeta® Turbo Charge™ Active')
        turbo_sub.add_css_class('card-row-sublabel')
        turbo_sub.set_halign(Gtk.Align.START)
        turbo_row.append(turbo_sub)

        turbo_slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 20, 100, 5)
        turbo_slider.set_value(self._config.turbo_charge_min_watts)
        turbo_slider.set_draw_value(False)
        turbo_slider.add_css_class('beeta-slider')
        turbo_slider.connect('value-changed', self._on_turbo_changed)
        turbo_row.append(turbo_slider)
        charge_card.append(turbo_row)

        sep = Gtk.Box()
        sep.add_css_class('card-separator')
        charge_card.append(sep)

        # Fast Charge threshold
        fast_row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        fast_row.add_css_class('card-row')
        fast_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        fast_lbl = Gtk.Label(label='Fast Charging Threshold')
        fast_lbl.add_css_class('card-row-label')
        fast_lbl.set_halign(Gtk.Align.START)
        fast_lbl.set_hexpand(True)
        fast_header.append(fast_lbl)
        self._fast_val = Gtk.Label(label=f'{self._config.fast_charge_min_watts}W')
        self._fast_val.add_css_class('slider-value')
        fast_header.append(self._fast_val)
        fast_row.append(fast_header)

        fast_slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 5, 45, 5)
        fast_slider.set_value(self._config.fast_charge_min_watts)
        fast_slider.set_draw_value(False)
        fast_slider.add_css_class('beeta-slider')
        fast_slider.connect('value-changed', self._on_fast_changed)
        fast_row.append(fast_slider)
        charge_card.append(fast_row)

        sep2 = Gtk.Box()
        sep2.add_css_class('card-separator')
        charge_card.append(sep2)

        # Show charge label toggle
        charge_label_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        charge_label_row.add_css_class('card-row')
        cl_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        cl_text.set_hexpand(True)
        cl_lbl = Gtk.Label(label='Show charging label')
        cl_lbl.add_css_class('card-row-label')
        cl_lbl.set_halign(Gtk.Align.START)
        cl_text.append(cl_lbl)
        cl_sub = Gtk.Label(label='Display "Turbo Charge™ Active" or "Fast Charging" in top bar')
        cl_sub.add_css_class('card-row-sublabel')
        cl_sub.set_halign(Gtk.Align.START)
        cl_sub.set_wrap(True)
        cl_sub.set_max_width_chars(40)
        cl_text.append(cl_sub)
        charge_label_row.append(cl_text)
        cl_switch = Gtk.Switch()
        cl_switch.set_active(True)
        cl_switch.set_valign(Gtk.Align.CENTER)
        charge_label_row.append(cl_switch)
        charge_card.append(charge_label_row)

        self.append(charge_card)

    def _start_battery_monitor(self) -> None:
        """Connect to UPower via D-Bus to read battery state."""
        try:
            bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
            proxy = Gio.DBusProxy.new_sync(
                bus, Gio.DBusProxyFlags.NONE, None,
                'org.freedesktop.UPower',
                '/org/freedesktop/UPower/devices/battery_BAT0',
                'org.freedesktop.UPower.Device',
                None,
            )

            pct = proxy.get_cached_property('Percentage')
            if pct:
                self._battery_level = int(pct.get_double())

            state = proxy.get_cached_property('State')
            if state:
                self._is_charging = state.get_uint32() == 1

            rate = proxy.get_cached_property('EnergyRate')
            if rate:
                self._charge_rate = abs(rate.get_double())

            time_to = proxy.get_cached_property('TimeToEmpty')
            time_full = proxy.get_cached_property('TimeToFull')

            self._update_display(time_to, time_full)

            proxy.connect('g-properties-changed', self._on_props_changed)
        except Exception:
            self._level_label.set_text('—')
            self._status_label.set_text('Battery not detected')

    def _update_display(self, time_to=None, time_full=None) -> None:
        """Refresh the battery display."""
        level = self._battery_level
        self._level_label.set_text(f'{level}%')
        self._progress.set_fraction(level / 100.0)

        if self._is_charging:
            turbo = self._config.turbo_charge_min_watts
            fast = self._config.fast_charge_min_watts
            if self._charge_rate >= turbo:
                self._status_label.set_text('⚡ Beeta® Turbo Charge™ Active')
            elif self._charge_rate >= fast:
                self._status_label.set_text('⚡ Fast Charging')
            else:
                self._status_label.set_text('⚡ Charging')
            self._status_label.remove_css_class('discharging')
            self._status_label.remove_css_class('low')
        elif level <= 10:
            self._status_label.set_text('⚠ Critically Low')
            self._status_label.add_css_class('low')
        elif level <= 20:
            self._status_label.set_text('Low Battery')
            self._status_label.add_css_class('low')
        elif level >= 95:
            self._status_label.set_text('Fully Charged')
            self._status_label.remove_css_class('low')
        else:
            self._status_label.set_text('On Battery')
            self._status_label.add_css_class('discharging')
            self._status_label.remove_css_class('low')

        self._rate_lbl.set_text(f'{self._charge_rate:.1f}W' if self._charge_rate > 0 else '—')

        # Time remaining
        if time_to and not self._is_charging:
            secs = time_to.get_int64() if hasattr(time_to, 'get_int64') else 0
            if secs > 0:
                hrs = secs // 3600
                mins = (secs % 3600) // 60
                self._time_lbl.set_text(f'{hrs}h {mins}m')
            else:
                self._time_lbl.set_text('—')
        elif time_full and self._is_charging:
            secs = time_full.get_int64() if hasattr(time_full, 'get_int64') else 0
            if secs > 0:
                hrs = secs // 3600
                mins = (secs % 3600) // 60
                self._time_lbl.set_text(f'{hrs}h {mins}m to full')
            else:
                self._time_lbl.set_text('—')
        else:
            self._time_lbl.set_text('—')

        self._health_lbl.set_text('Good')
        self._cycle_lbl.set_text('—')

    def _on_props_changed(self, proxy, changed, invalidated) -> None:
        pct = proxy.get_cached_property('Percentage')
        if pct:
            self._battery_level = int(pct.get_double())
        state = proxy.get_cached_property('State')
        if state:
            self._is_charging = state.get_uint32() == 1
        rate = proxy.get_cached_property('EnergyRate')
        if rate:
            self._charge_rate = abs(rate.get_double())
        time_to = proxy.get_cached_property('TimeToEmpty')
        time_full = proxy.get_cached_property('TimeToFull')
        self._update_display(time_to, time_full)

    def _on_turbo_changed(self, slider: Gtk.Scale) -> None:
        val = int(slider.get_value())
        self._turbo_val.set_text(f'{val}W')
        self._config.set('Battery', 'turbo_charge_min_watts', str(val))

    def _on_fast_changed(self, slider: Gtk.Scale) -> None:
        val = int(slider.get_value())
        self._fast_val.set_text(f'{val}W')
        self._config.set('Battery', 'fast_charge_min_watts', str(val))
