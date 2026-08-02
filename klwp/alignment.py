"""Calculate visual alignment and equal-gap distribution movements."""


class AlignmentLayout:
    def __init__(self, entries):
        self._entries = tuple(entries)

    def movements(self, operation):
        actions = {
            "left": self._align_left,
            "center_horizontal": self._align_center_horizontal,
            "right": self._align_right,
            "top": self._align_top,
            "center_vertical": self._align_center_vertical,
            "bottom": self._align_bottom,
            "distribute_horizontal": self._distribute_horizontal,
            "distribute_vertical": self._distribute_vertical,
        }
        return actions[operation]()

    def _align_left(self):
        target = min(bounds[0] for _item, bounds in self._entries)
        return self._horizontal_moves(lambda bounds: target - bounds[0])

    def _align_center_horizontal(self):
        left = min(bounds[0] for _item, bounds in self._entries)
        right = max(self._right(bounds) for _item, bounds in self._entries)
        target = (left + right) / 2.0
        return self._horizontal_moves(
            lambda bounds: target - self._horizontal_center(bounds))

    def _align_right(self):
        target = max(self._right(bounds) for _item, bounds in self._entries)
        return self._horizontal_moves(
            lambda bounds: target - self._right(bounds))

    def _align_top(self):
        target = min(bounds[1] for _item, bounds in self._entries)
        return self._vertical_moves(lambda bounds: target - bounds[1])

    def _align_center_vertical(self):
        top = min(bounds[1] for _item, bounds in self._entries)
        bottom = max(self._bottom(bounds) for _item, bounds in self._entries)
        target = (top + bottom) / 2.0
        return self._vertical_moves(
            lambda bounds: target - self._vertical_center(bounds))

    def _align_bottom(self):
        target = max(self._bottom(bounds) for _item, bounds in self._entries)
        return self._vertical_moves(
            lambda bounds: target - self._bottom(bounds))

    def _horizontal_moves(self, difference):
        return tuple(
            (item, difference(bounds), 0.0)
            for item, bounds in self._entries)

    def _vertical_moves(self, difference):
        return tuple(
            (item, 0.0, difference(bounds))
            for item, bounds in self._entries)

    def _distribute_horizontal(self):
        return self._distributed(0)

    def _distribute_vertical(self):
        return self._distributed(1)

    def _distributed(self, axis):
        dimension = axis + 2
        entries = sorted(self._entries, key=lambda entry: entry[1][axis])
        first_bounds = entries[0][1]
        last_bounds = entries[-1][1]
        start = first_bounds[axis]
        end = last_bounds[axis] + last_bounds[dimension]
        total = sum(bounds[dimension] for _item, bounds in entries)
        gap = (end - start - total) / float(len(entries) - 1)
        return self._distribution_moves(entries, axis, dimension, start, gap)

    @staticmethod
    def _distribution_moves(entries, axis, dimension, start, gap):
        cursor = start
        movements = []
        for item, bounds in entries:
            difference = cursor - bounds[axis]
            movements.append((item, *AlignmentLayout._vector(axis, difference)))
            cursor += bounds[dimension] + gap
        return tuple(movements)

    @staticmethod
    def _vector(axis, difference):
        if axis == 0:
            return difference, 0.0
        return 0.0, difference

    @staticmethod
    def _right(bounds):
        return bounds[0] + bounds[2]

    @staticmethod
    def _bottom(bounds):
        return bounds[1] + bounds[3]

    @staticmethod
    def _horizontal_center(bounds):
        return bounds[0] + bounds[2] / 2.0

    @staticmethod
    def _vertical_center(bounds):
        return bounds[1] + bounds[3] / 2.0
