"""First-class collections passed through the rendering pipeline."""


class PaintRequest:
    def __init__(self, **values):
        self._values = values

    def __getitem__(self, name):
        return self._values[name]

    def __setitem__(self, name, value):
        self._values[name] = value


class ItemPlacement:
    def __init__(self, **values):
        self._values = values

    def __getitem__(self, name):
        return self._values[name]


class StackCursor:
    def __init__(self, horizontal, vertical):
        self._coordinates = {"horizontal": horizontal, "vertical": vertical}

    def horizontal(self):
        return self._coordinates["horizontal"]

    def vertical(self):
        return self._coordinates["vertical"]

    def move_horizontal(self, distance):
        self._coordinates["horizontal"] += distance

    def move_vertical(self, distance):
        self._coordinates["vertical"] += distance
