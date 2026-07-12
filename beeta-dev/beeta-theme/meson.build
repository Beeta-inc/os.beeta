# ═══════════════════════════════════════════════════════════════
# BeetaGlass Theme — Meson Build
# Copyright (C) 2023-2026 Beeta Technologies Inc.
# Licensed under GNU General Public License v3.0
# ═══════════════════════════════════════════════════════════════

# ── Daemon Script ────────────────────────────────────────────────

install_data(
    'bin/beeta-themed',
    install_dir: get_option('bindir'),
    install_mode: 'rwxr-xr-x',
)

# ── Theme Metadata ───────────────────────────────────────────────

install_data(
    'index.theme',
    install_dir: join_paths(get_option('datadir'), 'themes', 'BeetaGlass'),
)

# ── GTK4 Theme ───────────────────────────────────────────────────

install_data(
    'gtk-4.0/gtk.css.template',
    install_dir: join_paths(get_option('datadir'), 'themes', 'BeetaGlass', 'gtk-4.0'),
)

# ── GTK3 Theme ───────────────────────────────────────────────────

install_data(
    'gtk-3.0/gtk.css.template',
    install_dir: join_paths(get_option('datadir'), 'themes', 'BeetaGlass', 'gtk-3.0'),
)

# ── Kvantum Theme (Qt) ───────────────────────────────────────────

install_data(
    'kvantum/BeetaGlass/BeetaGlass.kvconfig',
    install_dir: join_paths(get_option('datadir'), 'Kvantum', 'BeetaGlass'),
)

install_data(
    'kvantum/BeetaGlass/BeetaGlass.svg',
    install_dir: join_paths(get_option('datadir'), 'Kvantum', 'BeetaGlass'),
)
