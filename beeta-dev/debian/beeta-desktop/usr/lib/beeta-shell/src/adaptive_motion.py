# -*- coding: utf-8 -*-
# Beeta Desktop Environment
# Copyright (C) 2023-2026 Beeta Technologies Inc.
# Licensed under GNU General Public License v3.0

"""Beeta Adaptive Motion™ — Performance-aware animation engine.

Dynamically adjusts animation quality, blur radius, transition duration,
and visual effects based on:

    - Performance mode (Power Saver / Balanced / Performance)
    - Battery level (auto-downgrade below 20%)
    - System load (future: CPU/GPU monitoring)
    - Desktop state (pause hidden animations)

The user always recognizes Beeta OS, but the system adapts intelligently
to deliver the best experience for the current conditions.

Tiers:
    Power Saver:  8px blur, 150ms transitions, fades only, no particles
    Balanced:    20px blur, 300ms transitions, standard Beeta animations
    Performance: 28px blur, 400ms transitions, full ambient effects
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from gi.repository import GLib, GObject

if TYPE_CHECKING:
    from .config import BeetaConfig


# ── Tier Definitions ─────────────────────────────────────────────

_TIERS = {
    'power-saver': {
        'blur_radius': 8,
        'transition_ms': 150,
        'should_animate': True,  # still animates, but simpler
        'use_particles': False,
        'use_ambient': False,
        'shadow_quality': 'low',
        'css_class': 'motion-saver',
    },
    'balanced': {
        'blur_radius': 20,
        'transition_ms': 300,
        'should_animate': True,
        'use_particles': False,
        'use_ambient': True,
        'shadow_quality': 'medium',
        'css_class': 'motion-balanced',
    },
    'performance': {
        'blur_radius': 28,
        'transition_ms': 400,
        'should_animate': True,
        'use_particles': True,
        'use_ambient': True,
        'shadow_quality': 'high',
        'css_class': 'motion-performance',
    },
}

# When battery is critically low, override to minimal animations
_CRITICAL_BATTERY_LEVEL: int = 10
_LOW_BATTERY_LEVEL: int = 20


class AdaptiveMotion(GObject.Object):
    """Performance-aware animation quality engine.

    Controls the visual richness of the Beeta Shell based on system
    conditions. Components query this engine to determine whether to
    run full animations, simplified alternatives, or skip entirely.

    The engine also manages the pause/resume lifecycle of animations
    for hidden UI components (e.g., bottom bar in Focus State) to
    conserve GPU/CPU resources.

    Signals:
        tier-changed(tier: str):
            Emitted when the animation tier changes. UI components
            should update their CSS classes and animation behavior.

    Example:
        >>> motion = AdaptiveMotion(config)
        >>> motion.tier
        'balanced'
        >>> motion.check_battery(15, False)
        >>> motion.tier
        'power-saver'  # auto-downgraded due to low battery
    """

    __gsignals__ = {
        'tier-changed': (
            GObject.SignalFlags.RUN_FIRST, None, (str,)
        ),
    }

    def __init__(self, config: BeetaConfig) -> None:
        """Initialize the Adaptive Motion engine.

        Args:
            config: Beeta configuration instance.
        """
        super().__init__()
        self._config = config
        self._base_tier: str = config.performance_mode
        self._effective_tier: str = self._base_tier
        self._battery_level: int = 100
        self._is_charging: bool = False
        self._battery_override: bool = False
        self._paused_components: set[str] = set()
        self._check_source: int = 0

        # Validate base tier
        if self._base_tier not in _TIERS:
            self._base_tier = 'balanced'
            self._effective_tier = 'balanced'

        # Listen for config changes
        self._config.connect('config-changed', self._on_config_changed)

    # ── Properties ───────────────────────────────────────────────

    @property
    def tier(self) -> str:
        """Current effective animation tier.

        This may differ from the configured performance_mode if
        battery is low and auto-downgrade is active.
        """
        return self._effective_tier

    @property
    def blur_radius(self) -> int:
        """Recommended backdrop blur radius in pixels."""
        return _TIERS[self._effective_tier]['blur_radius']

    @property
    def transition_ms(self) -> int:
        """Recommended CSS transition duration in milliseconds."""
        return _TIERS[self._effective_tier]['transition_ms']

    @property
    def should_animate(self) -> bool:
        """Whether animations should run at all.

        Returns False only at critical battery levels (<10%)
        when not charging.
        """
        if (
            self._battery_level <= _CRITICAL_BATTERY_LEVEL
            and not self._is_charging
        ):
            return False
        return _TIERS[self._effective_tier]['should_animate']

    @property
    def use_particles(self) -> bool:
        """Whether particle effects should be rendered."""
        return _TIERS[self._effective_tier]['use_particles']

    @property
    def use_ambient(self) -> bool:
        """Whether ambient glow/shadow effects should be rendered."""
        return _TIERS[self._effective_tier]['use_ambient']

    @property
    def shadow_quality(self) -> str:
        """Shadow rendering quality: 'low', 'medium', 'high'."""
        return _TIERS[self._effective_tier]['shadow_quality']

    @property
    def css_class(self) -> str:
        """CSS class to apply to root widget for motion tier styling."""
        return _TIERS[self._effective_tier]['css_class']

    @property
    def is_battery_downgraded(self) -> bool:
        """Whether the tier was auto-downgraded due to low battery."""
        return self._battery_override

    # ── Public API ───────────────────────────────────────────────

    def check_battery(self, level: int, charging: bool) -> None:
        """Update battery state and potentially adjust animation tier.

        If battery drops below 20% while not charging, the tier is
        automatically downgraded by one level. If charging resumes
        or battery rises, the configured tier is restored.

        Args:
            level: Battery percentage (0-100).
            charging: Whether the battery is currently charging.
        """
        self._battery_level = max(0, min(100, level))
        self._is_charging = charging
        self._recalculate_tier()

    def set_performance_mode(self, mode: str) -> None:
        """Change the base performance mode.

        Args:
            mode: One of 'power-saver', 'balanced', 'performance'.

        Raises:
            ValueError: If mode is not a valid tier name.
        """
        if mode not in _TIERS:
            raise ValueError(
                f"Invalid mode '{mode}'. "
                f"Must be one of: {', '.join(_TIERS.keys())}"
            )
        self._base_tier = mode
        self._config.set('Desktop', 'performance_mode', mode)
        self._recalculate_tier()

    def pause_component(self, component_id: str) -> None:
        """Mark a component's animations as paused.

        Used when a component becomes invisible (e.g., bottom bar
        hiding in Focus State). The component should stop its
        animation timers when paused.

        Args:
            component_id: Unique identifier for the component
                (e.g., 'bottombar', 'dock', 'workspace').
        """
        self._paused_components.add(component_id)

    def resume_component(self, component_id: str) -> None:
        """Mark a component's animations as active again.

        Args:
            component_id: Unique identifier for the component.
        """
        self._paused_components.discard(component_id)

    def is_component_paused(self, component_id: str) -> bool:
        """Check if a component's animations should be paused.

        Args:
            component_id: Unique identifier for the component.

        Returns:
            True if the component is currently paused.
        """
        return component_id in self._paused_components

    def get_animation_duration(self, base_ms: int) -> int:
        """Scale an animation duration based on current tier.

        Args:
            base_ms: The "standard" (balanced tier) duration in ms.

        Returns:
            Scaled duration appropriate for the current tier.
        """
        tier_data = _TIERS[self._effective_tier]
        # Scale relative to balanced tier's transition_ms
        balanced_ms = _TIERS['balanced']['transition_ms']
        scale = tier_data['transition_ms'] / balanced_ms
        return max(50, int(base_ms * scale))

    # ── Internal ─────────────────────────────────────────────────

    def _recalculate_tier(self) -> None:
        """Recalculate the effective tier based on all inputs."""
        old_tier = self._effective_tier
        new_tier = self._base_tier
        self._battery_override = False

        # Auto-downgrade on low battery (not charging)
        if not self._is_charging and self._battery_level <= _LOW_BATTERY_LEVEL:
            downgraded = self._downgrade_tier(self._base_tier)
            if downgraded != self._base_tier:
                new_tier = downgraded
                self._battery_override = True

        # Critical battery: force power-saver
        if (
            not self._is_charging
            and self._battery_level <= _CRITICAL_BATTERY_LEVEL
        ):
            new_tier = 'power-saver'
            self._battery_override = True

        self._effective_tier = new_tier

        if old_tier != new_tier:
            self.emit('tier-changed', new_tier)

    @staticmethod
    def _downgrade_tier(tier: str) -> str:
        """Downgrade a tier by one level.

        Args:
            tier: Current tier name.

        Returns:
            The tier one level below, or the same if already lowest.
        """
        order = ['power-saver', 'balanced', 'performance']
        try:
            idx = order.index(tier)
            return order[max(0, idx - 1)]
        except ValueError:
            return 'balanced'

    def _on_config_changed(
        self, config: BeetaConfig, section: str, key: str
    ) -> None:
        """React to configuration file changes."""
        if section == 'Desktop' and key == 'performance_mode':
            new_mode = config.performance_mode
            if new_mode in _TIERS and new_mode != self._base_tier:
                self._base_tier = new_mode
                self._recalculate_tier()
