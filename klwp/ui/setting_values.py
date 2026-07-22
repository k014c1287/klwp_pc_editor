"""Small setting queries shared by animation, event and switch dialogs."""

import re


def switch_global_names(global_values):
    if not isinstance(global_values, dict):
        return []
    names = (
        str(name) for name, entry in global_values.items()
        if isinstance(entry, dict) and entry.get("type") == "SWITCH"
    )
    return sorted(names)


def first_or_empty(values):
    if values:
        return values[0]
    return ""


class TouchActionValues:
    @staticmethod
    def update(original, action, switch="", intent="", music_action=""):
        event = dict(original)
        event["type"] = "SINGLE_TAP"
        event["action"] = action
        handlers = {
            "SWITCH_GLOBAL": TouchActionValues._switch,
            "MUSIC": TouchActionValues._music,
            "LAUNCH_APP": TouchActionValues._intent,
            "LAUNCH_SHORTCUT": TouchActionValues._intent,
            "OPEN_LINK": TouchActionValues._intent,
            "KUSTOM_ACTION": TouchActionValues._kustom,
        }
        handler = handlers.get(action, TouchActionValues._empty)
        handler(event, switch, intent, music_action)
        return event

    @staticmethod
    def _switch(event, switch, _intent, _music_action):
        TouchActionValues._clear_external(event)
        event["switch"] = switch

    @staticmethod
    def _music(event, _switch, _intent, music_action):
        TouchActionValues._clear_external(event)
        event.pop("switch", None)
        if music_action:
            event["music_action"] = music_action

    @staticmethod
    def _intent(event, _switch, intent, _music_action):
        event.pop("switch", None)
        event.pop("music_action", None)
        event.pop("kustom_action", None)
        event["intent"] = intent

    @staticmethod
    def _kustom(event, _switch, action, _music_action):
        event.pop("switch", None)
        event.pop("music_action", None)
        event.pop("intent", None)
        event["kustom_action"] = action

    @staticmethod
    def _empty(event, _switch, _intent, _music_action):
        event.pop("switch", None)
        TouchActionValues._clear_external(event)

    @staticmethod
    def _clear_external(event):
        event.pop("intent", None)
        event.pop("music_action", None)
        event.pop("kustom_action", None)


class SwitchReferenceCounter:
    def __init__(self, name):
        escaped = re.escape(str(name))
        self._name = name
        self._pattern = re.compile(
            r"\bgv\(\s*" + escaped + r"\s*(?:,|\))", re.I)

    def count(self, value):
        handlers = {
            dict: self._mapping_count,
            list: self._sequence_count,
            str: self._string_count,
        }
        handler = handlers.get(type(value), self._zero)
        return handler(value)

    def _mapping_count(self, mapping):
        own_count = int(
            mapping.get("trigger") == self._name
            or mapping.get("switch") == self._name)
        return own_count + sum(map(self.count, mapping.values()))

    def _sequence_count(self, sequence):
        return sum(map(self.count, sequence))

    def _string_count(self, value):
        pattern = self._pattern
        return int(bool(pattern.search(value)))

    @staticmethod
    def _zero(_value):
        return 0
