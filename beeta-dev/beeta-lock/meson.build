# ═══════════════════════════════════════════════════════════════
# Beeta Lock Screen — Meson Build
# Copyright (C) 2023-2026 Beeta Technologies Inc.
# Licensed under GNU General Public License v3.0
# ═══════════════════════════════════════════════════════════════

# Python Sources
lock_sources = [
    'src/__init__.py',
    'src/main.py',
    'src/ui.py',
    'src/animations.py',
    'src/theme.py',
    'src/auth.py',
]

install_data(
    lock_sources,
    install_dir: join_paths(get_option('datadir'), 'beeta-lock', 'src'),
)

# Assets / CSS
install_data(
    'data/style.css',
    install_dir: join_paths(get_option('datadir'), 'beeta-lock'),
)

# Executable Wrapper
install_data(
    'bin/beeta-lock',
    install_dir: get_option('bindir'),
    install_mode: 'rwxr-xr-x',
)
