"""First-class result returned by text measurement."""


class TextLayoutResult:
    ORDER = (
        "text", "font", "spacing", "bounds",
        "width", "height", "alignment",
    )

    def __init__(self, **values):
        self._values = values

    def __iter__(self):
        return iter(tuple(self._values[name] for name in self.ORDER))

    def __getitem__(self, index):
        return self._values[self.ORDER[index]]
