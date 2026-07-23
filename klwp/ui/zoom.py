"""Preview-only zoom controls and canvas/document coordinate conversion."""

from ..preview.zoom import PreviewZoom


class PreviewZoomMixin:
    def cmd_zoom_in(self):
        zoom = self._current_preview_zoom()
        self._apply_preview_zoom(zoom.increased())

    def cmd_zoom_out(self):
        zoom = self._current_preview_zoom()
        self._apply_preview_zoom(zoom.decreased())

    def cmd_zoom_reset(self):
        self.memory["preview_zoom"] = PreviewZoom.MINIMUM
        self.memory["_view_origin"] = (0.0, 0.0)
        self._update_preview_zoom_label()
        self._render()

    def cmd_zoom_selected(self):
        memory = self.memory
        selected = memory.optional("selected")
        if selected is None:
            self._set_status("先に拡大する要素を選択してください")
            return
        bounds = self._bounds(selected)
        if bounds is None:
            self._set_status("選択要素の表示範囲を取得できません")
            return
        zoom = PreviewZoom.for_selection(
            bounds, self._doc_size(), (self.CANVAS_W, self.CANVAS_H))
        self._apply_preview_zoom(zoom)

    def _on_preview_zoom_wheel(self, event):
        current = self._current_preview_zoom()
        target = self._wheel_zoom(current, event)
        if target.number() == current.number():
            return "break"
        document_point = self._document_point(event)
        memory = self.memory
        memory["preview_zoom"] = target.number()
        memory["_view_origin"] = self._pointer_focused_origin(
            document_point, event, target)
        self._update_preview_zoom_label()
        self._render()
        return "break"

    @staticmethod
    def _wheel_zoom(current, event):
        delta = float(getattr(event, "delta", 0.0))
        if delta > 0:
            return current.increased()
        if delta < 0:
            return current.decreased()
        button = int(getattr(event, "num", 0))
        if button == 4:
            return current.increased()
        if button == 5:
            return current.decreased()
        return current

    def _pointer_focused_origin(self, document_point, event, zoom):
        document_size = self._doc_size()
        viewport_size = (self.CANVAS_W, self.CANVAS_H)
        scale = zoom.scale(document_size, viewport_size)
        horizontal, vertical = document_point
        return horizontal * scale - event.x, vertical * scale - event.y

    def _apply_preview_zoom(self, zoom):
        self.memory["preview_zoom"] = zoom.number()
        self._focus_preview_on_selected()
        self._update_preview_zoom_label()
        self._render()

    def _current_preview_zoom(self):
        memory = self.memory
        value = memory.optional("preview_zoom", 1.0)
        return PreviewZoom(value)

    def _focus_preview_on_selected(self):
        memory = self.memory
        selected = memory.optional("selected")
        if selected is None:
            self._focus_preview_on_document()
            return
        bounds = self._bounds(selected)
        if bounds is None:
            self._focus_preview_on_document()
            return
        self.memory["_view_origin"] = self._focused_origin(bounds)

    def _focus_preview_on_document(self):
        document_width, document_height = self._doc_size()
        bounds = (0.0, 0.0, document_width, document_height)
        self.memory["_view_origin"] = self._focused_origin(bounds)

    def _focused_origin(self, bounds):
        zoom = self._current_preview_zoom()
        document_size = self._doc_size()
        viewport_size = (self.CANVAS_W, self.CANVAS_H)
        scale = zoom.scale(document_size, viewport_size)
        left, top, width, height = bounds
        horizontal = (left + width / 2.0) * scale - self.CANVAS_W / 2.0
        vertical = (top + height / 2.0) * scale - self.CANVAS_H / 2.0
        return horizontal, vertical

    def _document_point(self, event):
        memory = self.memory
        scale = memory["_scale"]
        origin_horizontal, origin_vertical = memory.optional(
            "_view_origin", (0.0, 0.0))
        horizontal = (event.x + origin_horizontal) / scale
        vertical = (event.y + origin_vertical) / scale
        return horizontal, vertical

    def _update_preview_zoom_label(self):
        memory = self.memory
        label = memory.optional("preview_zoom_label")
        if label is None:
            return
        zoom = self._current_preview_zoom()
        percentage = zoom.percentage()
        label.configure(text=f"{percentage}%")

    def _reset_preview_zoom(self):
        self.memory["preview_zoom"] = PreviewZoom.MINIMUM
        self.memory["_view_origin"] = (0.0, 0.0)
        self._update_preview_zoom_label()
