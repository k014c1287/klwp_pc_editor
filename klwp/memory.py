"""First-class collection containing mutable application state."""


class ApplicationMemory:
    """Keeps EditorApp itself free from dozens of unrelated instance fields."""

    def __init__(self):
        self._values = {}

    def __getitem__(self, name):
        return self._values[name]

    def __setitem__(self, name, value):
        self._values[name] = value

    def optional(self, name, default=None):
        values = self._values
        return values.get(name, default)

    def contains(self, name):
        return name in self._values

