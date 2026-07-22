"""Apply KLWP paint filters while compositing a rendered leaf."""

from ..shared import *  # noqa: F401,F403


class BlendRendererMixin:
    def _paint_blended_leaf(self, request, placement):
        item = request["item"]
        mode = str(self._value(
            item, "paint_mode", "NORMAL", request["global_values"])).upper()
        if mode in ("", "NORMAL", "SRC_OVER"):
            return False
        target = request["image"]
        source = Image.new("RGBA", target.size, (0, 0, 0, 0))
        request["image"] = source
        self._paint_plain_leaf(request, placement)
        request["image"] = target
        self._blend_leaf(target, source, mode)
        return True

    def _blend_leaf(self, target, source, mode):
        if mode == "CLEAR":
            self._clear_with_source(target, source)
            return
        blended = self._blend_rgb(target, source, mode)
        alpha = source.getchannel("A")
        base = target.convert("RGB")
        combined = Image.composite(blended, base, alpha)
        combined_alpha = ImageChops.lighter(target.getchannel("A"), alpha)
        combined.putalpha(combined_alpha)
        target.paste(combined)

    @staticmethod
    def _clear_with_source(target, source):
        source_alpha = source.getchannel("A")
        inverted = ImageChops.invert(source_alpha)
        target_alpha = target.getchannel("A")
        target.putalpha(ImageChops.multiply(target_alpha, inverted))

    def _blend_rgb(self, target, source, mode):
        base = target.convert("RGB")
        overlay = source.convert("RGB")
        handlers = {
            "MULTIPLY": ImageChops.multiply,
            "SCREEN": ImageChops.screen,
            "ADD": ImageChops.add,
            "DARKEN": ImageChops.darker,
            "LIGHTEN": ImageChops.lighter,
            "XOR": ImageChops.difference,
            "DIFFERENCE": ImageChops.difference,
            "COLORIZE": ImageChops.multiply,
        }
        handler = handlers.get(mode)
        if handler is not None:
            return handler(base, overlay)
        return overlay
