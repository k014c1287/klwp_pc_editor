"""Translate KLWP animation declarations into preview transforms."""

import math
import re
import time

from ..formula import _as_number


class TransformState:
    def __init__(self, page, triplet, switches):
        self._values = {
            "horizontal": 0.0, "vertical": 0.0, "alpha": 1.0,
            "page": page, "triplet": triplet, "switches": switches,
        }

    def __getitem__(self, name):
        return self._values[name]

    def add_horizontal(self, distance):
        self._values["horizontal"] += distance

    def add_vertical(self, distance):
        self._values["vertical"] += distance

    def multiply_alpha(self, value):
        self._values["alpha"] *= value

    def result(self):
        alpha = max(0.0, min(1.0, self._values["alpha"]))
        return {
            "dx": self._values["horizontal"],
            "dy": self._values["vertical"],
            "alpha": alpha,
        }


class LoopProgress:
    def __init__(self, started_at):
        self._started_at = started_at

    def for_animation(self, animation):
        if self._started_at is None:
            return 0.0
        duration = _as_number(animation.get("duration", 10), 10)
        duration = max(0.1, duration / 10.0)
        phase = ((time.perf_counter() - self._started_at) / duration) % 2.0
        if phase <= 1.0:
            return phase
        return 2.0 - phase


class AnimationTransform:
    def __init__(self, owner, item):
        self._owner = owner
        self._item = item

    def calculate(self):
        state = self._initial_state()
        item = self._item
        animations = item.get("internal_animations", []) or []
        for animation in animations:
            self._apply_animation(state, animation)
        return state.result()

    def _initial_state(self):
        owner = self._owner
        memory = owner.memory
        page = float(memory.optional("preview_scroll", 0.0))
        triplet = owner._scroll_fade_triplet()
        switches = memory.optional("preview_switch_progress", {})
        return TransformState(page, triplet, switches)

    def _apply_animation(self, state, animation):
        if not isinstance(animation, dict):
            return
        progress = self._progress(state, animation)
        if progress is None:
            return
        amount = _as_number(animation.get("amount", 100.0), 100.0)
        amount = max(0.0, min(100.0, amount)) / 100.0
        speed = _as_number(animation.get("speed", 100.0), 100.0)
        action = str(animation.get("action") or "SCROLL").upper()
        handlers = {
            "FADE": self._fade,
            "FADE_OUT": self._fade,
            "FADE_IN": self._fade_in,
            "SCROLL": self._scroll,
            "SCROLL_INVERTED": self._scroll,
        }
        handler = handlers.get(action)
        if handler is not None:
            handler(state, animation, progress, amount, speed)

    def _progress(self, state, animation):
        reaction = str(animation.get("type", "")).upper()
        handlers = {
            "SCROLL": self._scroll_progress,
            "SWITCH": self._switch_progress,
            "LOOP_2W": self._loop_progress,
        }
        handler = handlers.get(reaction)
        if handler is None:
            return None
        return handler(state, animation)

    def _scroll_progress(self, state, animation):
        action = str(animation.get("action") or "SCROLL").upper()
        rule = str(animation.get("rule") or "CENTER").upper()
        if self._uses_special_triplet(state, animation, action):
            centers = {"BEFORE_CENTER": 0.0, "CENTER": 1.0, "AFTER_CENTER": 2.0}
            return state["page"] - centers.get(rule, 1.0)
        progress = state["page"] - self.center(animation)
        if rule == "BEFORE_CENTER":
            return min(progress, 0.0)
        if rule == "AFTER_CENTER":
            return max(progress, 0.0)
        return progress

    @staticmethod
    def _uses_special_triplet(state, animation, action):
        return action == "FADE" and state["triplet"] and not animation.get("center")

    @staticmethod
    def _switch_progress(state, animation):
        trigger = str(animation.get("trigger", ""))
        return float(state["switches"].get(trigger, 0.0))

    def _loop_progress(self, _state, animation):
        owner = self._owner
        memory = owner.memory
        progress = LoopProgress(memory.optional("_loop_started_at"))
        return progress.for_animation(animation)

    @staticmethod
    def center(animation, default=0.0):
        match = re.match(r"SCREEN(\d+)$", str(animation.get("center", "")))
        if match is None:
            return default
        return float(int(match.group(1)) - 1)

    @staticmethod
    def _fade(state, animation, progress, amount, speed):
        reaction = str(animation.get("type", "")).upper()
        fade = AnimationTransform._fade_amount(reaction, progress, speed)
        state.multiply_alpha(max(0.0, 1.0 - fade * amount))

    @staticmethod
    def _fade_amount(reaction, progress, speed):
        if reaction == "SCROLL":
            return min(1.0, abs(progress) * abs(speed) / 100.0)
        return max(0.0, min(1.0, progress))

    @staticmethod
    def _fade_in(state, _animation, progress, amount, _speed):
        progress = max(0.0, min(1.0, progress))
        state.multiply_alpha(1.0 - amount + amount * progress)

    @staticmethod
    def _scroll(state, animation, progress, _amount, speed):
        action = str(animation.get("action") or "SCROLL").upper()
        distance = progress * speed
        if action == "SCROLL_INVERTED":
            distance = -distance
        distance = AnimationTransform._limited_distance(animation, distance)
        angle = _as_number(animation.get("angle", 0.0), 0.0)
        radians = math.radians(angle)
        state.add_horizontal(math.cos(radians) * distance)
        state.add_vertical(math.sin(radians) * distance)

    @staticmethod
    def _limited_distance(animation, distance):
        limit = _as_number(animation.get("limit", 0.0), 0.0)
        if limit <= 0:
            return distance
        return max(-limit, min(limit, distance))
