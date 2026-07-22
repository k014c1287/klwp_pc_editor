"""Render a Komponent as one uniformly scaled child layer."""

from ..shared import *  # noqa: F401,F403


class ComponentRendererMixin:
    def _component_scale(self, item, global_values):
        percentage = self._number(
            item, "config_scale_value", 100.0, global_values)
        return max(0.0, percentage / 100.0)

    def _component_size(self, item, global_values):
        width, height = self._layer_box_size(item, global_values)
        scale = self._component_scale(item, global_values)
        return width * scale, height * scale

    def _paint_component(self, request, placement):
        item = request["item"]
        if item.get("internal_type") != "KomponentModule":
            return False
        scale = self._component_scale(item, request["global_values"])
        if scale <= 0.0:
            return True
        self._paint_scaled_component(request, placement, scale)
        return True

    def _paint_scaled_component(self, request, placement, scale):
        image = request["image"]
        transparent = Image.new("RGBA", image.size, (0, 0, 0, 0))
        starts = self._component_record_starts()
        natural_box = self._component_natural_box(placement, scale)
        children = request["item"].get("viewgroup_items", [])
        for child in children:
            self._paint_item(
                transparent, child, natural_box, request["global_values"])
        transformed = self._scaled_component_image(
            transparent, placement, scale)
        image.alpha_composite(transformed)
        self._transform_component_records(starts, placement, scale)

    @staticmethod
    def _component_natural_box(placement, scale):
        return (
            placement["horizontal"], placement["vertical"],
            placement["width"] / scale, placement["height"] / scale,
        )

    def _component_record_starts(self):
        memory = self.memory
        bounds = memory.optional("_item_bounds", [])
        events = memory.optional("_event_regions", [])
        return len(bounds), len(events)

    @staticmethod
    def _scaled_component_image(image, placement, scale):
        inverse = 1.0 / scale
        origin_horizontal = placement["pixel_horizontal"]
        origin_vertical = placement["pixel_vertical"]
        matrix = (
            inverse, 0.0, origin_horizontal * (1.0 - inverse),
            0.0, inverse, origin_vertical * (1.0 - inverse),
        )
        return image.transform(
            image.size, Image.AFFINE, matrix,
            resample=Resampling.BICUBIC)

    def _transform_component_records(self, starts, placement, scale):
        bounds_start, events_start = starts
        memory = self.memory
        bounds = memory.optional("_item_bounds", [])
        events = memory.optional("_event_regions", [])
        origin = (placement["horizontal"], placement["vertical"])
        self._transform_bounds(bounds, bounds_start, origin, scale)
        self._transform_events(events, events_start, origin, scale)

    def _transform_bounds(self, entries, start, origin, scale):
        for index in range(start, len(entries)):
            item, bounds = entries[index]
            entries[index] = (
                item, self._scaled_bounds(bounds, origin, scale))

    def _transform_events(self, entries, start, origin, scale):
        for index in range(start, len(entries)):
            item, bounds, events = entries[index]
            entries[index] = (
                item, self._scaled_bounds(bounds, origin, scale), events)

    @staticmethod
    def _scaled_bounds(bounds, origin, scale):
        left, top, width, height = bounds
        origin_horizontal, origin_vertical = origin
        left = origin_horizontal + (left - origin_horizontal) * scale
        top = origin_vertical + (top - origin_vertical) * scale
        return left, top, width * scale, height * scale
