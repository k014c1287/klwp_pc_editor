"""Geometry and state for direct manipulation resize handles."""


class ResizeHandleSet:
    POSITIONS = {
        "NW": (0.0, 0.0), "N": (0.5, 0.0), "NE": (1.0, 0.0),
        "E": (1.0, 0.5), "SE": (1.0, 1.0), "S": (0.5, 1.0),
        "SW": (0.0, 1.0), "W": (0.0, 0.5),
    }
    CURSORS = {
        "N": "sb_v_double_arrow", "S": "sb_v_double_arrow",
        "E": "sb_h_double_arrow", "W": "sb_h_double_arrow",
        "NW": "crosshair", "NE": "crosshair",
        "SE": "crosshair", "SW": "crosshair",
    }

    @staticmethod
    def supports(item):
        if not isinstance(item, dict):
            return False
        return item.get("internal_type") in ("ShapeModule", "BitmapModule")

    @staticmethod
    def positions(bounds):
        left, top, width, height = bounds
        values = ResizeHandleSet.POSITIONS
        return tuple(
            (name, left + width * factors[0], top + height * factors[1])
            for name, factors in values.items())

    @staticmethod
    def hit(bounds, horizontal, vertical, tolerance):
        left, top, width, height = bounds
        right = left + width
        bottom = top + height
        near_left = abs(horizontal - left) <= tolerance
        near_right = abs(horizontal - right) <= tolerance
        near_top = abs(vertical - top) <= tolerance
        near_bottom = abs(vertical - bottom) <= tolerance
        within_horizontal = left - tolerance <= horizontal <= right + tolerance
        within_vertical = top - tolerance <= vertical <= bottom + tolerance
        checks = (
            ("NW", near_left and near_top), ("NE", near_right and near_top),
            ("SE", near_right and near_bottom), ("SW", near_left and near_bottom),
            ("N", near_top and within_horizontal),
            ("E", near_right and within_vertical),
            ("S", near_bottom and within_horizontal),
            ("W", near_left and within_vertical),
        )
        matches = filter(lambda entry: entry[1], checks)
        match = next(matches, None)
        if match is None:
            return None
        return match[0]

    @staticmethod
    def cursor(handle):
        cursors = ResizeHandleSet.CURSORS
        return cursors.get(handle, "")


class ResizeSession:
    MINIMUM_WIDTH = 40.0
    MINIMUM_HEIGHT = 30.0
    HORIZONTAL_DIRECTIONS = {
        "NW": -1.0, "W": -1.0, "SW": -1.0,
        "N": 0.0, "S": 0.0,
        "NE": 1.0, "E": 1.0, "SE": 1.0,
    }
    VERTICAL_DIRECTIONS = {
        "NW": -1.0, "N": -1.0, "NE": -1.0,
        "W": 0.0, "E": 0.0,
        "SW": 1.0, "S": 1.0, "SE": 1.0,
    }
    HORIZONTAL_FACTORS = {
        "NW": 1.0, "W": 1.0, "SW": 1.0,
        "N": 0.5, "S": 0.5,
        "NE": 0.0, "E": 0.0, "SE": 0.0,
    }
    VERTICAL_FACTORS = {
        "NW": 1.0, "N": 1.0, "NE": 1.0,
        "W": 0.5, "E": 0.5,
        "SW": 0.0, "S": 0.0, "SE": 0.0,
    }

    def __init__(self, item, handle, pointer, bounds, base_size):
        self._values = {
            "item": item, "handle": handle, "pointer": pointer,
            "bounds": bounds, "base_size": base_size, "changed": False,
        }

    def selected_item(self):
        return self._values["item"]

    def apply(self, horizontal, vertical):
        values = self._values
        initial_horizontal, initial_vertical = values["pointer"]
        difference_horizontal = horizontal - initial_horizontal
        difference_vertical = vertical - initial_vertical
        target = self._target(difference_horizontal, difference_vertical)
        self._apply_dimensions(target)
        values["changed"] = True
        return target

    def _target(self, difference_horizontal, difference_vertical):
        values = self._values
        item = values["item"]
        handlers = {"BitmapModule": self._locked_dimensions}
        handler = handlers.get(item.get("internal_type"), self._free_dimensions)
        width, height = handler(difference_horizontal, difference_vertical)
        left, top, old_width, old_height = values["bounds"]
        handle = values["handle"]
        horizontal_factor = self.HORIZONTAL_FACTORS[handle]
        vertical_factor = self.VERTICAL_FACTORS[handle]
        left += (old_width - width) * horizontal_factor
        top += (old_height - height) * vertical_factor
        return left, top, width, height

    def _free_dimensions(self, difference_horizontal, difference_vertical):
        values = self._values
        _left, _top, width, height = values["bounds"]
        handle = values["handle"]
        horizontal_direction = self.HORIZONTAL_DIRECTIONS[handle]
        vertical_direction = self.VERTICAL_DIRECTIONS[handle]
        width += difference_horizontal * horizontal_direction
        height += difference_vertical * vertical_direction
        return max(self.MINIMUM_WIDTH, width), max(self.MINIMUM_HEIGHT, height)

    def _locked_dimensions(self, difference_horizontal, difference_vertical):
        values = self._values
        _left, _top, width, height = values["bounds"]
        handle = values["handle"]
        horizontal_direction = self.HORIZONTAL_DIRECTIONS[handle]
        vertical_direction = self.VERTICAL_DIRECTIONS[handle]
        scales = [1.0]
        if horizontal_direction:
            scales.append((width + difference_horizontal * horizontal_direction) / width)
        if vertical_direction:
            scales.append((height + difference_vertical * vertical_direction) / height)
        scale = max(scales, key=self._scale_distance)
        minimum_scale = max(
            self.MINIMUM_WIDTH / width, self.MINIMUM_HEIGHT / height)
        scale = max(minimum_scale, scale)
        return width * scale, height * scale

    @staticmethod
    def _scale_distance(scale):
        return abs(scale - 1.0)

    def _apply_dimensions(self, target):
        values = self._values
        item = values["item"]
        handlers = {
            "ShapeModule": self._apply_shape_dimensions,
            "BitmapModule": self._apply_bitmap_dimensions,
        }
        handler = handlers.get(item.get("internal_type"))
        if handler is not None:
            handler(target)

    def _apply_shape_dimensions(self, target):
        values = self._values
        item = values["item"]
        _left, _top, old_width, old_height = values["bounds"]
        base_width, base_height = values["base_size"]
        _target_left, _target_top, width, height = target
        item["shape_width"] = round(base_width * width / old_width, 1)
        item["shape_height"] = round(base_height * height / old_height, 1)

    def _apply_bitmap_dimensions(self, target):
        values = self._values
        item = values["item"]
        _left, _top, old_width, _old_height = values["bounds"]
        base_width, _base_height = values["base_size"]
        _target_left, _target_top, width, _height = target
        item["bitmap_width"] = round(base_width * width / old_width, 1)

    def changed(self):
        return bool(self._values["changed"])
