"""Small domain values used at file-format boundaries."""

from os import fspath


class TextValue:
    """A string that has already crossed into the domain model."""

    def __init__(self, value):
        self._value = str(value)

    def __str__(self):
        return self._value

    def __bool__(self):
        return bool(self._value)


class NumberValue:
    """A numeric value with explicit integer and float protocols."""

    def __init__(self, value):
        self._value = value

    def __int__(self):
        return int(self._value)

    def __float__(self):
        return float(self._value)


class DocumentSize:
    """The two dimensions that define a KLWP document."""

    def __init__(self, width, height):
        self._width = NumberValue(width)
        self._height = NumberValue(height)

    def json_fields(self):
        return {"width": int(self._width), "height": int(self._height)}


class ArchiveLocation:
    """Filesystem location accepted by pathlib, open and zipfile."""

    def __init__(self, value):
        self._value = fspath(value)

    def __fspath__(self):
        return self._value

    def __str__(self):
        return self._value

