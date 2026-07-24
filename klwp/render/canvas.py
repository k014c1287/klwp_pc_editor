"""Render the document into Pillow and present it on the Tk canvas."""

from ..shared import *  # noqa: F401,F403
from ..preview.zoom import PreviewZoom
from ..resize import ResizeHandleSet


class CanvasRendererMixin:
    def _render(self):
        canvas = self.memory['canvas']
        canvas.delete("all")
        pixel_width, pixel_height = self._configure_canvas(canvas)
        if not HAS_PIL:
            self._paint_missing_pillow(canvas)
            return
        image = self.render_to_image(pixel_width, pixel_height)
        self.memory["_quality_preview"] = image
        preview = self._preview_crop(image)
        self.memory['_photo'] = ImageTk.PhotoImage(preview.convert("RGB"))
        canvas.create_image(0, 0, image=self.memory['_photo'], anchor="nw")
        self._paint_selection(canvas)

    def _configure_canvas(self, canvas):
        document_width, document_height = self._doc_size()
        memory = self.memory
        zoom = PreviewZoom(memory.optional("preview_zoom", 1.0))
        scale = zoom.scale(
            (document_width, document_height),
            (self.CANVAS_W, self.CANVAS_H))
        memory['_scale'] = scale
        memory['_doc'] = (document_width, document_height)
        pixel_width = int(document_width * scale)
        pixel_height = int(document_height * scale)
        viewport_width = min(self.CANVAS_W, pixel_width)
        viewport_height = min(self.CANVAS_H, pixel_height)
        memory["_viewport_size"] = (viewport_width, viewport_height)
        self._clamp_view_origin(
            pixel_width, pixel_height, viewport_width, viewport_height)
        canvas.config(width=viewport_width, height=viewport_height)
        return pixel_width, pixel_height

    def _clamp_view_origin(self, width, height, viewport_width, viewport_height):
        memory = self.memory
        horizontal, vertical = memory.optional(
            "_view_origin", (0.0, 0.0))
        maximum_horizontal = max(0, width - viewport_width)
        maximum_vertical = max(0, height - viewport_height)
        horizontal = max(0, min(maximum_horizontal, round(horizontal)))
        vertical = max(0, min(maximum_vertical, round(vertical)))
        memory["_view_origin"] = (horizontal, vertical)

    def _preview_crop(self, image):
        horizontal, vertical = self.memory["_view_origin"]
        width, height = self.memory["_viewport_size"]
        left, top = int(horizontal), int(vertical)
        return image.crop((left, top, left + width, top + height))

    def _paint_missing_pillow(self, canvas):
        canvas.create_text(
            self.CANVAS_W // 2, 40,
            text="Pillow 未導入のためプレビュー不可\npip install pillow",
            fill="#fff")

    def _paint_selection(self, canvas):
        selected = self.memory['selected']
        if selected is None:
            return
        bounds = self._bounds(selected)
        if bounds is None:
            return
        horizontal, vertical, width, height = bounds
        scale = self.memory['_scale']
        origin_horizontal, origin_vertical = self.memory["_view_origin"]
        canvas.create_rectangle(
            horizontal * scale - origin_horizontal,
            vertical * scale - origin_vertical,
            (horizontal + width) * scale - origin_horizontal,
            (vertical + height) * scale - origin_vertical,
            outline="#00E5FF", width=2, dash=(4, 3))
        origin = (origin_horizontal, origin_vertical)
        self._paint_resize_handles(canvas, selected, bounds, scale, origin)

    @staticmethod
    def _paint_resize_handles(canvas, item, bounds, scale, origin):
        if not ResizeHandleSet.supports(item):
            return
        origin_horizontal, origin_vertical = origin
        radius = 4
        for _name, horizontal, vertical in ResizeHandleSet.positions(bounds):
            pixel_horizontal = horizontal * scale - origin_horizontal
            pixel_vertical = vertical * scale - origin_vertical
            canvas.create_rectangle(
                pixel_horizontal - radius, pixel_vertical - radius,
                pixel_horizontal + radius, pixel_vertical + radius,
                fill="#FFFFFF", outline="#00A8C8", width=1)

    def render_to_image(self, pixel_width, pixel_height):
        """Render the current preset without requiring a Tk window."""
        document_width, document_height = self._doc_size()
        scale = min(
            pixel_width / document_width,
            pixel_height / document_height)
        self.memory['_scale'] = scale
        self.memory['_doc'] = (document_width, document_height)
        self.memory['_event_regions'] = []
        self.memory['_item_bounds'] = []
        width, height = int(pixel_width), int(pixel_height)
        image = Image.new("RGBA", (width, height), (16, 16, 24, 255))
        archive = self.memory['archive']
        root_module = archive.root_module()
        global_values = self._root_globals()
        self._paint_background(
            image, root_module, global_values, width, height)
        for item in archive.modules():
            self._paint_item(image, item, None, global_values)
        return image

    def _paint_background(self, image, root_module, global_values,
                          width, height):
        background_type = self._value(
            root_module, "background_type", "SOLID", global_values)
        if background_type == "IMAGE" and self._paint_background_image(
                image, root_module, global_values, width, height):
            return
        color = self._value(
            root_module, "background_color", "#FF202030", global_values)
        image.paste(Image.new("RGBA", (width, height), self._rgba(color)), (0, 0))

    def _paint_background_image(self, image, root_module, global_values,
                                width, height):
        reference = self._value(
            root_module, "background_bitmap", "", global_values)
        source = self._bitmap_image(reference)
        if source is None:
            return False
        image.paste(self._cover_fit(source, width, height), (0, 0))
        return True

    def _rgba(self, color, default=(255, 255, 255, 255)):
        if not isinstance(color, str) or not color.startswith("#"):
            return default
        hexadecimal = color[1:]
        try:
            return self._hexadecimal_rgba(hexadecimal, default)
        except ValueError:
            return default

    @staticmethod
    def _hexadecimal_rgba(hexadecimal, default):
        if len(hexadecimal) == 8:
            return (
                int(hexadecimal[2:4], 16), int(hexadecimal[4:6], 16),
                int(hexadecimal[6:8], 16), int(hexadecimal[0:2], 16),
            )
        if len(hexadecimal) == 6:
            return (
                int(hexadecimal[0:2], 16), int(hexadecimal[2:4], 16),
                int(hexadecimal[4:6], 16), 255,
            )
        return default

    def _bitmap_image(self, reference):
        if not isinstance(reference, str) or not reference:
            return None
        name = "bitmaps/" + reference.split("/")[-1]
        data = self.memory['archive']['bitmaps'].get(name)
        if not data:
            return None
        key = ("src", name)
        if key not in self.memory['photo_cache']:
            self.memory['photo_cache'][key] = self._decode_bitmap(data)
        return self.memory['photo_cache'][key]

    @staticmethod
    def _decode_bitmap(data):
        try:
            stream = io.BytesIO(data)
            return Image.open(stream).convert("RGBA")
        except Exception:
            return None

    @staticmethod
    def _cover_fit(source, width, height):
        source_width, source_height = source.size
        ratio = max(width / source_width, height / source_height)
        resized_width = max(1, int(source_width * ratio))
        resized_height = max(1, int(source_height * ratio))
        image = source.resize((resized_width, resized_height))
        horizontal = (image.width - width) // 2
        vertical = (image.height - height) // 2
        return image.crop((
            horizontal, vertical, horizontal + width, vertical + height))

    def _font(self, family, pixels):
        pixels = max(6, int(pixels))
        key = (family, pixels)
        cached = self.memory['font_cache'].get(key)
        if cached is not None:
            return cached
        font = self._archive_font(family, pixels)
        if font is None:
            font = self._system_font(pixels)
        if font is None:
            font = ImageFont.load_default()
        self.memory['font_cache'][key] = font
        return font

    def _archive_font(self, family, pixels):
        base_name = (family or "").split("/")[-1].lower()
        archive = self.memory['archive']
        candidates = map(
            lambda entry: self._load_archive_font(
                entry, base_name, pixels),
            archive["fonts"].items())
        return next(filter(None, candidates), None)

    @staticmethod
    def _load_archive_font(entry, base_name, pixels):
        name, data = entry
        if len(data) <= 1000 or not base_name or base_name not in name.lower():
            return None
        try:
            return ImageFont.truetype(io.BytesIO(data), pixels)
        except Exception:
            return None

    def _system_font(self, pixels):
        names = (
            "meiryo.ttc", "YuGothM.ttc", "msgothic.ttc",
            "NotoSansCJK-Regular.ttc", "DejaVuSans.ttf",
        )
        candidates = map(lambda name: self._load_system_font(name, pixels), names)
        return next(filter(None, candidates), None)

    @staticmethod
    def _load_system_font(name, pixels):
        try:
            return ImageFont.truetype(name, pixels)
        except Exception:
            return None
