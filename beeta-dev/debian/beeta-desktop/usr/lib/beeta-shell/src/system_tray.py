# -*- coding: utf-8 -*-
# Beeta Desktop Environment
# Copyright (C) 2023-2026 Beeta Technologies Inc.
# Licensed under GNU General Public License v3.0

"""System tray widget for the Beeta Shell top bar.

Provides real-time system indicators via D-Bus:
    - Battery level + charging state (UPower)
    - Wi-Fi status + signal strength (NetworkManager)
    - Bluetooth on/off (Bluez)
    - Volume level (PulseAudio/PipeWire)

Charging labels adapt based on charge rate:
    ≥45W → "Beeta® Turbo Charge™ Active"
    ≥15W → "Fast Charging"
    <15W → "Charging"

Click the tray to open a Quick Settings popover with toggles
and sliders for all system controls.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib, Gio, GObject

if TYPE_CHECKING:
    from .config import BeetaConfig
    from .adaptive_motion import AdaptiveMotion
    from .adaptive_nature import AdaptiveNature


class SystemTray(Gtk.Box):
    """System tray with battery, Wi-Fi, Bluetooth, and volume indicators.

    All system state is read from D-Bus services. When a service is
    unavailable, the corresponding indicator gracefully hides rather
    than showing an error.

    Signals:
        battery-changed(level: int, charging: bool, rate: float):
            Emitted when battery state changes. Used by Adaptive Nature
            and Adaptive Motion to adjust behavior.

        quick-settings-toggled(visible: bool):
            Emitted when the Quick Settings popover is opened/closed.
    """

    __gsignals__ = {
        'battery-changed': (
            GObject.SignalFlags.RUN_FIRST, None, (int, bool, float)
        ),
        'quick-settings-toggled': (
            GObject.SignalFlags.RUN_FIRST, None, (bool,)
        ),
    }

    def __init__(
        self,
        config: BeetaConfig,
        adaptive_motion: AdaptiveMotion,
    ) -> None:
        super().__init__(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=2,
            valign=Gtk.Align.CENTER,
            halign=Gtk.Align.END,
        )
        self.add_css_class('system-tray')

        self._config = config
        self._motion = adaptive_motion

        # State
        self._battery_level: int = 100
        self._is_charging: bool = False
        self._charge_rate: float = 0.0
        self._wifi_connected: bool = False
        self._wifi_strength: int = 0
        self._wifi_ssid: str = ''
        self._bluetooth_on: bool = False
        self._volume_level: int = 50
        self._volume_muted: bool = False

        # D-Bus proxies
        self._upower_proxy: Optional[Gio.DBusProxy] = None
        self._nm_proxy: Optional[Gio.DBusProxy] = None

        # Build UI
        self._build_indicators()
        self._build_quick_settings()

        # Start D-Bus monitors
        self._start_upower_monitor()
        self._start_networkmanager_monitor()
        self._start_volume_monitor()

    # ── Properties ───────────────────────────────────────────────

    @property
    def battery_level(self) -> int:
        """Current battery percentage (0-100)."""
        return self._battery_level

    @property
    def is_charging(self) -> bool:
        """Whether the battery is currently charging."""
        return self._is_charging

    @property
    def charge_rate_watts(self) -> float:
        """Current charge rate in watts."""
        return self._charge_rate

    @property
    def wifi_connected(self) -> bool:
        """Whether Wi-Fi is connected."""
        return self._wifi_connected

    @property
    def wifi_strength(self) -> int:
        """Wi-Fi signal strength (0-100)."""
        return self._wifi_strength

    @property
    def bluetooth_on(self) -> bool:
        """Whether Bluetooth is enabled."""
        return self._bluetooth_on

    @property
    def volume_level(self) -> int:
        """Audio volume level (0-100)."""
        return self._volume_level

    # ── Internal: Build UI ───────────────────────────────────────

    def _build_indicators(self) -> None:
        """Create the tray indicator icons."""
        # Volume icon
        self._volume_icon = Gtk.Image.new_from_icon_name('audio-volume-high-symbolic')
        self._volume_icon.set_pixel_size(16)
        self._volume_icon.add_css_class('tray-icon')
        self._volume_icon.set_tooltip_text('Volume')
        self.append(self._volume_icon)

        # Bluetooth icon
        self._bt_icon = Gtk.Image.new_from_icon_name('bluetooth-active-symbolic')
        self._bt_icon.set_pixel_size(16)
        self._bt_icon.add_css_class('tray-icon')
        self._bt_icon.set_tooltip_text('Bluetooth')
        self._bt_icon.set_visible(False)  # hidden until detected
        self.append(self._bt_icon)

        # Wi-Fi icon
        self._wifi_icon = Gtk.Image.new_from_icon_name('network-wireless-signal-excellent-symbolic')
        self._wifi_icon.set_pixel_size(16)
        self._wifi_icon.add_css_class('tray-icon')
        self._wifi_icon.set_tooltip_text('Wi-Fi')
        self.append(self._wifi_icon)

        # Battery icon + percentage
        self._battery_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=4,
            valign=Gtk.Align.CENTER,
        )

        self._battery_icon = Gtk.Image.new_from_icon_name('battery-full-symbolic')
        self._battery_icon.set_pixel_size(16)
        self._battery_icon.add_css_class('tray-icon')
        self._battery_icon.add_css_class('battery-icon')
        self._battery_box.append(self._battery_icon)

        self._battery_label = Gtk.Label(label='100%')
        self._battery_label.add_css_class('tray-battery-label')
        self._battery_box.append(self._battery_label)

        # Hide battery on desktops by default
        if not self._config.is_laptop:
            self._battery_box.set_visible(False)

        self.append(self._battery_box)

        # Charge label (Turbo Charge / Fast Charging) — shown below battery
        self._charge_label = Gtk.Label()
        self._charge_label.add_css_class('charge-label')
        self._charge_label.set_visible(False)
        self.append(self._charge_label)

        # Click handler for the entire tray
        click_ctrl = Gtk.GestureClick()
        click_ctrl.connect('released', self._on_tray_clicked)
        self.add_controller(click_ctrl)

    def _build_quick_settings(self) -> None:
        """Build the Quick Settings popover."""
        self._qs_popover = Gtk.Popover()
        self._qs_popover.set_parent(self)
        self._qs_popover.set_position(Gtk.PositionType.BOTTOM)
        self._qs_popover.add_css_class('quick-settings')

        qs_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
        )

        # ── Toggle Grid ──
        toggle_grid = Gtk.Grid()
        toggle_grid.set_column_spacing(8)
        toggle_grid.set_row_spacing(8)
        toggle_grid.set_column_homogeneous(True)

        # Wi-Fi toggle
        self._qs_wifi = self._make_toggle(
            '📶', 'Wi-Fi', self._wifi_ssid or 'Disconnected',
            self._wifi_connected,
        )
        toggle_grid.attach(self._qs_wifi, 0, 0, 1, 1)

        # Bluetooth toggle
        self._qs_bt = self._make_toggle(
            '', 'Bluetooth', 'Off', False,
        )
        toggle_grid.attach(self._qs_bt, 1, 0, 1, 1)

        # Night Light toggle
        self._qs_nightlight = self._make_toggle(
            '🌙', 'Night Light', 'Off', False,
        )
        toggle_grid.attach(self._qs_nightlight, 0, 1, 1, 1)

        # Do Not Disturb toggle
        self._qs_dnd = self._make_toggle(
            '🔕', 'Do Not Disturb', 'Off', False,
        )
        toggle_grid.attach(self._qs_dnd, 1, 1, 1, 1)

        qs_box.append(toggle_grid)

        # ── Volume Slider ──
        vol_label = Gtk.Label(label='VOLUME')
        vol_label.add_css_class('qs-section-label')
        vol_label.set_halign(Gtk.Align.START)
        qs_box.append(vol_label)

        vol_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=10,
        )
        vol_icon = Gtk.Label(label='🔊')
        vol_row.append(vol_icon)

        self._qs_volume_slider = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 0, 100, 1
        )
        self._qs_volume_slider.set_value(self._volume_level)
        self._qs_volume_slider.set_hexpand(True)
        self._qs_volume_slider.add_css_class('qs-slider')
        self._qs_volume_slider.set_draw_value(False)
        self._qs_volume_slider.connect(
            'value-changed', self._on_volume_changed
        )
        vol_row.append(self._qs_volume_slider)

        qs_box.append(vol_row)

        # ── Performance Mode ──
        perf_label = Gtk.Label(label='PERFORMANCE')
        perf_label.add_css_class('qs-section-label')
        perf_label.set_halign(Gtk.Align.START)
        qs_box.append(perf_label)

        perf_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=0,
        )
        perf_row.add_css_class('qs-mode-selector')

        self._perf_buttons: dict[str, Gtk.Button] = {}
        for mode, label_text in [
            ('power-saver', '🔋 Saver'),
            ('balanced', '⚡ Balanced'),
            ('performance', '🚀 Performance'),
        ]:
            btn = Gtk.Button(label=label_text)
            btn.add_css_class('qs-mode-btn')
            if mode == self._config.performance_mode:
                btn.add_css_class('active')
            btn.connect('clicked', self._on_perf_mode_clicked, mode)
            btn.set_hexpand(True)
            perf_row.append(btn)
            self._perf_buttons[mode] = btn

        qs_box.append(perf_row)

        # ── Adaptive Nature Mode ──
        nature_label = Gtk.Label(label='ADAPTIVE NATURE')
        nature_label.add_css_class('qs-section-label')
        nature_label.set_halign(Gtk.Align.START)
        qs_box.append(nature_label)

        nature_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=0,
        )
        nature_row.add_css_class('qs-mode-selector')

        self._nature_buttons: dict[str, Gtk.Button] = {}
        for mode, label_text in [
            ('static', '🎨 Static'),
            ('adaptive', '🌤 Adaptive'),
            ('expressive', '✨ Expressive'),
        ]:
            btn = Gtk.Button(label=label_text)
            btn.add_css_class('qs-mode-btn')
            if mode == self._config.adaptive_mode:
                btn.add_css_class('active')
            btn.connect('clicked', self._on_nature_mode_clicked, mode)
            btn.set_hexpand(True)
            nature_row.append(btn)
            self._nature_buttons[mode] = btn

        qs_box.append(nature_row)

        self._qs_popover.set_child(qs_box)

    @staticmethod
    def _make_toggle(
        icon: str, label: str, sublabel: str, active: bool
    ) -> Gtk.Button:
        """Create a Quick Settings toggle button.

        Args:
            icon: Emoji icon.
            label: Primary label.
            sublabel: Secondary label.
            active: Whether the toggle is initially active.

        Returns:
            Styled toggle button.
        """
        btn = Gtk.Button()
        btn.add_css_class('qs-toggle')
        if active:
            btn.add_css_class('active')

        box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
        )

        icon_label = Gtk.Label(label=icon)
        icon_label.add_css_class('qs-toggle-icon')
        box.append(icon_label)

        text_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=1,
        )
        name_label = Gtk.Label(label=label)
        name_label.add_css_class('qs-toggle-label')
        name_label.set_halign(Gtk.Align.START)
        text_box.append(name_label)

        sub_label = Gtk.Label(label=sublabel)
        sub_label.add_css_class('qs-toggle-sublabel')
        sub_label.set_halign(Gtk.Align.START)
        text_box.append(sub_label)

        box.append(text_box)
        btn.set_child(box)
        return btn

    # ── Internal: Update Display ─────────────────────────────────

    def _update_battery_display(self) -> None:
        """Refresh battery icon, label, and charge status indicator."""
        level = self._battery_level

        # Icon based on level and charging state
        if self._is_charging:
            self._battery_icon.set_from_icon_name('battery-full-charging-symbolic')
            self._battery_label.add_css_class('charging')
            self._battery_label.remove_css_class('low')

            # Charging animation CSS class based on rate
            turbo_min = self._config.turbo_charge_min_watts
            fast_min = self._config.fast_charge_min_watts

            self._battery_icon.remove_css_class('charging')
            self._battery_icon.remove_css_class('turbo-charging')

            if self._charge_rate >= turbo_min:
                self._battery_icon.add_css_class('turbo-charging')
                self._charge_label.set_text('Beeta® Turbo Charge™ Active')
                self._charge_label.set_visible(True)
            elif self._charge_rate >= fast_min:
                self._battery_icon.add_css_class('charging')
                self._charge_label.set_text('Fast Charging')
                self._charge_label.set_visible(True)
            else:
                self._battery_icon.add_css_class('charging')
                self._charge_label.set_text('Charging')
                self._charge_label.set_visible(True)
        else:
            self._charge_label.set_visible(False)
            self._battery_icon.remove_css_class('charging')
            self._battery_icon.remove_css_class('turbo-charging')
            self._battery_label.remove_css_class('charging')

            if level <= 10:
                self._battery_icon.set_from_icon_name('battery-empty-symbolic')
                self._battery_label.add_css_class('low')
            elif level <= 20:
                self._battery_icon.set_from_icon_name('battery-low-symbolic')
                self._battery_label.add_css_class('low')
            else:
                self._battery_icon.set_from_icon_name('battery-good-symbolic')
                self._battery_label.remove_css_class('low')

        self._battery_label.set_text(f'{level}%')
        self._battery_icon.set_tooltip_text(
            f'Battery: {level}%'
            + (f' ({self._charge_label.get_text()})' if self._is_charging else '')
        )

        # Emit signal for other components
        self.emit(
            'battery-changed',
            self._battery_level,
            self._is_charging,
            self._charge_rate,
        )

    def _update_wifi_display(self) -> None:
        """Refresh Wi-Fi indicator icon and tooltip."""
        if self._wifi_connected:
            strength = self._wifi_strength
            if strength >= 75:
                self._wifi_icon.set_from_icon_name('network-wireless-signal-excellent-symbolic')
            elif strength >= 50:
                self._wifi_icon.set_from_icon_name('network-wireless-signal-good-symbolic')
            elif strength >= 25:
                self._wifi_icon.set_from_icon_name('network-wireless-signal-ok-symbolic')
            else:
                self._wifi_icon.set_from_icon_name('network-wireless-signal-weak-symbolic')
            self._wifi_icon.set_tooltip_text(
                f'Wi-Fi: {self._wifi_ssid} ({strength}%)'
            )
        else:
            self._wifi_icon.set_from_icon_name('network-wireless-disconnected-symbolic')
            self._wifi_icon.set_tooltip_text('Wi-Fi: Disconnected')

    def _update_volume_display(self) -> None:
        """Refresh volume icon."""
        if self._volume_muted or self._volume_level == 0:
            self._volume_icon.set_from_icon_name('audio-volume-muted-symbolic')
        elif self._volume_level < 30:
            self._volume_icon.set_from_icon_name('audio-volume-low-symbolic')
        elif self._volume_level < 70:
            self._volume_icon.set_from_icon_name('audio-volume-medium-symbolic')
        else:
            self._volume_icon.set_from_icon_name('audio-volume-high-symbolic')
        self._volume_icon.set_tooltip_text(
            f'Volume: {self._volume_level}%'
            + (' (Muted)' if self._volume_muted else '')
        )

    # ── Internal: D-Bus Monitors ─────────────────────────────────

    def _start_upower_monitor(self) -> None:
        """Connect to UPower D-Bus for battery monitoring."""
        try:
            bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)

            # Find the battery device path
            upower_proxy = Gio.DBusProxy.new_sync(
                bus, Gio.DBusProxyFlags.NONE, None,
                'org.freedesktop.UPower',
                '/org/freedesktop/UPower',
                'org.freedesktop.UPower',
                None,
            )

            # Enumerate devices to find the battery
            result = upower_proxy.call_sync(
                'EnumerateDevices', None,
                Gio.DBusCallFlags.NONE, 1000, None,
            )
            if result:
                devices = result.unpack()[0]
                for device_path in devices:
                    if 'battery' in device_path.lower() or 'BAT' in device_path:
                        self._connect_battery_device(bus, device_path)
                        return

            # Fallback: try the common path directly
            self._connect_battery_device(
                bus, '/org/freedesktop/UPower/devices/battery_BAT0'
            )
        except Exception:
            # UPower not available — battery info stays at defaults
            if not self._config.is_laptop:
                self._battery_box.set_visible(False)

    def _connect_battery_device(
        self, bus: Gio.DBusConnection, device_path: str
    ) -> None:
        """Connect to a specific UPower battery device.

        Args:
            bus: System D-Bus connection.
            device_path: D-Bus object path of the battery device.
        """
        try:
            self._upower_proxy = Gio.DBusProxy.new_sync(
                bus, Gio.DBusProxyFlags.NONE, None,
                'org.freedesktop.UPower',
                device_path,
                'org.freedesktop.UPower.Device',
                None,
            )

            # Read initial state
            self._read_battery_state()

            # Watch for changes
            self._upower_proxy.connect(
                'g-properties-changed',
                self._on_upower_changed,
            )

            self._battery_box.set_visible(True)
        except Exception:
            pass

    def _read_battery_state(self) -> None:
        """Read current battery state from UPower proxy."""
        if self._upower_proxy is None:
            return

        try:
            pct = self._upower_proxy.get_cached_property('Percentage')
            if pct:
                self._battery_level = int(pct.get_double())

            state = self._upower_proxy.get_cached_property('State')
            if state:
                # UPower state: 1=Charging, 2=Discharging, 4=Full
                state_val = state.get_uint32()
                self._is_charging = state_val == 1

            rate = self._upower_proxy.get_cached_property('EnergyRate')
            if rate:
                self._charge_rate = abs(rate.get_double())

            self._update_battery_display()
        except Exception:
            pass

    def _on_upower_changed(
        self,
        proxy: Gio.DBusProxy,
        changed: GLib.Variant,
        invalidated: list[str],
    ) -> None:
        """Handle UPower property changes."""
        self._read_battery_state()

    def _start_networkmanager_monitor(self) -> None:
        """Connect to NetworkManager D-Bus for Wi-Fi monitoring."""
        try:
            bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
            self._nm_proxy = Gio.DBusProxy.new_sync(
                bus, Gio.DBusProxyFlags.NONE, None,
                'org.freedesktop.NetworkManager',
                '/org/freedesktop/NetworkManager',
                'org.freedesktop.NetworkManager',
                None,
            )

            # Read initial state
            self._read_network_state()

            # Watch for changes
            self._nm_proxy.connect(
                'g-properties-changed',
                self._on_nm_changed,
            )

            # Poll periodically for signal strength updates
            GLib.timeout_add_seconds(10, self._poll_network_state)
        except Exception:
            pass

    def _read_network_state(self) -> None:
        """Read current network state from NetworkManager."""
        if self._nm_proxy is None:
            return

        try:
            # Check connectivity state
            state = self._nm_proxy.get_cached_property('State')
            if state:
                nm_state = state.get_uint32()
                # NM states: 70=connected-global, 60=connected-site
                self._wifi_connected = nm_state >= 60

            # Try to get active connection info
            active_conns = self._nm_proxy.get_cached_property(
                'ActiveConnections'
            )
            if active_conns and self._wifi_connected:
                conn_paths = active_conns.unpack()
                for conn_path in conn_paths:
                    self._read_active_connection(conn_path)
                    break  # Use first active connection

            self._update_wifi_display()
        except Exception:
            pass

    def _read_active_connection(self, conn_path: str) -> None:
        """Read SSID from an active NetworkManager connection.

        Args:
            conn_path: D-Bus object path of the active connection.
        """
        try:
            bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
            conn_proxy = Gio.DBusProxy.new_sync(
                bus, Gio.DBusProxyFlags.NONE, None,
                'org.freedesktop.NetworkManager',
                conn_path,
                'org.freedesktop.NetworkManager.Connection.Active',
                None,
            )
            name_var = conn_proxy.get_cached_property('Id')
            if name_var:
                self._wifi_ssid = name_var.get_string()
        except Exception:
            pass

    def _on_nm_changed(
        self,
        proxy: Gio.DBusProxy,
        changed: GLib.Variant,
        invalidated: list[str],
    ) -> None:
        """Handle NetworkManager property changes."""
        self._read_network_state()

    def _poll_network_state(self) -> bool:
        """Periodic poll for network state (signal strength)."""
        self._read_network_state()
        return GLib.SOURCE_CONTINUE

    def _start_volume_monitor(self) -> None:
        """Start monitoring audio volume via PulseAudio/PipeWire.

        Uses pactl subscribe for real-time updates with fallback
        to periodic polling.
        """
        # Initial read
        self._read_volume_state()
        # Poll every 5 seconds as a simple fallback
        GLib.timeout_add_seconds(5, self._poll_volume_state)

    def _read_volume_state(self) -> None:
        """Read current volume level via pactl (works with PipeWire too)."""
        try:
            import subprocess
            result = subprocess.run(
                ['pactl', 'get-sink-volume', '@DEFAULT_SINK@'],
                capture_output=True, text=True, timeout=2,
            )
            if result.returncode == 0:
                output = result.stdout
                # Parse "Volume: front-left: 32768 /  50% / ..."
                for part in output.split('/'):
                    part = part.strip()
                    if part.endswith('%'):
                        try:
                            self._volume_level = int(
                                part.rstrip('%').strip()
                            )
                            break
                        except ValueError:
                            pass

            # Check mute state
            mute_result = subprocess.run(
                ['pactl', 'get-sink-mute', '@DEFAULT_SINK@'],
                capture_output=True, text=True, timeout=2,
            )
            if mute_result.returncode == 0:
                self._volume_muted = 'yes' in mute_result.stdout.lower()

            self._update_volume_display()
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pass

    def _poll_volume_state(self) -> bool:
        """Periodic poll for volume state."""
        self._read_volume_state()
        return GLib.SOURCE_CONTINUE

    # ── Internal: Event Handlers ─────────────────────────────────

    def _on_tray_clicked(
        self,
        gesture: Gtk.GestureClick,
        n_press: int,
        x: float,
        y: float,
    ) -> None:
        """Open/close Quick Settings popover."""
        if self._qs_popover.get_visible():
            self._qs_popover.popdown()
            self.emit('quick-settings-toggled', False)
        else:
            self._qs_popover.popup()
            self.emit('quick-settings-toggled', True)

    def _on_volume_changed(self, scale: Gtk.Scale) -> None:
        """Handle volume slider changes in Quick Settings."""
        level = int(scale.get_value())
        self._volume_level = level
        self._update_volume_display()

        # Apply via pactl
        try:
            import subprocess
            subprocess.Popen(
                ['pactl', 'set-sink-volume', '@DEFAULT_SINK@', f'{level}%'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except (FileNotFoundError, OSError):
            pass

    def _on_perf_mode_clicked(
        self, button: Gtk.Button, mode: str
    ) -> None:
        """Handle performance mode selection in Quick Settings."""
        for m, btn in self._perf_buttons.items():
            if m == mode:
                btn.add_css_class('active')
            else:
                btn.remove_css_class('active')
        self._config.set('Desktop', 'performance_mode', mode)

    def _on_nature_mode_clicked(
        self, button: Gtk.Button, mode: str
    ) -> None:
        """Handle Adaptive Nature mode selection in Quick Settings."""
        for m, btn in self._nature_buttons.items():
            if m == mode:
                btn.add_css_class('active')
            else:
                btn.remove_css_class('active')
        self._config.set('Desktop', 'adaptive_nature_mode', mode)

    def set_focus_mode(self, is_focus: bool, is_laptop: bool) -> None:
        """Adjust tray visibility for Focus State.

        Args:
            is_focus: Whether Focus State is active.
            is_laptop: Whether the device is a laptop.
        """
        if is_focus:
            self._volume_icon.set_visible(False)
            self._bt_icon.set_visible(False)
            self._wifi_icon.set_visible(False)
            # Battery stays visible on laptops
            self._battery_box.set_visible(is_laptop)
            self._charge_label.set_visible(False)
        else:
            self._volume_icon.set_visible(True)
            self._wifi_icon.set_visible(True)
            self._battery_box.set_visible(self._config.is_laptop)

    def cleanup(self) -> None:
        """Disconnect D-Bus watchers. Call on shutdown."""
        self._upower_proxy = None
        self._nm_proxy = None
