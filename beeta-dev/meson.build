# ═══════════════════════════════════════════════════════════════
# Beeta Desktop Environment — Root Meson Build
# Copyright (C) 2023-2026 Beeta Technologies Inc.
# Licensed under GNU General Public License v3.0
# ═══════════════════════════════════════════════════════════════

project(
    'beeta-desktop',
    version: '0.1.0',
    license: 'GPL-3.0-or-later',
    meson_version: '>= 0.60.0',
    default_options: [
        'warning_level=2',
    ],
)

# ── Dependencies ─────────────────────────────────────────────────

python = import('python')
py_install = python.find_installation('python3', required: true)

# ── Subdirectories ───────────────────────────────────────────────

subdir('beeta-shell')
subdir('beeta-control')
subdir('beeta-theme')
subdir('beeta-lock')

# ── Session Files ────────────────────────────────────────────────

# Install session startup script
install_data(
    'services/beeta-session',
    install_dir: get_option('bindir'),
    install_mode: 'rwxr-xr-x',
)

# Install Wayland session file for display managers
install_data(
    'services/beeta-session.desktop',
    install_dir: join_paths(get_option('datadir'), 'wayland-sessions'),
)

# Install systemd service
install_data(
    'services/systemd/beeta-desktop.service',
    install_dir: join_paths(get_option('prefix'), 'lib', 'systemd', 'system'),
)

# ── Compositor Config ────────────────────────────────────────────

install_data(
    'beeta-compositor/wayfire.ini',
    install_dir: join_paths(get_option('sysconfdir'), 'beeta'),
)
