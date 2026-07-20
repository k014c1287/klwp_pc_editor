"""Value collections used while calculating module layout."""


class LayoutRequest:
    def __init__(self, **values):
        self._values = values

    def __getitem__(self, name):
        return self._values[name]


class ModulePadding:
    def __init__(self, left, right, top, bottom):
        self._values = {
            "left": left, "right": right, "top": top, "bottom": bottom,
        }

    def __getitem__(self, name):
        return self._values[name]

    def divide(self, divisor):
        for name in self._values:
            self._values[name] /= divisor

    def scale_horizontal(self, multiplier):
        self._values["left"] *= multiplier
        self._values["right"] *= multiplier

    def scale_vertical(self, multiplier):
        self._values["top"] *= multiplier
        self._values["bottom"] *= multiplier

    def horizontal_difference(self):
        return self._values["left"] - self._values["right"]

    def vertical_difference(self):
        return self._values["top"] - self._values["bottom"]
