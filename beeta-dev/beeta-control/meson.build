# ═══════════════════════════════════════════════════════════════
# Beeta Control Panel — Meson Build
# Copyright (C) 2023-2026 Beeta Technologies Inc.
# Licensed under GNU General Public License v3.0
# ═══════════════════════════════════════════════════════════════

# ── Python Source Files ──────────────────────────────────────────

control_sources = files(
    'src/__init__.py',
    'src/main.py',
    'src/window.py',
)

control_page_sources = files(
    'src/pages/__init__.py',
    'src/pages/appearance.py',
    'src/pages/performance.py',
    'src/pages/desktop.py',
    'src/pages/display.py',
    'src/pages/sound.py',
    'src/pages/network.py',
    'src/pages/battery.py',
    'src/pages/about.py',
)

# Install sources
install_data(
    control_sources,
    install_dir: join_paths(get_option('prefix'), 'lib', 'beeta-control', 'src'),
)

install_data(
    control_page_sources,
    install_dir: join_paths(get_option('prefix'), 'lib', 'beeta-control', 'src', 'pages'),
)

# ── Data Files ───────────────────────────────────────────────────

install_data(
    'data/style.css',
    install_dir: join_paths(get_option('datadir'), 'beeta-control'),
)

install_data(
    'data/beeta-control.desktop',
    install_dir: join_paths(get_option('datadir'), 'applications'),
)

# ── Launch Script ────────────────────────────────────────────────

install_data(
    'bin/beeta-control',
    install_dir: get_option('bindir'),
    install_mode: 'rwxr-xr-x',
)
