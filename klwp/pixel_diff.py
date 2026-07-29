"""Measure and visualize differences between KLWP preview images."""

from pathlib import Path

from .archive import KlwpArchive
from .memory import ApplicationMemory
from .runtime import (
    ImageChops, ImageOps, ImageStat, json, math)


class ComparisonRegion:
    """Crop system UI or other excluded margins from both images."""

    def __init__(self, left=0, top=0, right=0, bottom=0):
        self._margins = tuple(map(int, (left, top, right, bottom)))

    def apply(self, image):
        left, top, right, bottom = self._margins
        width, height = image.size
        box = left, top, width - right, height - bottom
        if box[0] >= box[2] or box[1] >= box[3]:
            raise ValueError("comparison margins remove the complete image")
        return image.crop(box)


class PixelDiffMetrics:
    """Wrap numeric comparison results for JSON and console output."""

    def __init__(self, mean_squared_error, similarity, dimensions):
        self._values = {
            "width": dimensions[0],
            "height": dimensions[1],
            "mse": round(float(mean_squared_error), 6),
            "psnr": self._peak_signal_ratio(mean_squared_error),
            "ssim": round(float(similarity), 6),
        }

    def as_mapping(self):
        return dict(self._values)

    @staticmethod
    def _peak_signal_ratio(mean_squared_error):
        if mean_squared_error <= 0.0:
            return None
        ratio = 255.0 * 255.0 / mean_squared_error
        return round(10.0 * math.log10(ratio), 6)


class PixelDiffThresholds:
    """Evaluate optional quality gates against measured metrics."""

    def __init__(self, maximum_error=None, minimum_similarity=None):
        self._limits = {
            "maximum_error": maximum_error,
            "minimum_similarity": minimum_similarity,
        }

    def failures(self, metrics):
        failures = []
        maximum_error = self._limits["maximum_error"]
        minimum_similarity = self._limits["minimum_similarity"]
        if maximum_error is not None and metrics["mse"] > maximum_error:
            failures.append(
                f"MSE {metrics['mse']} exceeds maximum {maximum_error}")
        if minimum_similarity is not None \
                and metrics["ssim"] < minimum_similarity:
            failures.append(
                f"SSIM {metrics['ssim']} is below minimum {minimum_similarity}")
        return tuple(failures)


class ComparableImages:
    """Own two normalized images and their comparison operations."""

    def __init__(self, reference, actual):
        reference_image = reference.convert("RGB")
        actual_image = actual.convert("RGB")
        if reference_image.size != actual_image.size:
            raise ValueError("reference and actual image sizes must match")
        self._reference = reference_image
        self._actual = actual_image

    def cropped(self, region):
        reference = self._reference
        actual = self._actual
        return ComparableImages(region.apply(reference), region.apply(actual))

    def mean_squared_error(self):
        difference = self._difference()
        histogram = difference.histogram()
        squared_total = sum(
            (index % 256) ** 2 * count
            for index, count in enumerate(histogram))
        width, height = difference.size
        channel_count = len(difference.getbands())
        return squared_total / max(1, width * height * channel_count)

    def structural_similarity(self):
        reference, actual = self._grayscale_pair()
        reference_stat = ImageStat.Stat(reference)
        actual_stat = ImageStat.Stat(actual)
        reference_mean = reference_stat.mean[0]
        actual_mean = actual_stat.mean[0]
        reference_variance = reference_stat.var[0]
        actual_variance = actual_stat.var[0]
        reference_data = reference.getdata()
        actual_data = actual.getdata()
        width, height = reference.size
        product_total = sum(
            reference_value * actual_value
            for reference_value, actual_value
            in zip(reference_data, actual_data))
        product_mean = product_total / max(1, width * height)
        covariance = product_mean - reference_mean * actual_mean
        return self._ssim(
            reference_mean, actual_mean, reference_variance,
            actual_variance, covariance)

    def dimensions(self):
        reference = self._reference
        return reference.size

    def heatmap(self, gain=4.0):
        difference = self._difference()
        grayscale = ImageOps.grayscale(difference)
        amplified = grayscale.point(
            lambda value: min(255, round(value * float(gain))))
        return ImageOps.colorize(
            amplified, black=(0, 0, 24), white=(255, 48, 0))

    def write_images(self, directory):
        reference = self._reference
        actual = self._actual
        reference.save(directory / "reference.png")
        actual.save(directory / "actual.png")

    def _difference(self):
        reference = self._reference
        actual = self._actual
        return ImageChops.difference(reference, actual)

    def _grayscale_pair(self):
        reference = self._reference
        actual = self._actual
        return ImageOps.grayscale(reference), ImageOps.grayscale(actual)

    @staticmethod
    def _ssim(reference_mean, actual_mean, reference_variance,
              actual_variance, covariance):
        luminance_constant = (0.01 * 255.0) ** 2
        structure_constant = (0.03 * 255.0) ** 2
        numerator = (
            (2.0 * reference_mean * actual_mean + luminance_constant)
            * (2.0 * covariance + structure_constant))
        denominator = (
            (reference_mean ** 2 + actual_mean ** 2 + luminance_constant)
            * (reference_variance + actual_variance + structure_constant))
        if denominator == 0.0:
            return 1.0
        return max(-1.0, min(1.0, numerator / denominator))


class PixelDiff:
    """Produce metrics and report artifacts from comparable images."""

    def __init__(self, images):
        self._images = images

    def measure(self):
        images = self._images
        error = images.mean_squared_error()
        similarity = images.structural_similarity()
        dimensions = images.dimensions()
        return PixelDiffMetrics(error, similarity, dimensions).as_mapping()

    def write_report(self, directory, heat_gain=4.0):
        output_directory = Path(directory)
        output_directory.mkdir(parents=True, exist_ok=True)
        images = self._images
        images.write_images(output_directory)
        heatmap = images.heatmap(heat_gain)
        heatmap.save(output_directory / "heatmap.png")
        metrics = self.measure()
        serialized = json.dumps(metrics, ensure_ascii=False, indent=2)
        metrics_path = output_directory / "metrics.json"
        metrics_path.write_text(serialized + "\n", encoding="utf-8")
        return metrics


class PresetPreview:
    """Render a KLWP archive without creating a Tk window."""

    def __init__(self, archive, timestamp=None):
        self._archive = archive
        self._timestamp = timestamp

    @classmethod
    def load(cls, path, timestamp=None):
        archive = KlwpArchive()
        archive.load(path)
        return cls(archive, timestamp)

    def render(self, dimensions):
        renderer = self._renderer(dimensions)
        width, height = dimensions
        return renderer.render_to_image(width, height)

    def _renderer(self, dimensions):
        from .editor import EditorApp

        renderer = object.__new__(EditorApp)
        memory = ApplicationMemory()
        memory["archive"] = self._archive
        memory["photo_cache"] = {}
        memory["font_cache"] = {}
        memory["device_res"] = dimensions
        timestamp = self._timestamp
        if timestamp is not None:
            memory["preview_ts"] = timestamp
        renderer.memory = memory
        return renderer
