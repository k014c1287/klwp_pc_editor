"""Measure and render KLWP text modules."""

from ..shared import *  # noqa: F401,F403
from .text_layout import TextLayoutResult


class TextRendererMixin:
    @staticmethod
    def _wrap_fixed(text, width, lines):
        flattened = text.replace("\n", "")
        character_count = max(1, len(flattened))
        characters_per_line = max(1, math.ceil(character_count / lines))
        font_size = max(9.0, width / characters_per_line)
        indexes = range(0, character_count, characters_per_line)
        wrapped = "\n".join(
            flattened[index:index + characters_per_line] for index in indexes)
        return wrapped, font_size

    def _text_layout(self, item, globals_=None):
        memory = self.memory
        scale = float(memory.optional("_scale", 1.0) or 1.0)
        text, size, fixed = self._text_content(item, globals_)
        family = self._value(item, "text_family", "", globals_) or ""
        font_source = self._text_font_source(family)
        alignment = self._text_alignment(item, globals_)
        key = ("textlayout", text, size, family, fixed, alignment, round(scale, 4))
        cached = self.memory['photo_cache'].get(key)
        if cached is not None:
            return cached
        result = self._measure_text(
            item, text, size, font_source, alignment, fixed, scale, globals_)
        self.memory['photo_cache'][key] = result
        return result

    def _text_content(self, item, global_values):
        size = self._number(item, "text_size", 20.0, global_values)
        text = self._text_of(item, global_values) or " "
        fixed = self._value(
            item, "text_size_type", "", global_values) == "FIXED_WIDTH"
        if not fixed:
            return text, size, fixed
        lines = self._number(item, "text_lines", 2.0, global_values)
        text, size = self._wrap_fixed(text, size, max(1, int(lines)))
        return text, size, fixed

    @staticmethod
    def _text_font_source(family):
        normalized = str(family).lower()
        icon_markers = ("communitymaterial", "material-font", "icon-font")
        if any(marker in normalized for marker in icon_markers):
            return ""
        return family

    def _text_alignment(self, item, global_values):
        alignment = str(self._value(
            item, "text_align", "LEFT", global_values)).lower()
        if alignment in ("center", "right"):
            return alignment
        return "left"

    def _measure_text(self, item, text, size, font_source, alignment,
                      fixed, scale, global_values):
        font = self._font(font_source, size * scale)
        spacing = self._TEXT_SPACING_U * scale
        drawing = ImageDraw.Draw(Image.new("RGB", (1, 1)))
        bounds = self._text_bounds(drawing, text, font, spacing, alignment)
        font, bounds = self._fallback_empty_font(
            drawing, text, font, bounds, size, spacing, alignment, scale)
        width = max(1.0, (bounds[2] - bounds[0]) / scale)
        height = max(1.0, (bounds[3] - bounds[1]) / scale)
        if fixed:
            width = self._number(item, "text_size", 20.0, global_values)
        return TextLayoutResult(
            text=text, font=font, spacing=spacing, bounds=bounds,
            width=width, height=height, alignment=alignment)

    @staticmethod
    def _text_bounds(drawing, text, font, spacing, alignment):
        try:
            return drawing.multiline_textbbox(
                (0, 0), text, font=font, spacing=spacing, align=alignment)
        except Exception:
            return drawing.multiline_textbbox((0, 0), text, font=font)

    def _fallback_empty_font(self, drawing, text, font, bounds, size,
                             spacing, alignment, scale):
        if not self._empty_text_bounds(text, bounds):
            return font, bounds
        font = self._font("", size * scale)
        bounds = drawing.multiline_textbbox(
            (0, 0), text, font=font, spacing=spacing, align=alignment)
        return font, bounds

    @staticmethod
    def _empty_text_bounds(text, bounds):
        has_no_width = bounds[2] <= bounds[0]
        has_no_height = bounds[3] <= bounds[1]
        return bool(text.strip()) and (has_no_width or has_no_height)

    def _paint_text(self, _image, drawing, item, horizontal, vertical,
                    _box, scale, globals_=None):
        color = self._rgba(self._value(
            item, "paint_color", "#FFFFFFFF", globals_))
        if color[3] <= 10 or not self._text_of(item, globals_):
            return
        text, font, spacing, bounds, width, _height, alignment = \
            self._text_layout(item, globals_)
        pixel_horizontal = horizontal * scale - bounds[0]
        pixel_vertical = vertical * scale - bounds[1]
        pixel_horizontal = self._aligned_text_horizontal(
            item, globals_, pixel_horizontal, bounds, width, alignment, scale)
        self._draw_text(
            drawing, pixel_horizontal, pixel_vertical, text,
            font, color, spacing, alignment)

    def _aligned_text_horizontal(self, item, global_values, horizontal,
                                 bounds, width, alignment, scale):
        size_type = self._value(
            item, "text_size_type", "", global_values)
        if size_type != "FIXED_WIDTH":
            return horizontal
        ink_width = bounds[2] - bounds[0]
        box_width = width * scale
        if alignment == "center":
            return horizontal + (box_width - ink_width) / 2
        if alignment == "right":
            return horizontal + box_width - ink_width
        return horizontal

    @staticmethod
    def _draw_text(drawing, horizontal, vertical, text, font, color,
                   spacing, alignment):
        try:
            drawing.multiline_text(
                (horizontal, vertical), text, font=font, fill=color,
                spacing=spacing, align=alignment)
        except Exception:
            drawing.multiline_text(
                (horizontal, vertical), text, font=font, fill=color)
