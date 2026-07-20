"""Determine desktop preview page behavior from KLWP modules."""

import re


class PreviewPageCounter:
    def __init__(self, root_module):
        self._state = {
            "root": root_module,
            "count": 1,
            "has_scroll": False,
        }

    def count(self):
        self._visit(self._state["root"])
        if self._state["has_scroll"]:
            self._state["count"] = max(self._state["count"], 3)
        return self._state["count"]

    def _visit(self, value):
        visitors = {dict: self._visit_mapping, list: self._visit_sequence}
        visitor = visitors.get(type(value))
        if visitor is not None:
            visitor(value)

    def _visit_mapping(self, mapping):
        self._visit_animations(mapping)
        self._visit_events(mapping)
        for child in mapping.values():
            self._visit(child)

    def _visit_sequence(self, sequence):
        for child in sequence:
            self._visit(child)

    def _visit_animations(self, mapping):
        animations = mapping.get("internal_animations", []) or []
        for animation in animations:
            self._record_animation(animation)

    def _record_animation(self, animation):
        if not isinstance(animation, dict):
            return
        if animation.get("type") != "SCROLL":
            return
        self._state["has_scroll"] = True
        match = re.match(r"SCREEN(\d+)$", str(animation.get("center", "")))
        if match is None:
            return
        self._state["count"] = max(self._state["count"], int(match.group(1)))

    def _visit_events(self, mapping):
        events = mapping.get("internal_events", []) or []
        for event in events:
            self._record_event(event)

    def _record_event(self, event):
        if not isinstance(event, dict):
            return
        pattern = r"(?:^|;)i\.PAGE_NUMBER=(\d+)(?:;|$)"
        match = re.search(pattern, str(event.get("intent", "")))
        if match is None:
            return
        page_count = int(match.group(1)) + 1
        self._state["count"] = max(self._state["count"], page_count)


class ScrollFadeRuleDetector:
    def __init__(self, modules):
        self._modules = modules

    def has_triplet(self):
        rules = set()
        for module in self._modules:
            self._add_module_rules(rules, module)
        required = {"BEFORE_CENTER", "CENTER", "AFTER_CENTER"}
        return required <= rules

    @staticmethod
    def _add_module_rules(rules, module):
        animations = module.get("internal_animations", []) or []
        for animation in animations:
            ScrollFadeRuleDetector._add_animation_rule(rules, animation)

    @staticmethod
    def _add_animation_rule(rules, animation):
        if not isinstance(animation, dict):
            return
        if animation.get("type") != "SCROLL":
            return
        if animation.get("action") != "FADE":
            return
        if animation.get("center"):
            return
        rules.add(animation.get("rule", "CENTER"))
