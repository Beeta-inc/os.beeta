# ═══════════════════════════════════════════════════════════════
# Beeta Shell — Meson Build
# Copyright (C) 2023-2026 Beeta Technologies Inc.
# Licensed under GNU General Public License v3.0
# ═══════════════════════════════════════════════════════════════

# ── Python Source Files ──────────────────────────────────────────

shell_sources = files(
    'src/__init__.py',
    'src/main.py',
    'src/config.py',
    'src/states.py',
    'src/adaptive_nature.py',
    'src/adaptive_motion.py',
    'src/topbar.py',
    'src/bottombar.py',
    'src/workspace.py',
    'src/live_center.py',
    'src/system_tray.py',
    'src/dock.py',
    'src/launcher.py',
)

# Install Python sources to /usr/lib/beeta-shell/src/
install_data(
    shell_sources,
    install_dir: join_paths(get_option('prefix'), 'lib', 'beeta-shell', 'src'),
)

# ── Data Files ───────────────────────────────────────────────────

shell_data = files(
    'data/style.css',
    'data/beeta.conf',
)

# Install data to /usr/share/beeta-shell/
install_data(
    shell_data,
    install_dir: join_paths(get_option('datadir'), 'beeta-shell'),
)

# Also install default config to /etc/beeta/
install_data(
    'data/beeta.conf',
    install_dir: join_paths(get_option('sysconfdir'), 'beeta'),
)

# ── Launch Script ────────────────────────────────────────────────

install_data(
    'bin/beeta-shell',
    install_dir: get_option('bindir'),
    install_mode: 'rwxr-xr-x',
)
