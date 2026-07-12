# -*- coding: utf-8 -*-
# Beeta Desktop Environment
# Copyright (C) 2023-2026 Beeta Technologies Inc.
# Licensed under GNU General Public License v3.0

"""Network settings page — Wi-Fi and Bluetooth."""

from __future__ import annotations

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gio, GLib


class NetworkPage(Gtk.Box):
    """Network settings — Wi-Fi networks and Bluetooth devices."""

    def __init__(self, config) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._config = config
        self._build_page()

    def _build_page(self) -> None:
        title = Gtk.Label(label='Network')
        title.add_css_class('page-title')
        title.set_halign(Gtk.Align.START)
        self.append(title)

        subtitle = Gtk.Label(label='Wi-Fi, Bluetooth, and connectivity')
        subtitle.add_css_class('page-subtitle')
        subtitle.set_halign(Gtk.Align.START)
        self.append(subtitle)

        # ── Wi-Fi ──
        wifi_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        wifi_card.add_css_class('settings-card')

        wifi_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        wifi_title = Gtk.Label(label='WI-FI')
        wifi_title.add_css_class('card-title')
        wifi_title.set_halign(Gtk.Align.START)
        wifi_title.set_hexpand(True)
        wifi_header.append(wifi_title)
        wifi_switch = Gtk.Switch()
        wifi_switch.set_active(True)
        wifi_switch.set_valign(Gtk.Align.CENTER)
        wifi_header.append(wifi_switch)
        wifi_card.append(wifi_header)

        # Available networks list
        self._wifi_list = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=4,
            margin_top=12,
        )

        # Load networks
        self._load_wifi_networks()

        wifi_card.append(self._wifi_list)
        self.append(wifi_card)

        # ── Bluetooth ──
        bt_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        bt_card.add_css_class('settings-card')

        bt_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        bt_title = Gtk.Label(label='BLUETOOTH')
        bt_title.add_css_class('card-title')
        bt_title.set_halign(Gtk.Align.START)
        bt_title.set_hexpand(True)
        bt_header.append(bt_title)
        bt_switch = Gtk.Switch()
        bt_switch.set_active(False)
        bt_switch.set_valign(Gtk.Align.CENTER)
        bt_header.append(bt_switch)
        bt_card.append(bt_header)

        bt_desc = Gtk.Label(label='No devices paired')
        bt_desc.add_css_class('card-row-sublabel')
        bt_desc.set_halign(Gtk.Align.START)
        bt_desc.set_margin_top(12)
        bt_card.append(bt_desc)

        self.append(bt_card)

        # ── VPN ──
        vpn_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        vpn_card.add_css_class('settings-card')

        vpn_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        vpn_title = Gtk.Label(label='VPN')
        vpn_title.add_css_class('card-title')
        vpn_title.set_halign(Gtk.Align.START)
        vpn_title.set_hexpand(True)
        vpn_header.append(vpn_title)
        vpn_card.append(vpn_header)

        vpn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        vpn_row.add_css_class('card-row')
        vpn_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        vpn_text.set_hexpand(True)
        vpn_lbl = Gtk.Label(label='No VPN configured')
        vpn_lbl.add_css_class('card-row-label')
        vpn_lbl.set_halign(Gtk.Align.START)
        vpn_text.append(vpn_lbl)
        vpn_sub = Gtk.Label(label='Add a VPN connection for secure browsing')
        vpn_sub.add_css_class('card-row-sublabel')
        vpn_sub.set_halign(Gtk.Align.START)
        vpn_text.append(vpn_sub)
        vpn_row.append(vpn_text)

        vpn_btn = Gtk.Button(label='Add VPN')
        vpn_btn.add_css_class('beeta-btn')
        vpn_btn.add_css_class('beeta-btn-secondary')
        vpn_btn.set_valign(Gtk.Align.CENTER)
        vpn_row.append(vpn_btn)
        vpn_card.append(vpn_row)

        self.append(vpn_card)

    def _load_wifi_networks(self) -> None:
        """Load Wi-Fi networks from NetworkManager via D-Bus."""
        # Try to get current connection
        try:
            bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
            nm = Gio.DBusProxy.new_sync(
                bus, Gio.DBusProxyFlags.NONE, None,
                'org.freedesktop.NetworkManager',
                '/org/freedesktop/NetworkManager',
                'org.freedesktop.NetworkManager',
                None,
            )
            state = nm.get_cached_property('State')
            is_connected = state and state.get_uint32() >= 60

            # Add current connection
            if is_connected:
                active = nm.get_cached_property('ActiveConnections')
                if active:
                    for conn_path in active.unpack():
                        self._add_wifi_item(bus, conn_path, True)
                        break

            # Add placeholder networks for demo
            for ssid, strength, secured in [
                ('Neighbor-5G', 72, True),
                ('CoffeeShop_Free', 45, False),
                ('Office-Network', 38, True),
            ]:
                item = self._make_network_item(ssid, strength, secured, False)
                self._wifi_list.append(item)

        except Exception:
            # NM not available; show placeholder
            placeholder = Gtk.Label(label='NetworkManager not available')
            placeholder.add_css_class('card-row-sublabel')
            placeholder.set_halign(Gtk.Align.START)
            self._wifi_list.append(placeholder)

    def _add_wifi_item(self, bus, conn_path: str, connected: bool) -> None:
        """Add a Wi-Fi network item from an active connection path."""
        try:
            conn = Gio.DBusProxy.new_sync(
                bus, Gio.DBusProxyFlags.NONE, None,
                'org.freedesktop.NetworkManager',
                conn_path,
                'org.freedesktop.NetworkManager.Connection.Active',
                None,
            )
            name_var = conn.get_cached_property('Id')
            ssid = name_var.get_string() if name_var else 'Unknown'
            item = self._make_network_item(ssid, 90, True, connected)
            self._wifi_list.append(item)
        except Exception:
            pass

    @staticmethod
    def _make_network_item(
        ssid: str, strength: int, secured: bool, connected: bool
    ) -> Gtk.Box:
        """Create a Wi-Fi network list item."""
        item = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        item.add_css_class('network-item')
        if connected:
            item.add_css_class('connected')

        # Signal strength bars
        signal_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=1, valign=Gtk.Align.CENTER)
        bars = 4
        filled = max(1, int(strength / 25))
        for i in range(bars):
            bar = Gtk.Box()
            bar.add_css_class('signal-bar')
            bar.set_size_request(3, 6 + (i * 3))
            if i < filled:
                bar.add_css_class('filled')
            signal_box.append(bar)
        item.append(signal_box)

        # SSID + status
        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        text_box.set_hexpand(True)
        name = Gtk.Label(label=ssid)
        name.add_css_class('network-ssid')
        name.set_halign(Gtk.Align.START)
        text_box.append(name)

        status_parts = []
        if connected:
            status_parts.append('Connected')
        if secured:
            status_parts.append('🔒 Secured')
        else:
            status_parts.append('Open')
        status = Gtk.Label(label=' · '.join(status_parts))
        status.add_css_class('network-status')
        status.set_halign(Gtk.Align.START)
        text_box.append(status)
        item.append(text_box)

        if not connected:
            connect_btn = Gtk.Button(label='Connect')
            connect_btn.add_css_class('beeta-btn')
            connect_btn.add_css_class('beeta-btn-secondary')
            connect_btn.set_valign(Gtk.Align.CENTER)
            item.append(connect_btn)

        return item
