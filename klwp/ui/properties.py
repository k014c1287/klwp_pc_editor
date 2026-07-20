"""Property editing and dirty-history integration."""

from ..shared import *  # noqa: F401,F403
from .property_panel import AnchorChoices, JsonEditorDialog, PropertyPanelBuilder


class PropertyPanelMixin:
    INVALID = object()
    NUMERIC_PROPERTIES = {
        "position_offset_x", "position_offset_y",
        "shape_width", "shape_height", "shape_corners",
        "text_size", "icon_size", "bitmap_width", "bitmap_alpha",
    }

    def _build_props(self):
        PropertyPanelBuilder(self, self.memory['selected']).build()

    def _apply_prop(self, key, variable):
        self._apply_property_value(key, variable.get())

    def _apply_property_value(self, key, raw):
        item = self.memory['selected']
        if item is None:
            return
        value = self._converted_property(
            raw, item.get(key), key)
        if value is self.INVALID:
            return
        item[key] = value
        self._mark_dirty()
        self._render()
        self._rebuild_tree(select=item)

    def _converted_property(self, raw, old, key):
        converters = {"position_anchor": AnchorChoices.to_internal}
        converter = converters.get(key)
        if converter is not None:
            return converter(raw)
        is_numeric = isinstance(old, float) or key in self.NUMERIC_PROPERTIES
        if not is_numeric:
            return raw
        try:
            return float(raw)
        except ValueError:
            return self.INVALID

    def _edit_json(self):
        item = self.memory['selected']
        if item is not None:
            JsonEditorDialog(self, item).show()

    def _mark_dirty(self):
        current = self._snapshot_archive()
        self.memory['history'].record(current)
        self.memory['dirty'] = self.memory['history'].dirty()
        self._update_history_ui()
