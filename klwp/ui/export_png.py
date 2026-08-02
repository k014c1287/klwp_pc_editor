"""Export the current preview state as a full-resolution PNG image."""

from ..shared import *  # noqa: F401,F403


class PngExportMixin:
    def cmd_export_png(self):
        if not HAS_PIL:
            messagebox.showerror(
                APP_TITLE, "PNG書き出しにはPillowが必要です。")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG image", "*.png")])
        if not path:
            return
        self._export_png(path)

    def _export_png(self, path):
        try:
            self._write_png(path)
        except Exception as error:
            messagebox.showerror(
                APP_TITLE, f"PNG書き出しに失敗しました:\n{error}")

    def _write_png(self, path):
        width, height = self.memory["device_res"]
        image = self.render_to_image(int(width), int(height))
        image.save(path, format="PNG")
        name = basename(path)
        self._set_status(f"PNGを書き出しました: {name}")
