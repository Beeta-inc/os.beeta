# -*- coding: utf-8 -*-
# Beeta Desktop Environment

from __future__ import annotations
import math
import random
import gi

gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, Graphene
import cairo

class Particle:
    def __init__(self, x: float, y: float, vx: float, vy: float, life: float = 1.0):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.life = life
        self.max_life = life
        self.size = random.uniform(1.0, 3.0)

class PhysicsWeatherWidget(Gtk.DrawingArea):
    """A highly optimized, physics-based weather rendering widget."""

    def __init__(self, adaptive_motion=None, width=48, height=48):
        super().__init__()
        self.set_size_request(width, height)
        self._width = width
        self._height = height
        self._motion = adaptive_motion
        
        self.condition = "clear" # clear, cloudy, rainy, snowy, stormy
        self._particles: list[Particle] = []
        self._time = 0.0
        
        self.set_draw_func(self._on_draw)
        self._tick_id = self.add_tick_callback(self._on_tick)
        
    def set_condition(self, condition: str):
        if condition != self.condition:
            self.condition = condition
            self._particles.clear()
            
    def _on_tick(self, widget, frame_clock):
        # Respect AdaptiveMotion power saver mode if provided
        if self._motion and self._motion.is_paused('bottombar'):
            # Just return true to keep the callback alive, but don't update physics
            # The last rendered frame will stay visible (doesn't destroy looks)
            return True

        self._time += 0.016 # ~60fps
        
        if self.condition in ("rainy", "stormy"):
            # Spawn rain
            if len(self._particles) < 40:
                self._particles.append(Particle(
                    x=random.uniform(0, self._width),
                    y=-10,
                    vx=random.uniform(-0.5, 0.5), # slight wind
                    vy=random.uniform(8.0, 12.0)  # fast fall
                ))
        elif self.condition == "snowy":
            # Spawn snow
            if len(self._particles) < 30:
                self._particles.append(Particle(
                    x=random.uniform(0, self._width),
                    y=-10,
                    vx=random.uniform(-1.0, 1.0),
                    vy=random.uniform(1.0, 2.5),
                    life=random.uniform(2.0, 4.0)
                ))
        
        # Update physics
        alive = []
        for p in self._particles:
            p.x += p.vx
            p.y += p.vy
            
            if self.condition == "snowy":
                # Swaying motion for snow
                p.x += math.sin(self._time * 2.0 + p.y) * 0.5
                
            if p.y < self._height + 10:
                alive.append(p)
                
        self._particles = alive
        self.queue_draw()
        return True
        
    def _on_draw(self, drawing_area, cr, width, height):
        cx, cy = width / 2, height / 2
        
        if self.condition == "clear":
            # Draw rotating sun
            cr.translate(cx, cy)
            cr.rotate(self._time * 0.5)
            
            # Sun core
            cr.set_source_rgba(1.0, 0.8, 0.2, 1.0)
            cr.arc(0, 0, width * 0.25, 0, 2 * math.pi)
            cr.fill()
            
            # Sun rays
            cr.set_line_width(width * 0.05)
            cr.set_line_cap(cairo.LINE_CAP_ROUND)
            for i in range(8):
                angle = i * (math.pi / 4)
                x1 = math.cos(angle) * (width * 0.35)
                y1 = math.sin(angle) * (width * 0.35)
                x2 = math.cos(angle) * (width * 0.45)
                y2 = math.sin(angle) * (width * 0.45)
                cr.move_to(x1, y1)
                cr.line_to(x2, y2)
                cr.stroke()
                
        elif self.condition == "cloudy":
            # Draw drifting clouds
            drift = math.sin(self._time * 0.5) * 5.0
            cr.set_source_rgba(0.9, 0.9, 0.9, 0.9)
            
            cr.arc(cx - 10 + drift, cy + 5, width * 0.2, 0, 2 * math.pi)
            cr.arc(cx + drift, cy - 5, width * 0.25, 0, 2 * math.pi)
            cr.arc(cx + 15 + drift, cy + 2, width * 0.18, 0, 2 * math.pi)
            cr.fill()
            
        elif self.condition in ("rainy", "stormy"):
            # Dark cloud
            cr.set_source_rgba(0.5, 0.5, 0.55, 1.0)
            cr.arc(cx - 8, cy - 10, width * 0.2, 0, 2 * math.pi)
            cr.arc(cx + 8, cy - 10, width * 0.25, 0, 2 * math.pi)
            cr.fill()
            
            # Rain particles
            cr.set_source_rgba(0.4, 0.7, 1.0, 0.8)
            cr.set_line_width(2.0)
            for p in self._particles:
                cr.move_to(p.x, p.y)
                cr.line_to(p.x - p.vx*2, p.y - p.vy*2) # motion blur effect
                cr.stroke()
                
            # Lightning
            if self.condition == "stormy" and random.random() < 0.05:
                cr.set_source_rgba(1.0, 1.0, 0.8, 0.9)
                cr.move_to(cx, cy - 5)
                cr.line_to(cx - 5, cy + 5)
                cr.line_to(cx + 2, cy + 5)
                cr.line_to(cx - 8, cy + 15)
                cr.stroke()
                
        elif self.condition == "snowy":
            # Cloud
            cr.set_source_rgba(0.8, 0.8, 0.85, 1.0)
            cr.arc(cx - 8, cy - 10, width * 0.2, 0, 2 * math.pi)
            cr.arc(cx + 8, cy - 10, width * 0.25, 0, 2 * math.pi)
            cr.fill()
            
            # Snow particles
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.9)
            for p in self._particles:
                cr.arc(p.x, p.y, p.size, 0, 2 * math.pi)
                cr.fill()
