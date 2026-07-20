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
