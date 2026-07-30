"""Alignment snapping for canvas drag operations."""


class SnapTargets:
    def __init__(self, vertical, horizontal):
        self._values = {
            "vertical": tuple(vertical), "horizontal": tuple(horizontal),
        }

    @staticmethod
    def from_layout(document_size, item_bounds, selected):
        document_width, document_height = document_size
        vertical = SnapTargets._ruler_values(document_width)
        horizontal = SnapTargets._ruler_values(document_height)
        others = filter(lambda entry: entry[0] is not selected, item_bounds)
        bounds = tuple(entry[1] for entry in others)
        vertical += tuple(
            value for bound in bounds
            for value in SnapTargets._horizontal_features(bound))
        horizontal += tuple(
            value for bound in bounds
            for value in SnapTargets._vertical_features(bound))
        return SnapTargets(vertical, horizontal)

    @staticmethod
    def _ruler_values(length):
        limit = int(length // 100) * 100
        values = tuple(float(value) for value in range(0, limit + 1, 100))
        center = float(length) / 2.0
        return values + (center, float(length))

    @staticmethod
    def _horizontal_features(bounds):
        left, _top, width, _height = bounds
        return left, left + width / 2.0, left + width

    @staticmethod
    def _vertical_features(bounds):
        _left, top, _width, height = bounds
        return top, top + height / 2.0, top + height

    def vertical(self):
        return self._values["vertical"]

    def horizontal(self):
        return self._values["horizontal"]


class SnapResult:
    def __init__(self, horizontal, vertical, vertical_guide, horizontal_guide):
        self._values = {
            "horizontal": horizontal, "vertical": vertical,
            "vertical_guide": vertical_guide,
            "horizontal_guide": horizontal_guide,
        }

    def movement(self):
        return self._values["horizontal"], self._values["vertical"]

    def correction(self, horizontal, vertical):
        snapped_horizontal, snapped_vertical = self.movement()
        return (
            snapped_horizontal - horizontal,
            snapped_vertical - vertical,
        )

    def guides(self):
        guides = []
        vertical = self._values["vertical_guide"]
        horizontal = self._values["horizontal_guide"]
        if vertical is not None:
            guides.append(("vertical", vertical))
        if horizontal is not None:
            guides.append(("horizontal", horizontal))
        return tuple(guides)


class SnapEngine:
    def __init__(self, targets, tolerance):
        self._values = {"targets": targets, "tolerance": float(tolerance)}

    def apply(self, bounds, horizontal, vertical):
        targets = self._values["targets"]
        tolerance = self._values["tolerance"]
        moving_horizontal = SnapTargets._horizontal_features(bounds)
        moving_vertical = SnapTargets._vertical_features(bounds)
        snapped_horizontal, vertical_guide = self._snap_axis(
            moving_horizontal, targets.vertical(), horizontal, tolerance)
        snapped_vertical, horizontal_guide = self._snap_axis(
            moving_vertical, targets.horizontal(), vertical, tolerance)
        return SnapResult(
            snapped_horizontal, snapped_vertical,
            vertical_guide, horizontal_guide)

    @staticmethod
    def _snap_axis(features, targets, movement, tolerance):
        candidates = tuple(
            (abs(target - feature - movement),
             target - feature - movement, target)
            for feature in features for target in targets)
        if not candidates:
            return movement, None
        distance, correction, guide = min(candidates, key=lambda value: value[0])
        if distance > tolerance:
            return movement, None
        return movement + correction, guide
