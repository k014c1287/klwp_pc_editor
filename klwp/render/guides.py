"""Draw ruler ticks and transient alignment guides over the preview."""

from ..shared import *  # noqa: F401,F403


class CanvasGuideMixin:
    def _guides_enabled(self):
        memory = self.memory
        variable = memory.optional("snap_enabled")
        if variable is None:
            return False
        return bool(variable.get())

    def _on_snap_guides_changed(self):
        if not self._guides_enabled():
            self.memory["snap_guides"] = ()
        self._render()

    def _paint_canvas_guides(self, canvas):
        if not self._guides_enabled():
            return
        scale = self.memory["_scale"]
        document_width, document_height = self.memory["_doc"]
        self._paint_ruler_background(
            canvas, document_width * scale, document_height * scale)
        self._paint_horizontal_ruler(canvas, document_width, scale)
        self._paint_vertical_ruler(canvas, document_height, scale)
        memory = self.memory
        for orientation, value in memory.optional("snap_guides", ()):
            self._paint_snap_guide(
                canvas, orientation, value, document_width,
                document_height, scale)

    @staticmethod
    def _paint_ruler_background(canvas, pixel_width, pixel_height):
        canvas.create_rectangle(
            0, 0, pixel_width, 18, fill="#202634", outline="")
        canvas.create_rectangle(
            0, 0, 22, pixel_height, fill="#202634", outline="")

    @staticmethod
    def _paint_horizontal_ruler(canvas, document_width, scale):
        maximum = int(document_width // 100) * 100
        for value in range(0, maximum + 1, 100):
            horizontal = value * scale
            canvas.create_line(
                horizontal, 0, horizontal, 7, fill="#B8C0D4")
            canvas.create_text(
                horizontal + 2, 9, text=str(value), anchor="nw",
                fill="#B8C0D4", font=("", 7))

    @staticmethod
    def _paint_vertical_ruler(canvas, document_height, scale):
        maximum = int(document_height // 100) * 100
        for value in range(0, maximum + 1, 100):
            vertical = value * scale
            canvas.create_line(0, vertical, 7, vertical, fill="#B8C0D4")
            canvas.create_text(
                9, vertical + 2, text=str(value), anchor="nw",
                angle=90, fill="#B8C0D4", font=("", 7))

    @staticmethod
    def _paint_snap_guide(
            canvas, orientation, value, document_width,
            document_height, scale):
        if orientation == "vertical":
            horizontal = value * scale
            canvas.create_line(
                horizontal, 0, horizontal, document_height * scale,
                fill="#FF4FD8", width=1, dash=(3, 2))
            return
        vertical = value * scale
        canvas.create_line(
            0, vertical, document_width * scale, vertical,
            fill="#FF4FD8", width=1, dash=(3, 2))
