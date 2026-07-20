"""First-class collections owned by the KLWP domain."""


class ArchiveContents:
    """All mutable members of a KLWP archive behind one collection."""

    _EMPTY = {
        "preset": None,
        "bitmaps": None,
        "fonts": None,
        "extras": None,
        "path": None,
    }

    def __init__(self):
        self._entries = {}
        self.clear()

    def __getitem__(self, name):
        return self._entries[name]

    def __setitem__(self, name, value):
        self._entries[name] = value

    def clear(self):
        self._entries = dict(self._EMPTY)
        self._entries["bitmaps"] = {}
        self._entries["fonts"] = {}
        self._entries["extras"] = {}

    def asset_groups(self):
        names = ("extras", "fonts", "bitmaps")
        return tuple(self._entries[name] for name in names)

