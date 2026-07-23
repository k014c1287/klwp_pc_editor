"""Present a responsive zoom from the last high-quality render."""

from ..shared import *  # noqa: F401,F403
from ..preview.zoom import CachedPreviewImage


class ZoomPreviewRendererMixin:
    def _render_zoom_preview(self):
        memory = self.memory
        source = memory.optional("_quality_preview")
        if source is None:
            self._render()
            return
        canvas = memory["canvas"]
        canvas.delete("all")
        target_size = self._configure_canvas(canvas)
        viewport_size = memory["_viewport_size"]
        origin = memory["_view_origin"]
        preview = CachedPreviewImage(source).viewport(
            target_size, viewport_size, origin)
        self._present_zoom_preview(canvas, preview)

    def _present_zoom_preview(self, canvas, preview):
        converted = preview.convert("RGB")
        photo = ImageTk.PhotoImage(converted)
        self.memory["_photo"] = photo
        canvas.create_image(0, 0, image=photo, anchor="nw")
        self._paint_selection(canvas)

    def _quality_preview_is_current(self):
        memory = self.memory
        source = memory.optional("_quality_preview")
        if source is None:
            return False
        document_width, document_height = memory["_doc"]
        scale = memory["_scale"]
        target_size = (
            int(document_width * scale), int(document_height * scale))
        return source.size == target_size
