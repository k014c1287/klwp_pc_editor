"""Calculate one module's anchored position inside a parent box."""

from ..formula import _as_number
from ..modules import DEFAULT_ANCHOR
from .layout_context import ModulePadding


class PlacementCalculator:
    def __init__(self, owner, request):
        self._owner = owner
        self._request = request

    def calculate(self):
        padding = self._padding()
        version = self._preset_version()
        self._adjust_padding(padding, version)
        horizontal = self._base_horizontal()
        vertical = self._base_vertical()
        horizontal = self._horizontal_with_padding(horizontal, padding)
        vertical = self._vertical_with_padding(vertical, padding)
        return self._root_offsets(horizontal, vertical, version)

    def _padding(self):
        item = self._request["item"]
        global_values = self._request["global_values"]
        owner = self._owner
        number = owner._number
        return ModulePadding(
            number(item, "position_padding_left", 0.0, global_values),
            number(item, "position_padding_right", 0.0, global_values),
            number(item, "position_padding_top", 0.0, global_values),
            number(item, "position_padding_bottom", 0.0, global_values),
        )

    def _preset_version(self):
        owner = self._owner
        memory = owner.memory
        archive = memory['archive']
        information = archive["preset"].get("preset_info", {})
        return int(information.get("version", 15) or 15)

    def _adjust_padding(self, padding, version):
        if self._is_component():
            self._adjust_component_padding(padding)
            return
        if version <= 10:
            self._adjust_legacy_padding(padding)

    def _adjust_component_padding(self, padding):
        item = self._request["item"]
        global_values = self._request["global_values"]
        owner = self._owner
        scale = owner._number(
            item, "config_scale_value", 100.0, global_values) / 100.0
        if scale > 0:
            padding.divide(scale)

    def _adjust_legacy_padding(self, padding):
        owner = self._owner
        memory = owner.memory
        archive = memory['archive']
        information = archive["preset"].get("preset_info", {})
        multiplier = _as_number(information.get("width", 540), 540.0) / 720.0
        anchor = self._anchor()
        if anchor in ("TOP", "CENTER", "BOTTOM"):
            padding.scale_horizontal(multiplier)
        if anchor in ("CENTERLEFT", "CENTER", "CENTERRIGHT"):
            padding.scale_vertical(multiplier)

    def _base_horizontal(self):
        box_horizontal, _box_vertical, box_width, _box_height = self._request["box"]
        width = self._request["width"]
        anchor = self._anchor()
        if anchor in ("TOPLEFT", "CENTERLEFT", "BOTTOMLEFT"):
            return box_horizontal
        if anchor in ("TOPRIGHT", "CENTERRIGHT", "BOTTOMRIGHT"):
            return box_horizontal + box_width - width
        return box_horizontal + box_width / 2 - width / 2

    def _base_vertical(self):
        _box_horizontal, box_vertical, _box_width, box_height = self._request["box"]
        height = self._request["height"]
        anchor = self._anchor()
        if anchor in ("TOPLEFT", "TOP", "TOPRIGHT"):
            return box_vertical
        if anchor in ("BOTTOMLEFT", "BOTTOM", "BOTTOMRIGHT"):
            return box_vertical + box_height - height
        return box_vertical + box_height / 2 - height / 2

    def _horizontal_with_padding(self, horizontal, padding):
        anchor = self._anchor()
        if anchor in ("TOPLEFT", "CENTERLEFT", "BOTTOMLEFT"):
            return horizontal + padding["left"]
        if anchor in ("TOPRIGHT", "CENTERRIGHT", "BOTTOMRIGHT"):
            return horizontal - padding["right"]
        return horizontal + padding.horizontal_difference() / 2

    def _vertical_with_padding(self, vertical, padding):
        anchor = self._anchor()
        if anchor in ("TOPLEFT", "TOP", "TOPRIGHT"):
            return vertical + padding["top"]
        if anchor in ("BOTTOMLEFT", "BOTTOM", "BOTTOMRIGHT"):
            return vertical - padding["bottom"]
        return vertical + padding.vertical_difference() / 2

    def _root_offsets(self, horizontal, vertical, version):
        if not self._request["is_root"]:
            return horizontal, vertical
        horizontal_offset, vertical_offset = self._offsets(version)
        horizontal += self._horizontal_offset(horizontal_offset)
        vertical += self._vertical_offset(vertical_offset)
        return horizontal, vertical

    def _offsets(self, version):
        item = self._request["item"]
        global_values = self._request["global_values"]
        owner = self._owner
        horizontal = owner._number(
            item, "position_offset_x", 0.0, global_values)
        vertical = owner._number(
            item, "position_offset_y", 0.0, global_values)
        if version <= 10 and item.get("internal_type") == "OverlapLayerModule":
            vertical = 0.0
        return horizontal, vertical

    def _horizontal_offset(self, offset):
        if self._anchor() in ("TOPRIGHT", "CENTERRIGHT", "BOTTOMRIGHT"):
            return -offset
        return offset

    def _vertical_offset(self, offset):
        anchor = self._anchor()
        if anchor in ("CENTER", "CENTERLEFT", "CENTERRIGHT"):
            return -offset
        if anchor in ("BOTTOMLEFT", "BOTTOM", "BOTTOMRIGHT"):
            return -offset
        return offset

    def _anchor(self):
        return self._request["item"].get("position_anchor") or DEFAULT_ANCHOR

    def _is_component(self):
        item = self._request["item"]
        return item.get("internal_type") == "KomponentModule"
