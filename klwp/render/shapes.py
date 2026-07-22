"""Render KLWP shape geometry, masks, paths and shadows."""

from ..shared import *  # noqa: F401,F403
from .gradient import GradientRendererMixin


class ShapeGeometryMixin:
    def _shape_geometry_mask(self, item, width, height, scale, globals_=None,
                             stroke_width=None):
        mask = Image.new("L", (max(1, width), max(1, height)), 0)
        shape_type = str(self._value(
            item, "shape_type", "RECT", globals_)).upper()
        if shape_type == "PATH":
            return self._path_geometry_mask(
                mask, item, width, height, stroke_width)
        drawing = ImageDraw.Draw(mask)
        points = self._polygon_points(shape_type, width, height)
        if points is not None:
            self._draw_polygon(drawing, points, stroke_width)
            return mask
        box = [0, 0, max(0, width - 1), max(0, height - 1)]
        handlers = {
            "SLICE": self._draw_slice,
            "ARC": self._draw_arc,
            "CIRCLE": self._draw_ellipse,
            "OVAL": self._draw_ellipse,
        }
        handler = handlers.get(shape_type, self._draw_rectangle)
        handler(
            drawing, box, item, width, height, scale,
            globals_, stroke_width, shape_type)
        return mask

    def _path_geometry_mask(self, mask, item, width, height, stroke_width):
        if stroke_width is None:
            return self._path_mask(item, width, height) or mask
        drawing = ImageDraw.Draw(mask)
        subpaths = self._path_outline(item, 0, 0, width, height)
        for subpath in subpaths:
            self._draw_path_subpath(drawing, subpath, stroke_width)
        return mask

    @staticmethod
    def _draw_path_subpath(drawing, subpath, stroke_width):
        if len(subpath) > 1:
            drawing.line(
                subpath, fill=255, width=stroke_width, joint="curve")

    @staticmethod
    def _polygon_points(shape_type, width, height):
        points = {
            "TRIANGLE": [(0, 0), (0, height - 1), (width - 1, height / 2)],
            "RTRIANGLE": [(0, 0), (0, height - 1), (width - 1, height - 1)],
            "RT_TRIANGLE": [(0, 0), (0, height - 1), (width - 1, height - 1)],
            "EXAGON": [
                (width * 0.25, 0), (width * 0.75, 0),
                (width - 1, height * 0.5), (width * 0.75, height - 1),
                (width * 0.25, height - 1), (0, height * 0.5),
            ],
            "HEXAGON": [
                (width * 0.25, 0), (width * 0.75, 0),
                (width - 1, height * 0.5), (width * 0.75, height - 1),
                (width * 0.25, height - 1), (0, height * 0.5),
            ],
        }
        return points.get(shape_type)

    @staticmethod
    def _draw_polygon(drawing, points, stroke_width):
        if stroke_width is None:
            drawing.polygon(points, fill=255)
            return
        drawing.line(
            points + [points[0]], fill=255,
            width=stroke_width, joint="curve")

    def _draw_slice(self, drawing, box, item, _width, _height, _scale,
                    global_values, stroke_width, _shape_type):
        sweep = self._number(item, "shape_offset", 90.0, global_values)
        if stroke_width is None:
            drawing.pieslice(box, start=-90, end=-90 + sweep, fill=255)
            return
        drawing.pieslice(
            box, start=-90, end=-90 + sweep,
            outline=255, width=stroke_width)

    def _draw_arc(self, drawing, box, item, _width, _height, scale,
                  global_values, stroke_width, _shape_type):
        sweep = self._number(item, "shape_offset", 90.0, global_values)
        width = stroke_width
        if width is None:
            width = self._number(item, "paint_stroke", 12.0, global_values)
            width = max(1, int(width * scale))
        drawing.arc(
            box, start=-90, end=-90 + sweep, fill=255, width=width)

    @staticmethod
    def _draw_ellipse(drawing, box, _item, _width, _height, _scale,
                      _global_values, stroke_width, _shape_type):
        if stroke_width is None:
            drawing.ellipse(box, fill=255)
            return
        drawing.ellipse(box, outline=255, width=stroke_width)

    def _draw_rectangle(self, drawing, box, item, width, height, scale,
                        global_values, stroke_width, shape_type):
        corners = self._number(item, "shape_corners", 0.0, global_values)
        corners = int(corners * scale)
        if shape_type == "SQUIRCLE" and not corners:
            corners = int(min(width, height) * 0.25)
        radius = min(corners, min(width, height) // 2)
        if stroke_width is None:
            drawing.rounded_rectangle(box, radius=radius, fill=255)
            return
        drawing.rounded_rectangle(
            box, radius=radius, outline=255, width=stroke_width)

    def _clip_mask_for(self, size, item, box, globals_=None):
        scale = self.memory['_scale']
        width, height = self._item_size(item, globals_)
        horizontal, vertical = self._place(
            item, box, width, height, globals_=globals_)
        pixel_horizontal = int(horizontal * scale)
        pixel_vertical = int(vertical * scale)
        pixel_width = max(1, int(width * scale))
        pixel_height = max(1, int(height * scale))
        mask = Image.new("L", size, 0)
        geometry = self._shape_geometry_mask(
            item, pixel_width, pixel_height, scale, globals_)
        mask.paste(geometry, (pixel_horizontal, pixel_vertical))
        return mask

class ShapeMaskMixin:
    def _paint_rotated_item(self, image, item, horizontal, vertical,
                            width, height, scale, globals_):
        base_width, base_height = self._base_item_size(item, globals_)
        pixel_width = max(1, int(base_width * scale))
        pixel_height = max(1, int(base_height * scale))
        tile = Image.new("RGBA", (pixel_width, pixel_height), (0, 0, 0, 0))
        drawing = ImageDraw.Draw(tile)
        self._paint_rotated_content(
            tile, drawing, item, pixel_width, pixel_height,
            base_width, base_height, scale, globals_)
        angle = self._item_rotation(item, globals_)
        rotated = tile.rotate(
            -angle, expand=True, resample=Resampling.BICUBIC)
        pixel_horizontal = horizontal + (width - rotated.width) // 2
        pixel_vertical = vertical + (height - rotated.height) // 2
        image.alpha_composite(rotated, (pixel_horizontal, pixel_vertical))

    def _paint_rotated_content(self, tile, drawing, item, pixel_width,
                               pixel_height, base_width, base_height,
                               scale, global_values):
        if item.get("internal_type") == "ShapeModule":
            self._paint_shape(
                tile, drawing, item, 0, 0, pixel_width, pixel_height,
                scale, global_values)
            return
        box = (0.0, 0.0, base_width, base_height)
        self._paint_text(
            tile, drawing, item, 0.0, 0.0, box, scale, global_values)

    def _leaf_mask(self, item, width, height, scale, globals_=None):
        base_width, base_height = self._base_item_size(item, globals_)
        pixel_width = max(1, int(base_width * scale))
        pixel_height = max(1, int(base_height * scale))
        handlers = {
            "ShapeModule": self._shape_leaf_mask,
            "TextModule": self._text_leaf_mask,
            "FontIconModule": self._icon_leaf_mask,
        }
        handler = handlers.get(
            item.get("internal_type", ""), self._rectangle_leaf_mask)
        mask = handler(item, pixel_width, pixel_height, scale, globals_)
        mask = self._rotate_leaf_mask(mask, item, globals_)
        if mask.size != (width, height):
            mask = mask.resize((width, height), Resampling.LANCZOS)
        return mask

    def _shape_leaf_mask(self, item, width, height, scale, global_values):
        style = self._value(item, "paint_style", "", global_values)
        if style != "STROKE":
            return self._shape_geometry_mask(
                item, width, height, scale, global_values)
        stroke = self._shape_stroke(item, global_values)
        line_width = max(1, int(_as_number(stroke, 3.0) * scale))
        return self._shape_geometry_mask(
            item, width, height, scale, global_values,
            stroke_width=line_width)

    def _shape_stroke(self, item, global_values):
        stroke = self._value(item, "paint_stroke", None, global_values)
        if stroke is not None:
            return stroke
        return self._value(
            item, "paint_stroke_width", 3.0, global_values)

    def _text_leaf_mask(self, item, width, height, scale, global_values):
        mask = Image.new("L", (width, height), 0)
        drawing = ImageDraw.Draw(mask)
        text, font, spacing, bounds, box_width, _box_height, alignment = \
            self._text_layout(item, global_values)
        horizontal = -bounds[0]
        vertical = -bounds[1]
        horizontal = self._leaf_text_horizontal(
            item, global_values, horizontal, bounds,
            box_width, alignment, scale)
        drawing.multiline_text(
            (horizontal, vertical), text, font=font, fill=255,
            spacing=spacing, align=alignment)
        return mask

    def _leaf_text_horizontal(self, item, global_values, horizontal, bounds,
                              box_width, alignment, scale):
        size_type = self._value(
            item, "text_size_type", "", global_values)
        if size_type != "FIXED_WIDTH":
            return horizontal
        ink_width = bounds[2] - bounds[0]
        width = box_width * scale
        if alignment == "center":
            return horizontal + (width - ink_width) / 2
        if alignment == "right":
            return horizontal + width - ink_width
        return horizontal

    def _icon_leaf_mask(self, item, width, height, _scale, global_values):
        mask = Image.new("L", (width, height), 0)
        raw_icon = self._resolved_icon(item, global_values)
        _name, paths, viewbox = decode_kustom_icon(raw_icon)
        if paths:
            return self._build_svg_icon_mask(paths, viewbox, width, height)
        drawing = ImageDraw.Draw(mask)
        drawing.ellipse([
            width * 0.12, height * 0.12,
            width * 0.88, height * 0.88,
        ], fill=255)
        return mask

    @staticmethod
    def _rectangle_leaf_mask(_item, width, height, _scale, _global_values):
        mask = Image.new("L", (width, height), 0)
        drawing = ImageDraw.Draw(mask)
        drawing.rectangle([0, 0, width - 1, height - 1], fill=255)
        return mask

    def _rotate_leaf_mask(self, mask, item, global_values):
        angle = self._item_rotation(item, global_values)
        if not angle:
            return mask
        return mask.rotate(
            -angle, expand=True, resample=Resampling.BICUBIC)

    def _paint_outer_shadow(self, image, item, horizontal, vertical,
                            width, height, scale, globals_=None):
        leaf_mask = self._leaf_mask(item, width, height, scale, globals_)
        full_mask = Image.new("L", image.size, 0)
        full_mask.paste(leaf_mask, (horizontal, vertical))
        solid_mask = full_mask.copy()
        blur = self._number(item, "fx_shadow_blur", 10.0, globals_)
        full_mask = full_mask.filter(
            ImageFilter.GaussianBlur(max(0.5, blur * scale / 6)))
        full_mask = ImageChops.subtract(full_mask, solid_mask)
        full_mask = self._shifted_shadow_mask(
            full_mask, image.size, item, scale, globals_)
        color = self._rgba(self._value(
            item, "fx_shadow_color", "#FFFFFFFF", globals_))
        opacity = Image.new("L", image.size, color[3])
        alpha = ImageChops.multiply(full_mask, opacity)
        shadow = Image.new("RGBA", image.size, color[:3] + (0,))
        shadow.putalpha(alpha)
        image.alpha_composite(shadow)

    def _shifted_shadow_mask(self, mask, size, item, scale, global_values):
        distance = self._number(
            item, "fx_shadow_distance", 0.0, global_values) * scale
        if not distance:
            return mask
        direction = self._number(
            item, "fx_shadow_direction", 0.0, global_values)
        radians = math.radians(direction)
        shifted = Image.new("L", size, 0)
        offset = (
            int(math.cos(radians) * distance),
            int(math.sin(radians) * distance),
        )
        shifted.paste(mask, offset)
        return shifted

    @staticmethod
    def _path_viewbox(path):
        subpaths = _svg_subpaths(path or "")
        coordinates = [value for subpath in subpaths for point in subpath for value in point]
        if coordinates and min(coordinates) >= -1 and max(coordinates) <= 101:
            return (0.0, 0.0, 100.0, 100.0)
        return None

    def _path_mask(self, item, width, height):
        path = item.get("shape_path") or ""
        return svg_path_mask(
            path, width, height, viewbox=self._path_viewbox(path))

    def _path_outline(self, item, horizontal, vertical, width, height):
        path = item.get("shape_path") or ""
        subpaths = _svg_subpaths(path)
        viewbox = self._path_viewbox(path) or self._subpath_viewbox(subpaths)
        if viewbox is None:
            return []
        view_horizontal, view_vertical, view_width, view_height = viewbox
        return [[(
            horizontal + (point[0] - view_horizontal) / view_width * width,
            vertical + (point[1] - view_vertical) / view_height * height,
        ) for point in subpath] for subpath in subpaths]

    @staticmethod
    def _subpath_viewbox(subpaths):
        horizontal_values = [point[0] for subpath in subpaths for point in subpath]
        vertical_values = [point[1] for subpath in subpaths for point in subpath]
        if not horizontal_values:
            return None
        horizontal = min(horizontal_values)
        vertical = min(vertical_values)
        width = max(horizontal_values) - horizontal or 1
        height = max(vertical_values) - vertical or 1
        return horizontal, vertical, width, height

class ShapeRendererMixin(ShapeGeometryMixin, ShapeMaskMixin,
                         GradientRendererMixin):
    def _paint_shape(self, image, _drawing, item, horizontal, vertical,
                     width, height, scale, globals_=None):
        color = self._rgba(self._value(
            item, "paint_color", "#80FFFFFF", globals_))
        mask_type = str(self._value(item, "fx_mask", "", globals_))
        if mask_type.startswith("CLIP"):
            return
        style = self._value(item, "paint_style", "", globals_)
        if style == "STROKE":
            self._paint_stroked_shape(
                image, item, horizontal, vertical, width, height,
                scale, color, globals_)
            return
        mask = self._shape_geometry_mask(
            item, width, height, scale, globals_)
        self._paint_shape_fill(
            image, item, horizontal, vertical, width, height,
            scale, color, mask, mask_type, globals_)

    def _paint_shape_fill(self, image, item, horizontal, vertical,
                          width, height, scale, color, mask, mask_type,
                          global_values):
        if mask_type == "BLURRED":
            self._paint_blurred_shape(
                image, item, horizontal, vertical, width, height,
                scale, color, mask, global_values)
            return
        gradient = self._value(item, "fx_gradient", "", global_values)
        if gradient == "BITMAP":
            self._paint_bitmap_shape(
                image, item, horizontal, vertical, width, height,
                mask, global_values)
            return
        if gradient not in ("", "NONE"):
            self._paint_gradient_shape(
                image, item, horizontal, vertical, width, height,
                mask, global_values)
            return
        self._paint_solid_shape(
            image, horizontal, vertical, width, height, color, mask)

    def _paint_gradient_shape(self, image, item, horizontal, vertical,
                              width, height, mask, global_values):
        tile = self._gradient_tile(
            item, width, height, global_values)
        transparent = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        masked = Image.composite(tile, transparent, mask)
        box = [horizontal, vertical, horizontal + width, vertical + height]
        composite = Image.alpha_composite(image.crop(box), masked)
        image.paste(composite, (horizontal, vertical))

    def _paint_stroked_shape(self, image, item, horizontal, vertical,
                             width, height, scale, color, global_values):
        if color[3] <= 10:
            return
        stroke = self._shape_stroke(item, global_values)
        line_width = max(1, int(_as_number(stroke, 3.0) * scale))
        mask = self._shape_geometry_mask(
            item, width, height, scale, global_values,
            stroke_width=line_width)
        self._composite_shape_color(
            image, horizontal, vertical, width, height, color, mask)

    def _paint_blurred_shape(self, image, item, horizontal, vertical,
                             width, height, scale, color, mask, global_values):
        box = [horizontal, vertical, horizontal + width, vertical + height]
        region = image.crop(box).convert("RGB")
        blur = self._number(item, "fx_bitmap_blur", 40.0, global_values)
        region = region.filter(
            ImageFilter.GaussianBlur(max(1, blur * scale / 5)))
        tint = Image.new("RGB", (width, height), color[:3])
        region = Image.blend(region, tint, 0.35)
        image.paste(region, (horizontal, vertical), mask)

    def _paint_bitmap_shape(self, image, item, horizontal, vertical,
                            width, height, mask, global_values):
        reference = self._value(
            item, "fx_gradient_bitmap", "", global_values)
        source = self._bitmap_image(reference) if reference else None
        if source is not None:
            fitted = self._cover_fit(source, width, height)
            image.paste(fitted, (horizontal, vertical), mask)
            return
        placeholder = self._shape_placeholder(width, height)
        image.paste(placeholder, (horizontal, vertical), mask)

    def _shape_placeholder(self, width, height):
        placeholder = Image.new("RGB", (width, height), (44, 46, 72))
        drawing = ImageDraw.Draw(placeholder)
        font = self._font("", height * 0.5)
        drawing.text(
            (width / 2, height / 2), "♪", font=font,
            fill=(180, 186, 230), anchor="mm")
        return placeholder

    def _paint_solid_shape(self, image, horizontal, vertical,
                           width, height, color, mask):
        if color[3] == 0:
            return
        self._composite_shape_color(
            image, horizontal, vertical, width, height, color, mask)

    @staticmethod
    def _composite_shape_color(image, horizontal, vertical,
                               width, height, color, mask):
        box = [horizontal, vertical, horizontal + width, vertical + height]
        layer = Image.new("RGBA", (width, height), color)
        transparent = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        masked = Image.composite(layer, transparent, mask)
        composite = Image.alpha_composite(image.crop(box), masked)
        image.paste(composite, (horizontal, vertical))
