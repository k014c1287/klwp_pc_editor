"""Pan a zoomed preview by dragging its unoccupied background."""

from ..preview.zoom import PreviewPan, PreviewZoom


class PreviewPanMixin:
    def _start_preview_pan(self, event):
        zoom = self._current_preview_zoom()
        if zoom.number() <= PreviewZoom.MINIMUM:
            return False
        self._cancel_zoom_quality_render()
        memory = self.memory
        pointer = event.x, event.y
        origin = memory.optional("_view_origin", (0.0, 0.0))
        memory["_view_pan_state"] = PreviewPan(pointer, origin)
        memory["canvas"].configure(cursor="fleur")
        return True

    def _drag_preview_pan(self, event):
        memory = self.memory
        state = memory.optional("_view_pan_state")
        if state is None:
            return False
        pointer = event.x, event.y
        memory["_view_origin"] = state.moved_origin(pointer)
        self._render_zoom_preview()
        origin = memory["_view_origin"]
        memory["_view_pan_state"] = PreviewPan(pointer, origin)
        return True

    def _finish_preview_pan(self):
        memory = self.memory
        state = memory.optional("_view_pan_state")
        if state is None:
            return False
        memory["_view_pan_state"] = None
        memory["canvas"].configure(cursor="")
        if not self._quality_preview_is_current():
            self._schedule_zoom_quality_render()
        return True
