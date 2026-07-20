"""Measure and place KLWP modules in document coordinates."""

from ..shared import *  # noqa: F401,F403
from .layout_context import LayoutRequest
from .placement import PlacementCalculator


class LayoutMixin:
    def _place(self, item, box, width, height, is_root=False, globals_=None):
        request = LayoutRequest(
            item=item, box=box, width=width, height=height,
            is_root=is_root, global_values=globals_,
        )
        return PlacementCalculator(self, request).calculate()

    def _text_of(self, item, globals_=None):
        global_values = globals_ or self._root_globals()
        text = sample_eval(item.get("text_expression", ""), global_values)
        if "UP" in (item.get("text_filter") or []):
            return text.upper()
        return text

    def _item_rotation(self, item, globals_=None):
        handlers = {
            "TextModule": self._text_rotation,
            "ShapeModule": self._shape_rotation,
        }
        handler = handlers.get(item.get("internal_type", ""))
        if handler is None:
            return 0.0
        return handler(item, globals_)

    def _text_rotation(self, item, global_values):
        return self._module_rotation(
            item, "text_rotate_mode", "text_rotate_offset", global_values)

    def _shape_rotation(self, item, global_values):
        return self._module_rotation(
            item, "shape_rotate_mode", "shape_rotate_offset", global_values)

    def _module_rotation(self, item, mode_name, offset_name, global_values):
        mode = str(self._value(item, mode_name, "", global_values))
        if mode.startswith("DEG"):
            return _as_number(mode[3:], 0.0)
        return self._number(item, offset_name, 0.0, global_values)

    def _group_rotation(self, item, globals_=None):
        mode = str(self._value(item, "config_rotate_mode", "", globals_))
        date_values = (globals_ or {}).get("__df__", _DF)
        second = _as_number(date_values.get("ss", 0))
        minute = _as_number(date_values.get("mm", 0)) + second / 60.0
        hour = _as_number(date_values.get("H", 0)) % 12 + minute / 60.0
        rotations = {
            "CLOCK_SECOND": second * 6.0,
            "CLOCK_MINUTE": minute * 6.0,
            "CLOCK_MINUTE_SMOOTH": minute * 6.0,
            "CLOCK_HOUR": hour * 30.0,
            "CLOCK_HOUR_SMOOTH": hour * 30.0,
        }
        if mode in rotations:
            return rotations[mode]
        return self._number(item, "config_rotate_offset", 0.0, globals_)

    @staticmethod
    def _rotated_size(width, height, angle):
        if not angle % 360:
            return width, height
        radians = math.radians(angle)
        rotated_width = abs(width * math.cos(radians)) + abs(height * math.sin(radians))
        rotated_height = abs(width * math.sin(radians)) + abs(height * math.cos(radians))
        return rotated_width, rotated_height

    def _base_item_size(self, item, globals_=None):
        handlers = {
            "ShapeModule": self._shape_size,
            "FontIconModule": self._icon_size,
            "BitmapModule": self._bitmap_size,
            "ProgressModule": self._progress_size,
            "TextModule": self._text_size,
            "StackLayerModule": self._stack_size,
        }
        handler = handlers.get(item.get("internal_type", ""))
        if handler is not None:
            return handler(item, globals_)
        if "viewgroup_items" in item:
            return self._layer_box_size(item, globals_)
        return 100.0, 50.0

    def _shape_size(self, item, global_values):
        width = self._number(item, "shape_width", 50.0, global_values)
        if "shape_height" not in item:
            return width, width
        height = self._number(item, "shape_height", width, global_values)
        return width, height

    def _icon_size(self, item, global_values):
        size = self._number(item, "icon_size", 80.0, global_values)
        return size, size

    def _bitmap_size(self, item, global_values):
        reference = self._value(item, "bitmap_bitmap", "", global_values)
        source = self._bitmap_image(reference)
        width = self._number(item, "bitmap_width", 100.0, global_values)
        if source is not None and source.width:
            return width, width * source.height / source.width
        height = self._number(item, "bitmap_height", width, global_values)
        return width, height

    def _progress_size(self, item, global_values):
        diameter = self._number(item, "style_size", 100.0, global_values)
        style = self._value(item, "style_style", "", global_values)
        if style == "CIRCLE":
            return diameter, diameter
        height = self._number(item, "style_height", 6.0, global_values)
        return diameter, height

    def _text_size(self, item, global_values):
        layout = self._text_layout(item, global_values)
        return layout[4], layout[5]

    def _item_size(self, item, globals_=None):
        width, height = self._base_item_size(item, globals_)
        angle = self._item_rotation(item, globals_)
        return self._rotated_size(width, height, angle)

    @staticmethod
    def _stack_is_horizontal(item):
        return "HORIZONTAL" in str(item.get("config_stacking", ""))

    def _stack_size(self, item, globals_=None):
        children = item.get("viewgroup_items", [])
        if not children:
            return 50.0, 20.0
        sizes = [self._padded_child_size(child, globals_) for child in children]
        margin = self._number(item, "config_margin", 0.0, globals_)
        gap = margin * (len(children) - 1)
        if self._stack_is_horizontal(item):
            return sum(width for width, _height in sizes) + gap, max(height for _width, height in sizes)
        return max(width for width, _height in sizes), sum(height for _width, height in sizes) + gap

    def _padded_child_size(self, child, global_values):
        width, height = self._item_size(child, global_values)
        width += self._number(child, "position_padding_left", 0.0, global_values)
        width += self._number(child, "position_padding_right", 0.0, global_values)
        height += self._number(child, "position_padding_top", 0.0, global_values)
        height += self._number(child, "position_padding_bottom", 0.0, global_values)
        return width, height

    def _layer_box_size(self, item, globals_=None):
        global_values = self._with_local_globals(item, globals_)
        extent = {"width": 0.0, "height": 0.0}
        for child in item.get("viewgroup_items", []):
            self._expand_layer_extent(extent, child, global_values)
        return extent["width"] or 200.0, extent["height"] or 120.0

    def _expand_layer_extent(self, extent, child, global_values):
        width, height = self._item_size(child, global_values)
        anchor = str(child.get("position_anchor") or "CENTER")
        horizontal = self._padding_difference(child, "left", "right", global_values)
        vertical = self._padding_difference(child, "top", "bottom", global_values)
        required_width = self._required_horizontal(anchor, width, horizontal)
        required_height = self._required_vertical(anchor, height, vertical)
        extent["width"] = max(extent["width"], required_width)
        extent["height"] = max(extent["height"], required_height)

    def _padding_difference(self, item, first, second, global_values):
        first_value = self._number(
            item, f"position_padding_{first}", 0.0, global_values)
        second_value = self._number(
            item, f"position_padding_{second}", 0.0, global_values)
        return first_value - second_value

    @staticmethod
    def _required_horizontal(anchor, width, difference):
        if anchor in ("TOPLEFT", "CENTERLEFT", "BOTTOMLEFT"):
            return width + max(0.0, difference)
        if anchor in ("TOPRIGHT", "CENTERRIGHT", "BOTTOMRIGHT"):
            return width + max(0.0, -difference)
        return width + abs(difference)

    @staticmethod
    def _required_vertical(anchor, height, difference):
        if anchor in ("TOPLEFT", "TOP", "TOPRIGHT"):
            return height + max(0.0, difference)
        if anchor in ("BOTTOMLEFT", "BOTTOM", "BOTTOMRIGHT"):
            return height + max(0.0, -difference)
        return height + abs(difference)

    def _bounds(self, item):
        archive = self.memory['archive']
        if item not in archive.modules():
            return None
        document_width, document_height = self.memory['_doc']
        global_values = self._root_globals()
        width, height = self._item_size(item, global_values)
        width, height = max(width, 40), max(height, 30)
        box = (0, 0, document_width, document_height)
        horizontal, vertical = self._place(
            item, box, width, height, is_root=True, globals_=global_values)
        animation = self._animation_transform(item)
        if animation["alpha"] <= 0.001:
            return None
        horizontal += animation["dx"]
        vertical += animation["dy"]
        return horizontal, vertical, width, height
