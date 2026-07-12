# -*- coding: utf-8 -*-
# Beeta Desktop Environment
# Copyright (C) 2023-2026 Beeta Technologies Inc.
# Licensed under GNU General Public License v3.0

"""About page — system information and Beeta OS branding."""

from __future__ import annotations

import platform
import os
import subprocess
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib


class AboutPage(Gtk.Box):
    """About page showing Beeta OS branding and system information."""

    def __init__(self, config) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._config = config
        self._build_page()

    def _build_page(self) -> None:
        title = Gtk.Label(label='About Beeta')
        title.add_css_class('page-title')
        title.set_halign(Gtk.Align.START)
        self.append(title)

        subtitle = Gtk.Label(label='System information')
        subtitle.add_css_class('page-subtitle')
        subtitle.set_halign(Gtk.Align.START)
        self.append(subtitle)

        # ── Branding Card ──
        brand_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        brand_card.add_css_class('settings-card')

        # Center-aligned branding
        brand_center = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=4,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
            margin_top=12,
            margin_bottom=12,
        )

        logo = Gtk.Label(label='🟣')
        logo.add_css_class('about-logo')
        brand_center.append(logo)

        name = Gtk.Label(label='Beeta OS')
        name.add_css_class('about-name')
        brand_center.append(name)

        version = Gtk.Label(label='Desktop Environment v0.1.0')
        version.add_css_class('about-version')
        brand_center.append(version)

        tagline = Gtk.Label(label='"Where technology meets nature"')
        tagline.add_css_class('about-tagline')
        brand_center.append(tagline)

        brand_card.append(brand_center)
        self.append(brand_card)

        # ── System Info Card ──
        sys_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        sys_card.add_css_class('settings-card')

        sys_title = Gtk.Label(label='SYSTEM INFORMATION')
        sys_title.add_css_class('card-title')
        sys_title.set_halign(Gtk.Align.START)
        sys_card.append(sys_title)

        # Gather system info
        hostname = platform.node()
        kernel = platform.release()
        arch = platform.machine()
        cpu = self._get_cpu_name()
        memory = self._get_memory()
        gpu = self._get_gpu()
        disk = self._get_disk_usage()
        uptime = self._get_uptime()
        compositor = os.environ.get('WAYLAND_DISPLAY', 'Unknown')
        session = os.environ.get('XDG_SESSION_TYPE', 'Unknown')

        info_items = [
            ('Hostname', hostname),
            ('Kernel', kernel),
            ('Architecture', arch),
            ('Processor', cpu),
            ('Memory', memory),
            ('Graphics', gpu),
            ('Disk Usage', disk),
            ('Uptime', uptime),
            ('Session Type', session),
            ('Wayland Display', compositor),
            ('Shell', 'Beeta Shell v0.1.0'),
            ('Compositor', 'Wayfire'),
            ('GTK Version', f'{Gtk.get_major_version()}.{Gtk.get_minor_version()}.{Gtk.get_micro_version()}'),
        ]

        for i, (key, value) in enumerate(info_items):
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            row.add_css_class('about-info-row')

            k = Gtk.Label(label=key)
            k.add_css_class('about-info-key')
            k.set_halign(Gtk.Align.START)
            k.set_hexpand(True)
            row.append(k)

            v = Gtk.Label(label=value)
            v.add_css_class('about-info-value')
            v.set_halign(Gtk.Align.END)
            v.set_selectable(True)
            row.append(v)

            sys_card.append(row)

            if i < len(info_items) - 1:
                sep = Gtk.Box()
                sep.add_css_class('card-separator')
                sys_card.append(sep)

        self.append(sys_card)

        # ── Technologies Card ──
        tech_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        tech_card.add_css_class('settings-card')

        tech_title = Gtk.Label(label='POWERED BY')
        tech_title.add_css_class('card-title')
        tech_title.set_halign(Gtk.Align.START)
        tech_card.append(tech_title)

        technologies = [
            ('🐍 Python 3', 'Shell and control panel logic'),
            ('🎨 GTK4', 'Widget toolkit and CSS theming'),
            ('🪟 Wayfire', 'Wayland compositor with blur plugins'),
            ('🧱 gtk4-layer-shell', 'Wayland layer-shell for panels'),
            ('📡 D-Bus', 'System service integration'),
            ('🌤 Open-Meteo', 'Free weather data API'),
        ]

        for icon_name, desc in technologies:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            row.add_css_class('card-row')

            tech_lbl = Gtk.Label(label=icon_name)
            tech_lbl.add_css_class('card-row-label')
            tech_lbl.set_halign(Gtk.Align.START)
            tech_lbl.set_hexpand(True)
            row.append(tech_lbl)

            desc_lbl = Gtk.Label(label=desc)
            desc_lbl.add_css_class('card-row-sublabel')
            desc_lbl.set_halign(Gtk.Align.END)
            row.append(desc_lbl)

            tech_card.append(row)

        self.append(tech_card)

        # Trademark
        tm = Gtk.Label(
            label='© 2023-2026 Beeta Technologies Inc. All rights reserved.\n'
            'Beeta®, Adaptive Nature™, Adaptive Motion™, Turbo Charge™, and Liquid Glass™\n'
            'are trademarks of Beeta Technologies Inc.'
        )
        tm.add_css_class('about-trademark')
        tm.set_halign(Gtk.Align.CENTER)
        tm.set_justify(Gtk.Justification.CENTER)
        tm.set_margin_top(20)
        self.append(tm)

    @staticmethod
    def _get_cpu_name() -> str:
        try:
            with open('/proc/cpuinfo', 'r') as f:
                for line in f:
                    if line.startswith('model name'):
                        return line.split(':')[1].strip()
        except Exception:
            pass
        return platform.processor() or 'Unknown'

    @staticmethod
    def _get_memory() -> str:
        try:
            with open('/proc/meminfo', 'r') as f:
                for line in f:
                    if line.startswith('MemTotal'):
                        kb = int(line.split()[1])
                        gb = kb / (1024 * 1024)
                        return f'{gb:.1f} GB'
        except Exception:
            pass
        return 'Unknown'

    @staticmethod
    def _get_gpu() -> str:
        try:
            result = subprocess.run(
                ['lspci', '-mm'],
                capture_output=True, text=True, timeout=3,
            )
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'VGA' in line or '3D' in line or 'Display' in line:
                        parts = line.split('"')
                        if len(parts) >= 6:
                            return f'{parts[3]} {parts[5]}'
        except Exception:
            pass
        return 'Unknown'

    @staticmethod
    def _get_disk_usage() -> str:
        try:
            stat = os.statvfs('/')
            total = stat.f_blocks * stat.f_frsize
            free = stat.f_bfree * stat.f_frsize
            used = total - free
            total_gb = total / (1024 ** 3)
            used_gb = used / (1024 ** 3)
            pct = (used / total) * 100
            return f'{used_gb:.0f} / {total_gb:.0f} GB ({pct:.0f}%)'
        except Exception:
            return 'Unknown'

    @staticmethod
    def _get_uptime() -> str:
        try:
            with open('/proc/uptime', 'r') as f:
                secs = float(f.readline().split()[0])
                hrs = int(secs // 3600)
                mins = int((secs % 3600) // 60)
                if hrs > 24:
                    days = hrs // 24
                    hrs = hrs % 24
                    return f'{days}d {hrs}h {mins}m'
                return f'{hrs}h {mins}m'
        except Exception:
            return 'Unknown'
