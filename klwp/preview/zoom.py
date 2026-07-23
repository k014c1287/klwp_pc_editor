"""Calculate transient preview magnification without changing KLWP data."""

from ..runtime import Resampling, Transform


class PreviewZoom:
    MINIMUM = 1.0
    MAXIMUM = 4.0
    STEP = 1.5
    SETTLE_MILLISECONDS = 140

    def __init__(self, value=1.0):
        self._value = self._normalized(value)

    def number(self):
        return self._value

    def percentage(self):
        return round(self._value * 100)

    def increased(self):
        return PreviewZoom(self._value * self.STEP)

    def decreased(self):
        return PreviewZoom(self._value / self.STEP)

    def scale(self, document_size, viewport_size):
        document_width, document_height = document_size
        viewport_width, viewport_height = viewport_size
        fitted = min(
            viewport_width / document_width,
            viewport_height / document_height)
        return fitted * self._value

    @classmethod
    def for_selection(cls, bounds, document_size, viewport_size):
        _left, _top, width, height = bounds
        viewport_width, viewport_height = viewport_size
        document_width, document_height = document_size
        fitted = min(
            viewport_width / document_width,
            viewport_height / document_height)
        target = min(
            viewport_width * 0.7 / max(1.0, width),
            viewport_height * 0.7 / max(1.0, height))
        return cls(target / fitted)

    @classmethod
    def _normalized(cls, value):
        numeric = float(value)
        return max(cls.MINIMUM, min(cls.MAXIMUM, numeric))


class CachedPreviewImage:
    """Scale only the visible viewport from the last quality render."""

    def __init__(self, image):
        self._image = image

    def viewport(self, target_size, viewport_size, origin):
        image = self._image
        source_width, source_height = image.size
        target_width, target_height = target_size
        horizontal_ratio = source_width / max(1, target_width)
        vertical_ratio = source_height / max(1, target_height)
        horizontal, vertical = origin
        coefficients = (
            horizontal_ratio, 0.0, horizontal * horizontal_ratio,
            0.0, vertical_ratio, vertical * vertical_ratio)
        return image.transform(
            viewport_size, Transform.AFFINE, coefficients,
            resample=Resampling.BILINEAR)
