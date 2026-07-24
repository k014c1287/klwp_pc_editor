"""CLI for comparing a PC-rendered preview with an Android screenshot."""

import argparse
from datetime import datetime
from pathlib import Path
import sys

script_path = Path(__file__)
resolved_path = script_path.resolve()
tools_directory = resolved_path.parent
project_root = tools_directory.parent
search_path = sys.path
search_path.insert(0, str(project_root))

from klwp.pixel_diff import (
    ComparableImages, ComparisonRegion, PixelDiff, PixelDiffThresholds,
    PresetPreview)
from klwp.runtime import HAS_PIL, Image, Resampling, json


def argument_parser():
    parser = argparse.ArgumentParser(
        description="Compare a KLWP preview with a reference screenshot")
    parser.add_argument("--reference", required=True, type=Path)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--preset", type=Path)
    source.add_argument("--actual", type=Path)
    parser.add_argument("--timestamp")
    parser.add_argument("--width", type=int)
    parser.add_argument("--ignore-left", type=int, default=0)
    parser.add_argument("--ignore-top", type=int, default=0)
    parser.add_argument("--ignore-right", type=int, default=0)
    parser.add_argument("--ignore-bottom", type=int, default=0)
    parser.add_argument("--heat-gain", type=float, default=4.0)
    parser.add_argument("--max-mse", type=float)
    parser.add_argument("--min-ssim", type=float)
    parser.add_argument(
        "--output", type=Path, default=Path("artifacts/pixel_diff"))
    return parser


def load_image(path):
    return Image.open(path).convert("RGB")


def target_dimensions(reference, requested_width):
    width, height = reference.size
    if requested_width is None:
        return width, height
    ratio = requested_width / width
    return requested_width, max(1, round(height * ratio))


def resized(image, dimensions):
    if image.size == dimensions:
        return image
    return image.resize(dimensions, Resampling.LANCZOS)


def parsed_timestamp(value):
    if value is None:
        return None
    normalized = value.replace("Z", "+00:00")
    date_time = datetime.fromisoformat(normalized)
    return date_time.timestamp() * 1000.0


def actual_image(arguments, dimensions):
    if arguments.preset is not None:
        timestamp = parsed_timestamp(arguments.timestamp)
        preview = PresetPreview.load(arguments.preset, timestamp)
        return preview.render(dimensions)
    image = load_image(arguments.actual)
    return resized(image, dimensions)


def comparison_region(arguments):
    return ComparisonRegion(
        arguments.ignore_left, arguments.ignore_top,
        arguments.ignore_right, arguments.ignore_bottom)


def run(arguments):
    if not HAS_PIL:
        raise RuntimeError("Pillow is required for pixel comparison")
    reference = load_image(arguments.reference)
    dimensions = target_dimensions(reference, arguments.width)
    normalized_reference = resized(reference, dimensions)
    normalized_actual = actual_image(arguments, dimensions)
    images = ComparableImages(normalized_reference, normalized_actual)
    cropped_images = images.cropped(comparison_region(arguments))
    comparison = PixelDiff(cropped_images)
    return comparison.write_report(arguments.output, arguments.heat_gain)


def quality_gate(arguments, metrics):
    thresholds = PixelDiffThresholds(
        arguments.max_mse, arguments.min_ssim)
    failures = thresholds.failures(metrics)
    if not failures:
        return 0
    message = "; ".join(failures)
    print(f"quality gate failed: {message}", file=sys.stderr)
    return 1


def main():
    arguments = argument_parser().parse_args()
    metrics = run(arguments)
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    return quality_gate(arguments, metrics)


if __name__ == "__main__":
    raise SystemExit(main())
