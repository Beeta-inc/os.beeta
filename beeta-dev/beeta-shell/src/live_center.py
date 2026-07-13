# -*- coding: utf-8 -*-
# Beeta Desktop Environment
# Copyright (C) 2023-2026 Beeta Technologies Inc.
# Licensed under GNU General Public License v3.0

"""Live Center widget for the Beeta Shell top bar.

The Live Center is the defining feature of Beeta OS — a central
status hub that intelligently shows what's happening:

    Default:        10:42
                    Tuesday

    Media playing:  ▶ Spotify
                    Imagine Dragons

    Timer active:   ⏳ 12:41 remaining

    Downloading:    ⬇ Ubuntu.iso
                    73%

    Recording:      🎤 Recording...

    Screen sharing: 🖥 Sharing Screen

Instead of notifications interrupting the user, the Live Center
quietly tells them what's happening. Clicking it expands into
stacked floating cards showing all active tasks.

Listens to MPRIS D-Bus for media players and accepts programmatic
activity registration for timers, downloads, and recordings.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib, Gio, GObject, Pango

if TYPE_CHECKING:
    from .adaptive_motion import AdaptiveMotion


# Activity type priority (lower = higher priority)
_ACTIVITY_PRIORITY = {
    'recording': 0,
    'sharing': 1,
    'media': 2,
    'timer': 3,
    'download': 4,
}

# Icons for each activity type (Standard GTK Symbolic names)
_ACTIVITY_ICONS = {
    'media': 'media-playback-start-symbolic',
    'timer': 'alarm-symbolic',
    'download': 'folder-download-symbolic',
    'recording': 'media-record-symbolic',
    'sharing': 'camera-video-symbolic',
    'rendering': 'video-x-generic-symbolic',
}


class LiveCenter(Gtk.Box):
    """Dynamic status hub for the Beeta Shell top bar.

    Displays the current time by default, but automatically switches
    to show live activities (media, timers, downloads, recordings)
    when they're active. Activities are prioritized so the most
    important one is always visible.

    Click to expand into a card stack showing all active tasks.

    Args:
        adaptive_motion: Adaptive Motion engine for animation control.
    """

    __gsignals__ = {
        'expanded': (GObject.SignalFlags.RUN_FIRST, None, (bool,)),
    }

    def __init__(self, adaptive_motion: AdaptiveMotion) -> None:
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL,
            valign=Gtk.Align.CENTER,
            halign=Gtk.Align.CENTER,
        )
        self.add_css_class('live-center')

        self._motion = adaptive_motion
        self._activities: dict[str, dict] = {}
        self._is_expanded: bool = False
        self._clock_source: int = 0
        self._mpris_watcher_id: int = 0
        self._mpris_proxies: dict[str, Gio.DBusProxy] = {}

        # Build UI layers
        self._build_collapsed_view()
        self._build_expanded_view()

        # Start clock
        self._update_clock()
        self._clock_source = GLib.timeout_add_seconds(
            1, self._update_clock
        )

        # Start MPRIS watcher
        self._start_mpris_watcher()

        # Click to expand/collapse
        click_ctrl = Gtk.GestureClick()
        click_ctrl.connect('released', self._on_clicked)
        self.add_controller(click_ctrl)

    # ── Public API ───────────────────────────────────────────────

    def add_activity(self, activity: dict) -> str:
        """Register a new live activity.

        Args:
            activity: Activity dict with keys:
                'type': str — 'media', 'timer', 'download', 'recording',
                              'sharing', 'rendering'
                'title': str — primary text (track name, filename, etc.)
                'detail': str — secondary text (artist, percentage, etc.)
                'progress': float — 0.0-1.0 for progress-based activities
                'playing': bool — for media, whether it's currently playing

        Returns:
            Unique activity ID for later updates or removal.
        """
        activity_id = str(uuid.uuid4())[:8]
        self._activities[activity_id] = activity.copy()
        self._refresh_display()
        return activity_id

    def update_activity(self, activity_id: str, updates: dict) -> None:
        """Update an existing activity's data.

        Args:
            activity_id: The ID returned by add_activity().
            updates: Dict of fields to update.
        """
        if activity_id in self._activities:
            self._activities[activity_id].update(updates)
            self._refresh_display()

    def remove_activity(self, activity_id: str) -> None:
        """Remove an activity.

        Args:
            activity_id: The ID returned by add_activity().
        """
        if activity_id in self._activities:
            del self._activities[activity_id]
            self._refresh_display()

    def set_expanded(self, expanded: bool) -> None:
        """Expand or collapse the Live Center.

        Args:
            expanded: Whether to show the expanded card stack.
        """
        self._is_expanded = expanded
        self._collapsed_box.set_visible(not expanded)
        self._expanded_box.set_visible(expanded)
        self.emit('expanded', expanded)

    @property
    def current_activity(self) -> Optional[dict]:
        """The highest-priority active activity, or None."""
        return self._get_top_activity()

    @property
    def activities(self) -> list[dict]:
        """All active activities sorted by priority."""
        return sorted(
            self._activities.values(),
            key=lambda a: _ACTIVITY_PRIORITY.get(a.get('type', ''), 99),
        )

    # ── Internal: UI Building ────────────────────────────────────

    def _build_collapsed_view(self) -> None:
        """Build the compact (default) view showing clock or top activity."""
        self._collapsed_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            valign=Gtk.Align.CENTER,
            halign=Gtk.Align.CENTER,
            spacing=0,
        )

        # Clock row
        self._clock_label = Gtk.Label()
        self._clock_label.add_css_class('live-center-time')
        self._clock_label.set_halign(Gtk.Align.CENTER)
        self._collapsed_box.append(self._clock_label)

        # Day / activity detail row
        self._detail_label = Gtk.Label()
        self._detail_label.add_css_class('live-center-day')
        self._detail_label.set_halign(Gtk.Align.CENTER)
        self._detail_label.set_ellipsize(Pango.EllipsizeMode.END)
        self._detail_label.set_max_width_chars(25)
        self._collapsed_box.append(self._detail_label)

        # Activity icon + title row (hidden when showing clock)
        self._activity_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            halign=Gtk.Align.CENTER,
            spacing=4,
        )
        self._activity_icon = Gtk.Image()
        self._activity_icon.add_css_class('live-center-icon')
        self._activity_icon.set_pixel_size(14)
        self._activity_row.append(self._activity_icon)

        self._activity_title = Gtk.Label()
        self._activity_title.add_css_class('live-center-activity-title')
        self._activity_title.set_ellipsize(Pango.EllipsizeMode.END)
        self._activity_title.set_max_width_chars(20)
        self._activity_row.append(self._activity_title)
        self._activity_row.set_visible(False)

        self._collapsed_box.append(self._activity_row)

        # Activity detail (below icon row)
        self._activity_detail = Gtk.Label()
        self._activity_detail.add_css_class('live-center-activity-detail')
        self._activity_detail.set_halign(Gtk.Align.CENTER)
        self._activity_detail.set_ellipsize(Pango.EllipsizeMode.END)
        self._activity_detail.set_max_width_chars(22)
        self._activity_detail.set_visible(False)
        self._collapsed_box.append(self._activity_detail)

        # Progress bar (for downloads/rendering)
        self._progress_bar = Gtk.ProgressBar()
        self._progress_bar.add_css_class('live-center-progress')
        self._progress_bar.set_visible(False)
        self._collapsed_box.append(self._progress_bar)

        self.append(self._collapsed_box)

    def _build_expanded_view(self) -> None:
        """Build the expanded card-stack view."""
        self._expanded_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=4,
            valign=Gtk.Align.START,
        )
        self._expanded_box.set_visible(False)

        # Cards will be dynamically added
        self._card_container = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=6,
        )
        self._expanded_box.append(self._card_container)

        self.append(self._expanded_box)

    # ── Internal: Display Refresh ────────────────────────────────

    def _refresh_display(self) -> None:
        """Update the visible content based on active activities."""
        top = self._get_top_activity()

        if self._is_expanded:
            self._refresh_expanded()
            return

        if top is None:
            # No activities — show clock
            self._show_clock_mode()
        else:
            # Show top activity
            self._show_activity_mode(top)

    def _show_clock_mode(self) -> None:
        """Display the default clock view."""
        self._clock_label.set_visible(True)
        self._detail_label.set_visible(True)
        self._activity_row.set_visible(False)
        self._activity_detail.set_visible(False)
        self._progress_bar.set_visible(False)

    def _show_activity_mode(self, activity: dict) -> None:
        """Display a live activity in the collapsed view.

        Args:
            activity: The activity dict to display.
        """
        act_type = activity.get('type', '')
        title = activity.get('title', '')
        detail = activity.get('detail', '')
        progress = activity.get('progress')
        playing = activity.get('playing', True)

        # Icon + title row
        icon_name = _ACTIVITY_ICONS.get(act_type, 'dialog-information-symbolic')
        if act_type == 'media' and not playing:
            icon_name = 'media-playback-pause-symbolic'

        self._activity_icon.set_from_icon_name(icon_name)

        # Set icon CSS class for coloring
        for cls in ('media', 'timer', 'download', 'recording', 'sharing'):
            self._activity_icon.remove_css_class(cls)
        self._activity_icon.add_css_class(act_type)

        self._activity_title.set_text(title)

        # Hide clock, show activity
        self._clock_label.set_visible(False)
        self._detail_label.set_visible(False)
        self._activity_row.set_visible(True)

        # Detail text
        if detail:
            self._activity_detail.set_text(detail)
            self._activity_detail.set_visible(True)
        else:
            self._activity_detail.set_visible(False)

        # Progress bar
        if progress is not None and act_type in ('download', 'rendering'):
            self._progress_bar.set_fraction(
                max(0.0, min(1.0, progress))
            )
            self._progress_bar.set_visible(True)
        else:
            self._progress_bar.set_visible(False)

    def _refresh_expanded(self) -> None:
        """Rebuild the expanded card stack with all activities."""
        # Clear existing cards
        child = self._card_container.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self._card_container.remove(child)
            child = next_child

        # Add clock card first
        clock_card = self._make_card(
            icon='preferences-system-time-symbolic',
            title=datetime.now().strftime('%H:%M'),
            detail=datetime.now().strftime('%A, %B %d'),
            css_type='clock',
        )
        self._card_container.append(clock_card)

        # Add activity cards
        for activity in self.activities:
            act_type = activity.get('type', '')
            icon = _ACTIVITY_ICONS.get(act_type, 'dialog-information-symbolic')
            title = activity.get('title', '')
            detail = activity.get('detail', '')

            card = self._make_card(
                icon=icon,
                title=title,
                detail=detail,
                css_type=act_type,
            )
            self._card_container.append(card)

    @staticmethod
    def _make_card(
        icon: str, title: str, detail: str, css_type: str
    ) -> Gtk.Box:
        """Create a single activity card for the expanded view.

        Args:
            icon: Emoji/text icon.
            title: Primary text.
            detail: Secondary text.
            css_type: CSS class suffix for coloring.

        Returns:
            A styled Gtk.Box card widget.
        """
        card = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=10,
            valign=Gtk.Align.CENTER,
        )
        card.add_css_class('live-center-card')

        icon_image = Gtk.Image.new_from_icon_name(icon)
        icon_image.set_pixel_size(16)
        icon_image.add_css_class('live-center-icon')
        icon_image.add_css_class(css_type)
        card.append(icon_image)

        text_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=1,
        )
        title_label = Gtk.Label(label=title)
        title_label.add_css_class('live-center-activity-title')
        title_label.set_halign(Gtk.Align.START)
        title_label.set_ellipsize(Pango.EllipsizeMode.END)
        title_label.set_max_width_chars(22)
        text_box.append(title_label)

        if detail:
            detail_label = Gtk.Label(label=detail)
            detail_label.add_css_class('live-center-activity-detail')
            detail_label.set_halign(Gtk.Align.START)
            detail_label.set_ellipsize(Pango.EllipsizeMode.END)
            detail_label.set_max_width_chars(28)
            text_box.append(detail_label)

        card.append(text_box)
        return card

    # ── Internal: Clock ──────────────────────────────────────────

    def _update_clock(self) -> bool:
        """Update the clock display every second."""
        now = datetime.now()
        self._clock_label.set_text(now.strftime('%H:%M'))
        self._detail_label.set_text(now.strftime('%A'))

        # If in expanded mode, refresh the clock card too
        if self._is_expanded:
            self._refresh_expanded()

        return GLib.SOURCE_CONTINUE

    # ── Internal: Event Handlers ─────────────────────────────────

    def _on_clicked(
        self,
        gesture: Gtk.GestureClick,
        n_press: int,
        x: float,
        y: float,
    ) -> None:
        """Handle click to toggle expanded/collapsed state."""
        self.set_expanded(not self._is_expanded)

    # ── Internal: MPRIS Media Integration ────────────────────────

    def _start_mpris_watcher(self) -> None:
        """Watch for MPRIS media players appearing/disappearing on D-Bus."""
        try:
            bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            proxy = Gio.DBusProxy.new_sync(
                bus,
                Gio.DBusProxyFlags.DO_NOT_LOAD_PROPERTIES,
                None,
                'org.freedesktop.DBus',
                '/org/freedesktop/DBus',
                'org.freedesktop.DBus',
                None,
            )

            # List current MPRIS players
            result = proxy.call_sync(
                'ListNames',
                None,
                Gio.DBusCallFlags.NONE,
                1000,
                None,
            )
            if result:
                names = result.unpack()[0]
                for name in names:
                    if name.startswith('org.mpris.MediaPlayer2.'):
                        self._add_mpris_player(bus, name)

            # Watch for new players
            bus.signal_subscribe(
                'org.freedesktop.DBus',
                'org.freedesktop.DBus',
                'NameOwnerChanged',
                '/org/freedesktop/DBus',
                None,
                Gio.DBusSignalFlags.NONE,
                self._on_name_owner_changed,
            )
        except Exception:
            pass  # D-Bus not available; no media integration

    def _on_name_owner_changed(
        self,
        connection: Gio.DBusConnection,
        sender_name: str,
        object_path: str,
        interface_name: str,
        signal_name: str,
        parameters: GLib.Variant,
    ) -> None:
        """Handle D-Bus name owner changes for MPRIS players."""
        name, old_owner, new_owner = parameters.unpack()

        if not name.startswith('org.mpris.MediaPlayer2.'):
            return

        if new_owner and not old_owner:
            # New player appeared
            try:
                bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
                self._add_mpris_player(bus, name)
            except Exception:
                pass
        elif old_owner and not new_owner:
            # Player disappeared
            self._remove_mpris_player(name)

    def _add_mpris_player(
        self, bus: Gio.DBusConnection, bus_name: str
    ) -> None:
        """Start monitoring an MPRIS media player.

        Args:
            bus: The D-Bus session bus connection.
            bus_name: The MPRIS bus name (e.g., org.mpris.MediaPlayer2.spotify).
        """
        if bus_name in self._mpris_proxies:
            return

        try:
            proxy = Gio.DBusProxy.new_sync(
                bus,
                Gio.DBusProxyFlags.NONE,
                None,
                bus_name,
                '/org/mpris/MediaPlayer2',
                'org.mpris.MediaPlayer2.Player',
                None,
            )
            self._mpris_proxies[bus_name] = proxy

            # Get initial state
            self._update_mpris_state(bus_name, proxy)

            # Watch for property changes
            proxy.connect(
                'g-properties-changed',
                self._on_mpris_properties_changed,
                bus_name,
            )
        except Exception:
            pass

    def _remove_mpris_player(self, bus_name: str) -> None:
        """Stop monitoring an MPRIS player.

        Args:
            bus_name: The MPRIS bus name to remove.
        """
        if bus_name in self._mpris_proxies:
            del self._mpris_proxies[bus_name]

        # Remove the activity if it exists
        to_remove = [
            aid for aid, act in self._activities.items()
            if act.get('_mpris_name') == bus_name
        ]
        for aid in to_remove:
            del self._activities[aid]
        self._refresh_display()

    def _on_mpris_properties_changed(
        self,
        proxy: Gio.DBusProxy,
        changed: GLib.Variant,
        invalidated: list[str],
        bus_name: str,
    ) -> None:
        """Handle MPRIS property changes (metadata, playback status)."""
        self._update_mpris_state(bus_name, proxy)

    def _update_mpris_state(
        self, bus_name: str, proxy: Gio.DBusProxy
    ) -> None:
        """Read MPRIS state and update or create activity.

        Args:
            bus_name: The MPRIS bus name.
            proxy: The D-Bus proxy for the player.
        """
        try:
            # Get playback status
            status_var = proxy.get_cached_property('PlaybackStatus')
            status = status_var.get_string() if status_var else 'Stopped'

            # Get metadata
            metadata_var = proxy.get_cached_property('Metadata')

            title = ''
            artist = ''
            if metadata_var:
                metadata = metadata_var.unpack()
                title_var = metadata.get('xesam:title', '')
                if isinstance(title_var, str):
                    title = title_var

                artist_var = metadata.get('xesam:artist', [])
                if isinstance(artist_var, list) and artist_var:
                    artist = artist_var[0]
                elif isinstance(artist_var, str):
                    artist = artist_var

            # Extract player name from bus name
            player_name = bus_name.replace(
                'org.mpris.MediaPlayer2.', ''
            ).title()

            if status == 'Stopped' or not title:
                # Remove activity if player stopped
                to_remove = [
                    aid for aid, act in self._activities.items()
                    if act.get('_mpris_name') == bus_name
                ]
                for aid in to_remove:
                    del self._activities[aid]
            else:
                # Find existing or create new activity
                existing_id = None
                for aid, act in self._activities.items():
                    if act.get('_mpris_name') == bus_name:
                        existing_id = aid
                        break

                activity_data = {
                    'type': 'media',
                    'title': f'{player_name}' if not title else title,
                    'detail': artist if artist else player_name,
                    'playing': status == 'Playing',
                    '_mpris_name': bus_name,
                }

                if existing_id:
                    self._activities[existing_id] = activity_data
                else:
                    aid = str(uuid.uuid4())[:8]
                    self._activities[aid] = activity_data

            self._refresh_display()
        except Exception:
            pass

    # ── Internal: Helpers ────────────────────────────────────────

    def _get_top_activity(self) -> Optional[dict]:
        """Return the highest-priority active activity, or None."""
        if not self._activities:
            return None

        return min(
            self._activities.values(),
            key=lambda a: _ACTIVITY_PRIORITY.get(a.get('type', ''), 99),
        )

    def cleanup(self) -> None:
        """Cancel all timers and watchers. Call on shutdown."""
        if self._clock_source:
            GLib.source_remove(self._clock_source)
            self._clock_source = 0
