"""Render bitmap, icon and progress module content."""

from ..shared import *  # noqa: F401,F403


class ContentRendererMixin:
    def _paint_bitmap(self, image, item, horizontal, vertical, width, height,
                      globals_=None):
        reference = self._value(item, "bitmap_bitmap", "", globals_)
        source = self._bitmap_image(reference)
        if source is None:
            return
        resized = source.resize((width, height), Resampling.LANCZOS)
        tile = resized.copy()
        opacity = self._number(item, "bitmap_alpha", 100.0, globals_)
        opacity = max(0.0, min(100.0, opacity))
        self._apply_bitmap_opacity(tile, opacity)
        image.alpha_composite(tile, (horizontal, vertical))

    @staticmethod
    def _apply_bitmap_opacity(tile, opacity):
        if opacity >= 100:
            return
        alpha_channel = tile.getchannel("A")
        table = lambda value: int(value * opacity / 100.0)
        tile.putalpha(alpha_channel.point(table))

    def _paint_icon(self, image, drawing, item, horizontal, vertical,
                    width, height, globals_=None):
        color = self._rgba(self._value(
            item, "paint_color", "#FFFFFFFF", globals_))
        if color[3] <= 10:
            return
        raw_icon = self._resolved_icon(item, globals_)
        name, paths, viewbox = decode_kustom_icon(raw_icon)
        if paths:
            self._paint_svg_icon(
                image, raw_icon, paths, viewbox, horizontal, vertical,
                width, height, color)
            return
        self._paint_fallback_icon(
            drawing, name, horizontal, vertical, width, height, color)

    def _resolved_icon(self, item, global_values):
        raw_icon = str(self._value(item, "icon_icon", "", global_values))
        stored_icon = str(item.get("icon_icon", ""))
        if "#" not in raw_icon and "#" in stored_icon:
            return stored_icon
        return raw_icon

    def _paint_svg_icon(self, image, raw_icon, paths, viewbox,
                        horizontal, vertical, width, height, color):
        key = ("icon", raw_icon[:80], width, height)
        mask = self.memory['photo_cache'].get(key)
        if mask is None:
            mask = self._build_svg_icon_mask(paths, viewbox, width, height)
            self.memory['photo_cache'][key] = mask
        tile = Image.new("RGBA", (width, height), color)
        opacity = Image.new("L", (width, height), color[3])
        tile.putalpha(ImageChops.multiply(mask, opacity))
        image.alpha_composite(tile, (horizontal, vertical))

    @staticmethod
    def _build_svg_icon_mask(paths, viewbox, width, height):
        mask = Image.new("L", (width, height), 0)
        masks = map(
            lambda path: svg_path_mask(path, width, height, viewbox=viewbox),
            paths)
        for path_mask in filter(None, masks):
            mask = ImageChops.lighter(mask, path_mask)
        return mask

    def _paint_fallback_icon(self, drawing, name, horizontal, vertical,
                             width, height, color):
        normalized = (name or "").lower()
        center_horizontal = horizontal + width / 2
        center_vertical = vertical + height / 2
        radius = min(width, height) * 0.38
        handler = self._fallback_icon_handler(normalized)
        handler(drawing, center_horizontal, center_vertical, radius, color)

    def _fallback_icon_handler(self, name):
        if "play" in name:
            return self._fallback_play
        if "pause" in name:
            return self._fallback_pause
        if "next" in name or "skip" in name:
            return self._fallback_next
        if "previous" in name:
            return self._fallback_previous
        if "wifi" in name:
            return self._fallback_wifi
        return self._fallback_circle

    @staticmethod
    def _fallback_play(drawing, horizontal, vertical, radius, color):
        drawing.polygon([
            (horizontal - radius * 0.6, vertical - radius),
            (horizontal - radius * 0.6, vertical + radius),
            (horizontal + radius, vertical),
        ], fill=color)

    @staticmethod
    def _fallback_pause(drawing, horizontal, vertical, radius, color):
        bar_width = radius * 0.5
        drawing.rectangle([
            horizontal - radius, vertical - radius,
            horizontal - radius + bar_width, vertical + radius,
        ], fill=color)
        drawing.rectangle([
            horizontal + radius - bar_width, vertical - radius,
            horizontal + radius, vertical + radius,
        ], fill=color)

    @staticmethod
    def _fallback_next(drawing, horizontal, vertical, radius, color):
        drawing.polygon([
            (horizontal - radius, vertical - radius),
            (horizontal - radius, vertical + radius),
            (horizontal + radius * 0.4, vertical),
        ], fill=color)
        drawing.rectangle([
            horizontal + radius * 0.5, vertical - radius,
            horizontal + radius * 0.9, vertical + radius,
        ], fill=color)

    @staticmethod
    def _fallback_previous(drawing, horizontal, vertical, radius, color):
        drawing.polygon([
            (horizontal + radius, vertical - radius),
            (horizontal + radius, vertical + radius),
            (horizontal - radius * 0.4, vertical),
        ], fill=color)
        drawing.rectangle([
            horizontal - radius * 0.9, vertical - radius,
            horizontal - radius * 0.5, vertical + radius,
        ], fill=color)

    @staticmethod
    def _fallback_wifi(drawing, horizontal, vertical, radius, color):
        for multiplier in (1.0, 0.66, 0.33):
            drawing.arc([
                horizontal - radius * multiplier,
                vertical - radius * multiplier,
                horizontal + radius * multiplier,
                vertical + radius * multiplier,
            ], start=215, end=325, fill=color,
                width=max(2, int(radius * 0.18)))

    @staticmethod
    def _fallback_circle(drawing, horizontal, vertical, radius, color):
        drawing.ellipse([
            horizontal - radius, vertical - radius,
            horizontal + radius, vertical + radius,
        ], outline=color, width=max(2, int(radius * 0.22)))

    def _paint_progress(self, _image, drawing, item, horizontal, vertical,
                        scale, globals_=None):
        color = self._progress_color(item, globals_)
        style = self._value(item, "style_style", "", globals_)
        if style == "CIRCLE":
            self._paint_circular_progress(
                drawing, item, horizontal, vertical, scale, color, globals_)
            return
        self._paint_linear_progress(
            drawing, item, horizontal, vertical, scale, color, globals_)

    def _progress_color(self, item, global_values):
        color = self._value(item, "progress_color", None, global_values)
        if color is None:
            color = self._value(
                item, "paint_color", "#FF8E96F2", global_values)
        return self._rgba(color)

    def _paint_circular_progress(self, drawing, item, horizontal, vertical,
                                 scale, color, global_values):
        diameter = self._number(item, "style_size", 100.0, global_values) * scale
        line_width = self._number(item, "style_height", 4.0, global_values)
        line_width = max(1, int(line_width * scale))
        drawing.arc([
            horizontal, vertical, horizontal + diameter, vertical + diameter,
        ], start=-90, end=-90 + 360 * 0.95, fill=color, width=line_width)

    def _paint_linear_progress(self, drawing, item, horizontal, vertical,
                               scale, color, global_values):
        width = self._number(item, "style_size", 150.0, global_values) * scale
        height = self._number(item, "style_height", 6.0, global_values) * scale
        height = max(2, int(height))
        drawing.rectangle([
            horizontal, vertical, horizontal + width, vertical + height,
        ], fill=(255, 255, 255, 40))
        drawing.rectangle([
            horizontal, vertical, horizontal + width * 0.95, vertical + height,
        ], fill=color)
