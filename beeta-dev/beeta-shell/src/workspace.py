# -*- coding: utf-8 -*-
# Beeta Desktop Environment
# Copyright (C) 2023-2026 Beeta Technologies Inc.
# Licensed under GNU General Public License v3.0

"""Workspace dot switcher widget for the Beeta Shell top bar.

Displays workspace indicators as minimalist dots:
    ● ○ ○   (workspace 1 active)
    ○ ● ○   (workspace 2 active)
    ○ ○ ●   (workspace 3 active)

When switching, the newly active dot briefly morphs into a pill shape
(stretches ~1.8× horizontally) before contracting back to a circle.
This micro-animation makes workspace switching feel alive.

Communicates with the Wayfire compositor via IPC socket to
switch workspaces and receive workspace change notifications.
"""

from __future__ import annotations

import json
import os
import socket
from typing import TYPE_CHECKING, Optional

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib, GObject

if TYPE_CHECKING:
    from .config import BeetaConfig
    from .adaptive_motion import AdaptiveMotion


class WorkspaceSwitcher(Gtk.Box):
    """Workspace indicator dots with animated switching.

    Each workspace is represented as a small circular dot. The active
    workspace dot is filled with the accent color and glows. Clicking
    a dot switches to that workspace with a pill-morph animation.

    Args:
        config: Beeta configuration instance.
        adaptive_motion: Adaptive Motion engine for animation control.

    Signals:
        workspace-changed(index: int):
            Emitted after the active workspace changes.
    """

    __gsignals__ = {
        'workspace-changed': (
            GObject.SignalFlags.RUN_FIRST, None, (int,)
        ),
    }

    # Duration of the pill-morph animation in ms (balanced tier)
    _MORPH_DURATION_MS: int = 200

    # Duration to hold the pill shape before contracting
    _MORPH_HOLD_MS: int = 80

    def __init__(
        self,
        config: BeetaConfig,
        adaptive_motion: AdaptiveMotion,
    ) -> None:
        super().__init__(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=0,
            valign=Gtk.Align.CENTER,
            halign=Gtk.Align.START,
        )
        self.add_css_class('workspace-switcher')

        self._config = config
        self._motion = adaptive_motion
        self._count: int = config.workspaces
        self._active: int = 0
        self._dots: list[Gtk.Button] = []
        self._morph_timeout: int = 0
        self._ipc_socket_path: Optional[str] = None

        # Build the dot buttons
        self._build_dots()

        # Try to connect to Wayfire IPC for real workspace switching
        self._discover_wayfire_ipc()

    @property
    def active(self) -> int:
        """Currently active workspace index (0-based)."""
        return self._active

    @property
    def count(self) -> int:
        """Total number of workspaces."""
        return self._count

    def switch_to(self, index: int) -> None:
        """Switch to a workspace by index.

        Args:
            index: Target workspace index (0-based).
        """
        if index < 0 or index >= self._count:
            return
        if index == self._active:
            return

        old_active = self._active
        self._active = index

        # Update dot visual states
        self._update_dot_states(old_active, index)

        # Send workspace switch command to compositor
        self._send_workspace_switch(index)

        self.emit('workspace-changed', index)

    def set_visible_animated(self, visible: bool) -> None:
        """Show or hide the workspace dots with animation.

        Used when transitioning to/from Focus State.

        Args:
            visible: Whether dots should be visible.
        """
        for dot in self._dots:
            if visible:
                dot.remove_css_class('hidden')
            else:
                dot.add_css_class('hidden')

    # ── Internal: Build UI ───────────────────────────────────────

    def _build_dots(self) -> None:
        """Create the workspace dot buttons."""
        # Clear existing dots
        while self._dots:
            dot = self._dots.pop()
            self.remove(dot)

        for i in range(self._count):
            dot = Gtk.Button()
            dot.set_can_focus(False)
            dot.add_css_class('workspace-dot')
            if i == self._active:
                dot.add_css_class('active')
            dot.set_tooltip_text(f'Workspace {i + 1}')

            # Click handler
            dot.connect('clicked', self._on_dot_clicked, i)

            self._dots.append(dot)
            self.append(dot)

    def _update_dot_states(self, old_index: int, new_index: int) -> None:
        """Update CSS classes on dots after a workspace switch.

        Triggers the pill-morph animation on the newly active dot.

        Args:
            old_index: Previously active workspace index.
            new_index: Newly active workspace index.
        """
        # Remove active from old dot
        if 0 <= old_index < len(self._dots):
            self._dots[old_index].remove_css_class('active')

        # Cancel any pending morph animation
        if self._morph_timeout:
            GLib.source_remove(self._morph_timeout)
            self._morph_timeout = 0
            # Clean up any dot that's mid-morph
            for dot in self._dots:
                dot.remove_css_class('morphing')

        if 0 <= new_index < len(self._dots):
            new_dot = self._dots[new_index]

            if self._motion.should_animate:
                # Phase 1: Expand to pill shape
                new_dot.add_css_class('morphing')
                new_dot.add_css_class('active')

                # Phase 2: After hold duration, contract back to circle
                hold_ms = self._motion.get_animation_duration(
                    self._MORPH_HOLD_MS
                )
                morph_ms = self._motion.get_animation_duration(
                    self._MORPH_DURATION_MS
                )

                self._morph_timeout = GLib.timeout_add(
                    hold_ms + morph_ms,
                    self._end_morph_animation,
                    new_index,
                )
            else:
                # No animation: just swap classes instantly
                new_dot.add_css_class('active')

    def _end_morph_animation(self, index: int) -> bool:
        """Remove the morphing class to contract the pill back to dot.

        Args:
            index: The dot index that was morphing.

        Returns:
            GLib.SOURCE_REMOVE to cancel the timeout.
        """
        self._morph_timeout = 0
        if 0 <= index < len(self._dots):
            self._dots[index].remove_css_class('morphing')
        return GLib.SOURCE_REMOVE

    # ── Internal: Event Handlers ─────────────────────────────────

    def _on_dot_clicked(self, button: Gtk.Button, index: int) -> None:
        """Handle click on a workspace dot."""
        self.switch_to(index)

    # ── Internal: Wayfire IPC ────────────────────────────────────

    def _discover_wayfire_ipc(self) -> None:
        """Find the Wayfire IPC socket path from environment."""
        # Wayfire exposes its IPC socket via WAYFIRE_SOCKET env var
        sock_path = os.environ.get('WAYFIRE_SOCKET', '')
        if sock_path and os.path.exists(sock_path):
            self._ipc_socket_path = sock_path
        else:
            # Try common paths
            runtime_dir = os.environ.get(
                'XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}'
            )
            candidates = [
                os.path.join(runtime_dir, 'wayfire-wayland-0.socket'),
                os.path.join(runtime_dir, 'wayfire.socket'),
            ]
            for candidate in candidates:
                if os.path.exists(candidate):
                    self._ipc_socket_path = candidate
                    break

    def _send_workspace_switch(self, index: int) -> None:
        """Send a workspace switch command to Wayfire via IPC.

        Falls back to wlr-foreign-toplevel or does nothing if
        compositor IPC is not available.

        Args:
            index: Target workspace index (0-based).
        """
        if self._ipc_socket_path is None:
            return

        # Wayfire IPC uses JSON-based messages over unix socket
        # Calculate workspace grid position (assuming horizontal layout)
        command = {
            'method': 'vswitch/set-workspace',
            'data': {
                'x': index,
                'y': 0,
            },
        }

        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(1.0)
            sock.connect(self._ipc_socket_path)

            msg = json.dumps(command).encode('utf-8')
            # Wayfire IPC protocol: 4-byte length prefix + JSON
            length = len(msg)
            header = length.to_bytes(4, byteorder='little')
            sock.sendall(header + msg)

            sock.close()
        except (OSError, socket.error):
            pass  # IPC not available; workspace switch is visual only

    def cleanup(self) -> None:
        """Cancel pending animations. Call on shutdown."""
        if self._morph_timeout:
            GLib.source_remove(self._morph_timeout)
            self._morph_timeout = 0
