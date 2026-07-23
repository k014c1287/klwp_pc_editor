"""Mutate KLWP position fields without treating them as absolute coordinates."""

from .modules import DEFAULT_ANCHOR


RIGHT_ANCHORS = ("TOPRIGHT", "CENTERRIGHT", "BOTTOMRIGHT")
BOTTOM_ANCHORS = ("BOTTOMLEFT", "BOTTOM", "BOTTOMRIGHT")
CENTER_HORIZONTAL_ANCHORS = ("TOP", "CENTER", "BOTTOM")
CENTER_VERTICAL_ANCHORS = ("CENTERLEFT", "CENTER", "CENTERRIGHT")
UPWARD_OFFSET_ANCHORS = (
    "CENTERLEFT", "CENTER", "CENTERRIGHT",
    "BOTTOMLEFT", "BOTTOM", "BOTTOMRIGHT",
)


class PositionMutation:
    """Move one item through the fields used by its KLWP layout context."""

    def __init__(self, item, is_root):
        self._values = {"item": item, "is_root": is_root}

    def move_by(self, horizontal, vertical):
        if self._values["is_root"]:
            self._move_offsets(horizontal, vertical)
            return
        self._move_margins(horizontal, vertical)

    def _move_offsets(self, horizontal, vertical):
        item = self._values["item"]
        anchor = item.get("position_anchor") or DEFAULT_ANCHOR
        self._increase(item, "position_offset_x", horizontal * self._horizontal_sign(anchor))
        self._increase(item, "position_offset_y", vertical * self._vertical_sign(anchor))

    def _move_margins(self, horizontal, vertical):
        item = self._values["item"]
        anchor = item.get("position_anchor") or DEFAULT_ANCHOR
        self._move_horizontal_margin(item, anchor, horizontal)
        self._move_vertical_margin(item, anchor, vertical)

    def _move_horizontal_margin(self, item, anchor, difference):
        if anchor in CENTER_HORIZONTAL_ANCHORS:
            self._increase(item, "position_padding_left", difference)
            self._increase(item, "position_padding_right", -difference)
            return
        if anchor in RIGHT_ANCHORS:
            self._increase(item, "position_padding_right", -difference)
            return
        self._increase(item, "position_padding_left", difference)

    def _move_vertical_margin(self, item, anchor, difference):
        if anchor in CENTER_VERTICAL_ANCHORS:
            self._increase(item, "position_padding_top", difference)
            self._increase(item, "position_padding_bottom", -difference)
            return
        if anchor in BOTTOM_ANCHORS:
            self._increase(item, "position_padding_bottom", -difference)
            return
        self._increase(item, "position_padding_top", difference)

    @staticmethod
    def _horizontal_sign(anchor):
        if anchor in RIGHT_ANCHORS:
            return -1.0
        return 1.0

    @staticmethod
    def _vertical_sign(anchor):
        if anchor in UPWARD_OFFSET_ANCHORS:
            return -1.0
        return 1.0

    @staticmethod
    def _increase(item, name, difference):
        current = float(item.get(name, 0.0) or 0.0)
        item[name] = round(current + difference, 1)
