"""Create KLWP-compatible two-colour gradient textures."""

from ..shared import *  # noqa: F401,F403


class GradientRendererMixin:
    def _gradient_tile(self, item, width, height, global_values):
        start = self._rgba(self._value(
            item, "paint_color", "#80FFFFFF", global_values))
        finish = self._rgba(self._value(
            item, "fx_gradient_color", "#00FFFFFF", global_values))
        kind = str(self._value(
            item, "fx_gradient", "HORIZONTAL", global_values)).upper()
        points = self._gradient_points(width, height)
        ratios = map(
            lambda point: self._gradient_ratio(
                item, point, width, height, kind, global_values),
            points)
        colors = map(
            lambda ratio: self._gradient_color(start, finish, ratio), ratios)
        tile = Image.new("RGBA", (width, height))
        tile.putdata(list(colors))
        return tile

    @staticmethod
    def _gradient_points(width, height):
        return ((horizontal, vertical)
                for vertical in range(height)
                for horizontal in range(width))

    def _gradient_ratio(self, item, point, width, height, kind,
                        global_values):
        raw = self._gradient_position(
            item, point, width, height, kind, global_values)
        gradient_width = self._number(
            item, "fx_gradient_width", 100.0, global_values)
        offset = self._number(
            item, "fx_gradient_offset", 0.0, global_values)
        span = max(0.01, abs(gradient_width) / 100.0)
        shifted = raw - offset / 100.0
        if kind == "SWEEP":
            shifted %= 1.0
        return max(0.0, min(1.0, shifted / span))

    def _gradient_position(self, item, point, width, height, kind,
                           global_values):
        horizontal, vertical = point
        if kind == "VERTICAL":
            return vertical / max(1, height - 1)
        if kind == "RADIAL":
            return self._radial_position(point, width, height)
        if kind == "SWEEP":
            return self._sweep_position(point, width, height)
        if kind == "LINEAR":
            angle = self._number(
                item, "fx_gradient_angle", 0.0, global_values)
            return self._linear_position(point, width, height, angle)
        return horizontal / max(1, width - 1)

    @staticmethod
    def _linear_position(point, width, height, angle):
        horizontal, vertical = point
        normalized_horizontal = horizontal / max(1, width - 1) - 0.5
        normalized_vertical = vertical / max(1, height - 1) - 0.5
        radians = math.radians(angle)
        projection = (
            normalized_horizontal * math.cos(radians)
            + normalized_vertical * math.sin(radians))
        return projection + 0.5

    @staticmethod
    def _radial_position(point, width, height):
        horizontal, vertical = point
        radius_horizontal = max(1.0, width / 2.0)
        radius_vertical = max(1.0, height / 2.0)
        offset_horizontal = (horizontal - radius_horizontal) / radius_horizontal
        offset_vertical = (vertical - radius_vertical) / radius_vertical
        return math.sqrt(
            offset_horizontal * offset_horizontal
            + offset_vertical * offset_vertical)

    @staticmethod
    def _sweep_position(point, width, height):
        horizontal, vertical = point
        offset_horizontal = horizontal - width / 2.0
        offset_vertical = vertical - height / 2.0
        radians = math.atan2(offset_vertical, offset_horizontal)
        return (radians / (2.0 * math.pi) + 1.0) % 1.0

    @staticmethod
    def _gradient_color(start, finish, ratio):
        channels = zip(start, finish)
        values = map(
            lambda pair: int(pair[0] + (pair[1] - pair[0]) * ratio),
            channels)
        return tuple(values)
