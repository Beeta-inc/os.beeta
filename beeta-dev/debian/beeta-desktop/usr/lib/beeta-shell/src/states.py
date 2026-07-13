# -*- coding: utf-8 -*-
# Beeta Desktop Environment
# Copyright (C) 2023-2026 Beeta Technologies Inc.
# Licensed under GNU General Public License v3.0

"""Desktop / Focus state manager for the Beeta Shell.

Manages transitions between two primary desktop states:

Desktop State (default):
    - Top bar: workspace dots + Live Center + full system tray
    - Bottom bar: visible, all animations running

Focus State (app maximized):
    - Top bar: workspace dots fade out, only Live Center + battery remain
    - Bottom bar: slides off-screen, animations paused
    - On desktop machines (no battery): even battery hides

The bottom bar can be temporarily revealed in Focus State by:
    - Moving the mouse to the bottom edge for ~150ms
    - Pressing the Super key
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from gi.repository import GLib, GObject

if TYPE_CHECKING:
    from .config import BeetaConfig


class StateManager(GObject.Object):
    """Manages Desktop ↔ Focus state transitions.

    Emits 'state-changed' whenever the desktop state changes, allowing
    the top bar and bottom bar to adapt their visibility and behavior.

    The StateManager also handles the bottom bar edge-hover reveal
    logic with configurable delay.

    Signals:
        state-changed(state: str):
            Emitted when state transitions between 'desktop' and 'focus'.
            Listeners should update their UI accordingly.

        bar-reveal-requested():
            Emitted when the user requests the bottom bar to temporarily
            appear in Focus State (via edge hover or keyboard shortcut).

        bar-dismiss-requested():
            Emitted when the temporarily revealed bottom bar should
            hide again.

    Example:
        >>> state_mgr = StateManager(config)
        >>> state_mgr.connect('state-changed', on_state_changed)
        >>> state_mgr.set_state('focus')
    """

    __gsignals__ = {
        'state-changed': (
            GObject.SignalFlags.RUN_FIRST, None, (str,)
        ),
        'bar-reveal-requested': (
            GObject.SignalFlags.RUN_FIRST, None, ()
        ),
        'bar-dismiss-requested': (
            GObject.SignalFlags.RUN_FIRST, None, ()
        ),
    }

    # Edge hover delay in milliseconds before revealing the bottom bar
    EDGE_HOVER_DELAY_MS: int = 150

    # Delay before hiding the bar after mouse leaves
    BAR_DISMISS_DELAY_MS: int = 400

    def __init__(self, config: BeetaConfig) -> None:
        """Initialize the state manager.

        Args:
            config: Beeta configuration instance.
        """
        super().__init__()
        self._config = config
        self._current_state: str = 'desktop'
        self._bar_temporarily_visible: bool = False
        self._edge_hover_source: int = 0
        self._dismiss_source: int = 0
        self._is_laptop: bool = config.is_laptop

    @property
    def current_state(self) -> str:
        """Current desktop state: 'desktop' or 'focus'."""
        return self._current_state

    @property
    def is_laptop(self) -> bool:
        """Whether the device is a laptop (affects Focus State behavior)."""
        return self._is_laptop

    @property
    def is_bar_visible(self) -> bool:
        """Whether the bottom bar should be visible.

        Returns True in Desktop State, or when temporarily revealed
        in Focus State.
        """
        return (
            self._current_state == 'desktop'
            or self._bar_temporarily_visible
        )

    def set_state(self, state: str) -> None:
        """Transition to a new desktop state.

        Args:
            state: Target state, either 'desktop', 'focus', or 'locked'.

        Raises:
            ValueError: If state is invalid.
        """
        if state not in ('desktop', 'focus', 'locked'):
            raise ValueError(
                f"Invalid state '{state}'. Must be 'desktop', 'focus', or 'locked'."
            )

        if state == self._current_state:
            return

        old_state = self._current_state
        self._current_state = state

        # Cancel any pending edge-hover or dismiss timers
        self._cancel_edge_hover()
        self._cancel_dismiss()

        # Reset temporary reveal when returning to desktop or locking
        if state in ('desktop', 'locked'):
            self._bar_temporarily_visible = False

        self.emit('state-changed', state)

    def toggle_state(self) -> None:
        """Toggle between Desktop and Focus states."""
        if self._current_state == 'desktop':
            self.set_state('focus')
        else:
            self.set_state('desktop')

    # ── Edge Hover Detection ─────────────────────────────────────

    def on_edge_hover_enter(self) -> None:
        """Called when the mouse enters the bottom edge zone.

        Starts a timer that will reveal the bottom bar after
        EDGE_HOVER_DELAY_MS if the mouse stays in the zone.
        """
        if self._current_state != 'focus':
            return  # Bar is already visible in desktop state

        if self._bar_temporarily_visible:
            # Bar is already shown, cancel any pending dismiss
            self._cancel_dismiss()
            return

        self._cancel_edge_hover()
        self._edge_hover_source = GLib.timeout_add(
            self.EDGE_HOVER_DELAY_MS,
            self._do_reveal_bar,
        )

    def on_edge_hover_leave(self) -> None:
        """Called when the mouse leaves the bottom edge zone or bar.

        If the bar is temporarily visible, starts a dismiss timer.
        If the mouse left before the reveal timer fired, cancels it.
        """
        self._cancel_edge_hover()

        if self._bar_temporarily_visible and self._current_state == 'focus':
            self._cancel_dismiss()
            self._dismiss_source = GLib.timeout_add(
                self.BAR_DISMISS_DELAY_MS,
                self._do_dismiss_bar,
            )

    def request_bar_reveal(self) -> None:
        """Immediately reveal the bottom bar (e.g., via keyboard shortcut).

        Used when Super key is pressed in Focus State.
        """
        if self._current_state != 'focus':
            return

        self._cancel_edge_hover()
        self._cancel_dismiss()
        self._bar_temporarily_visible = True
        self.emit('bar-reveal-requested')

    def request_bar_dismiss(self) -> None:
        """Immediately dismiss the temporarily revealed bottom bar."""
        if not self._bar_temporarily_visible:
            return

        self._cancel_edge_hover()
        self._cancel_dismiss()
        self._do_dismiss_bar()

    # ── Internal Timer Handlers ──────────────────────────────────

    def _do_reveal_bar(self) -> bool:
        """Reveal the bar after the edge-hover delay."""
        self._edge_hover_source = 0
        self._bar_temporarily_visible = True
        self.emit('bar-reveal-requested')
        return GLib.SOURCE_REMOVE

    def _do_dismiss_bar(self) -> bool:
        """Dismiss the temporarily revealed bar."""
        self._dismiss_source = 0
        self._bar_temporarily_visible = False
        self.emit('bar-dismiss-requested')
        return GLib.SOURCE_REMOVE

    def _cancel_edge_hover(self) -> None:
        """Cancel a pending edge-hover reveal timer."""
        if self._edge_hover_source:
            GLib.source_remove(self._edge_hover_source)
            self._edge_hover_source = 0

    def _cancel_dismiss(self) -> None:
        """Cancel a pending bar dismiss timer."""
        if self._dismiss_source:
            GLib.source_remove(self._dismiss_source)
            self._dismiss_source = 0

    def cleanup(self) -> None:
        """Cancel all pending timers. Call on shutdown."""
        self._cancel_edge_hover()
        self._cancel_dismiss()
