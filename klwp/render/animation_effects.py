"""Apply whole-item animation transforms after its layer is rendered."""

from ..shared import *  # noqa: F401,F403


class AnimationEffectMixin:
    def _paint_root_effect(self, request, placement):
        animation = request["root_animation"]
        if not self._needs_root_effect(request, animation):
            return False
        target = request["image"]
        layer = Image.new("RGBA", target.size, (0, 0, 0, 0))
        self._paint_item(
            layer, request["item"], request["parent_box"],
            request["global_values"], request["preplaced"],
            _root_animation=animation, _opacity_pass=True)
        layer = self._transform_animation_layer(layer, placement, animation)
        target.alpha_composite(layer)
        return True

    @staticmethod
    def _needs_root_effect(request, animation):
        if not request["is_root"] or request["opacity_pass"]:
            return False
        return (
            animation["alpha"] < 0.999
            or abs(animation["rotation"]) > 0.001
            or abs(animation["scale"] - 1.0) > 0.001
            or bool(animation["color_filter"])
        )

    def _transform_animation_layer(self, layer, placement, animation):
        center = self._rotation_center(placement)
        transformed = self._scaled_layer(layer, center, animation["scale"])
        transformed = self._rotated_layer(
            transformed, center, animation["rotation"])
        transformed = self._filtered_layer(transformed, animation)
        self._apply_opacity(transformed, animation["alpha"])
        return transformed

    @staticmethod
    def _scaled_layer(layer, center, scale):
        if abs(scale - 1.0) <= 0.001:
            return layer
        inverse = 1.0 / max(0.01, scale)
        horizontal, vertical = center
        matrix = (
            inverse, 0.0, horizontal * (1.0 - inverse),
            0.0, inverse, vertical * (1.0 - inverse),
        )
        return layer.transform(
            layer.size, Image.AFFINE, matrix,
            resample=Resampling.BICUBIC)

    @staticmethod
    def _rotated_layer(layer, center, angle):
        if abs(angle) <= 0.001:
            return layer
        return layer.rotate(
            -angle, resample=Resampling.BICUBIC,
            center=center, expand=False)

    def _filtered_layer(self, layer, animation):
        name = animation["color_filter"]
        amount = animation["filter_amount"]
        if not name or amount <= 0.0:
            return layer
        filtered = self._filter_image(layer, name, amount)
        return Image.blend(layer, filtered, amount)

    @staticmethod
    def _filter_image(layer, name, amount):
        if "INVERT" in name:
            return AnimationEffectMixin._inverted_image(layer)
        if "SEPIA" in name:
            return AnimationEffectMixin._sepia_image(layer)
        if "BRIGHT" in name:
            return ImageEnhance.Brightness(layer).enhance(1.0 + amount)
        if "SATURATE" in name:
            return ImageEnhance.Color(layer).enhance(1.0 + amount * 2.0)
        return layer

    @staticmethod
    def _inverted_image(layer):
        alpha = layer.getchannel("A")
        inverted = ImageChops.invert(layer.convert("RGB"))
        inverted.putalpha(alpha)
        return inverted

    @staticmethod
    def _sepia_image(layer):
        alpha = layer.getchannel("A")
        grayscale = layer.convert("RGB")
        grayscale = grayscale.convert("L")
        sepia = ImageOps.colorize(grayscale, "#2B1B0E", "#F4D7A1")
        sepia.putalpha(alpha)
        return sepia

    @staticmethod
    def _apply_opacity(image, opacity):
        alpha_channel = image.getchannel("A")
        table = [int(value * opacity) for value in range(256)]
        image.putalpha(alpha_channel.point(table))
