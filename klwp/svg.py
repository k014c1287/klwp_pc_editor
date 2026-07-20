"""Parse the SVG paths embedded in KLWP shapes and icon payloads."""

import base64
import gzip
import math
import re

from .runtime import Image, ImageDraw


SVG_TOKEN_PATTERN = re.compile(
    r"[A-Za-z]|-?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?")


class SvgTokenStream:
    def __init__(self, path):
        self._tokens = SVG_TOKEN_PATTERN.findall(path)
        self._position = 0

    def available(self):
        return self._position < len(self._tokens)

    def current(self):
        if not self.available():
            return None
        return self._tokens[self._position]

    def take(self):
        token = self.current()
        if token is not None:
            self._position += 1
        return token

    def number(self):
        return float(self.take())


class SvgPathState:
    def __init__(self):
        self._values = {
            "command": None,
            "current": (0.0, 0.0),
            "start": (0.0, 0.0),
            "previous_control": None,
            "subpaths": [],
            "points": [],
        }

    def __getitem__(self, name):
        return self._values[name]

    def __setitem__(self, name, value):
        self._values[name] = value

    def append(self, point):
        self._values["points"].append(point)

    def extend(self, points):
        self._values["points"].extend(points)

    def finish_subpath(self):
        if self._values["points"]:
            self._values["subpaths"].append(self._values["points"])
        self._values["points"] = []

    def close_subpath(self):
        if self._values["points"]:
            self._values["points"].append(self._values["start"])
        self.finish_subpath()
        self._values["current"] = self._values["start"]


class BezierCurve:
    @staticmethod
    def points(control_points, sample_count=14):
        samples = []
        for index in range(1, sample_count + 1):
            samples.append(BezierCurve._sample(
                control_points, index / sample_count))
        return samples

    @staticmethod
    def _sample(control_points, progress):
        points = list(control_points)
        while len(points) > 1:
            points = BezierCurve._interpolate(points, progress)
        return points[0]

    @staticmethod
    def _interpolate(points, progress):
        pairs = zip(points, points[1:])
        return [(
            (1 - progress) * first[0] + progress * second[0],
            (1 - progress) * first[1] + progress * second[1],
        ) for first, second in pairs]


class SvgArc:
    def __init__(self, start, end, radii, rotation, large_arc, sweep):
        self._values = {
            "start": start, "end": end, "radii": radii,
            "rotation": rotation, "large_arc": large_arc, "sweep": sweep,
        }

    def points(self, sample_count=18):
        radius_horizontal, radius_vertical = self._values["radii"]
        if radius_horizontal == 0 or radius_vertical == 0:
            return [self._values["end"]]
        geometry = self._geometry()
        return [self._point(geometry, index / sample_count)
                for index in range(1, sample_count + 1)]

    def _geometry(self):
        rotation = math.radians(self._values["rotation"])
        cosine, sine = math.cos(rotation), math.sin(rotation)
        start_horizontal, start_vertical = self._values["start"]
        end_horizontal, end_vertical = self._values["end"]
        difference_horizontal = (start_horizontal - end_horizontal) / 2
        difference_vertical = (start_vertical - end_vertical) / 2
        transformed_horizontal = cosine * difference_horizontal + sine * difference_vertical
        transformed_vertical = -sine * difference_horizontal + cosine * difference_vertical
        radius_horizontal, radius_vertical = self._corrected_radii(
            transformed_horizontal, transformed_vertical)
        center = self._center(
            transformed_horizontal, transformed_vertical,
            radius_horizontal, radius_vertical, cosine, sine)
        angles = self._angles(
            transformed_horizontal, transformed_vertical,
            radius_horizontal, radius_vertical, center["transformed"])
        return {
            "center": center["absolute"], "radii": (radius_horizontal, radius_vertical),
            "cosine": cosine, "sine": sine,
            "start_angle": angles[0], "sweep_angle": angles[1],
        }

    def _corrected_radii(self, horizontal, vertical):
        radius_horizontal, radius_vertical = map(abs, self._values["radii"])
        multiplier = horizontal ** 2 / radius_horizontal ** 2
        multiplier += vertical ** 2 / radius_vertical ** 2
        if multiplier > 1:
            correction = math.sqrt(multiplier)
            return radius_horizontal * correction, radius_vertical * correction
        return radius_horizontal, radius_vertical

    def _center(self, horizontal, vertical, radius_horizontal,
                radius_vertical, cosine, sine):
        numerator = radius_horizontal ** 2 * radius_vertical ** 2
        numerator -= radius_horizontal ** 2 * vertical ** 2
        numerator -= radius_vertical ** 2 * horizontal ** 2
        denominator = radius_horizontal ** 2 * vertical ** 2
        denominator += radius_vertical ** 2 * horizontal ** 2
        coefficient = math.sqrt(max(0, numerator / denominator)) if denominator else 0
        if self._values["large_arc"] == self._values["sweep"]:
            coefficient = -coefficient
        transformed_horizontal = coefficient * radius_horizontal * vertical / radius_vertical
        transformed_vertical = -coefficient * radius_vertical * horizontal / radius_horizontal
        start_horizontal, start_vertical = self._values["start"]
        end_horizontal, end_vertical = self._values["end"]
        absolute_horizontal = cosine * transformed_horizontal - sine * transformed_vertical
        absolute_horizontal += (start_horizontal + end_horizontal) / 2
        absolute_vertical = sine * transformed_horizontal + cosine * transformed_vertical
        absolute_vertical += (start_vertical + end_vertical) / 2
        return {
            "transformed": (transformed_horizontal, transformed_vertical),
            "absolute": (absolute_horizontal, absolute_vertical),
        }

    def _angles(self, horizontal, vertical, radius_horizontal,
                radius_vertical, transformed_center):
        center_horizontal, center_vertical = transformed_center
        start_vector = (
            (horizontal - center_horizontal) / radius_horizontal,
            (vertical - center_vertical) / radius_vertical,
        )
        end_vector = (
            (-horizontal - center_horizontal) / radius_horizontal,
            (-vertical - center_vertical) / radius_vertical,
        )
        start_angle = SvgArc._vector_angle((1, 0), start_vector)
        sweep_angle = SvgArc._vector_angle(start_vector, end_vector)
        if not self._values["sweep"] and sweep_angle > 0:
            sweep_angle -= 2 * math.pi
        if self._values["sweep"] and sweep_angle < 0:
            sweep_angle += 2 * math.pi
        return start_angle, sweep_angle

    @staticmethod
    def _vector_angle(first, second):
        cross = first[0] * second[1] - first[1] * second[0]
        dot = first[0] * second[0] + first[1] * second[1]
        return math.atan2(cross, dot)

    @staticmethod
    def _point(geometry, progress):
        angle = geometry["start_angle"] + geometry["sweep_angle"] * progress
        radius_horizontal, radius_vertical = geometry["radii"]
        center_horizontal, center_vertical = geometry["center"]
        cosine, sine = geometry["cosine"], geometry["sine"]
        horizontal = center_horizontal + radius_horizontal * math.cos(angle) * cosine
        horizontal -= radius_vertical * math.sin(angle) * sine
        vertical = center_vertical + radius_horizontal * math.cos(angle) * sine
        vertical += radius_vertical * math.sin(angle) * cosine
        return horizontal, vertical


class SvgPathParser:
    def __init__(self, path):
        self._stream = SvgTokenStream(path)
        self._state = SvgPathState()

    def subpaths(self):
        while self._safe_step():
            pass
        state = self._state
        state.finish_subpath()
        return state["subpaths"]

    def _safe_step(self):
        stream = self._stream
        if not stream.available():
            return False
        try:
            self._step()
            return True
        except (IndexError, TypeError, ValueError):
            return False

    def _step(self):
        self._accept_command()
        state = self._state
        stream = self._stream
        command = state["command"]
        if command is None:
            stream.take()
            return
        handlers = {
            "M": self._move, "L": self._line,
            "H": self._horizontal, "V": self._vertical,
            "C": self._cubic, "S": self._cubic,
            "Q": self._quadratic, "T": self._quadratic,
            "A": self._arc, "Z": self._close,
        }
        handler = handlers.get(command.upper(), self._unknown)
        preserve_control = handler(command.islower())
        if not preserve_control:
            state["previous_control"] = None

    def _accept_command(self):
        stream = self._stream
        state = self._state
        token = stream.current()
        if token is not None and token.isalpha():
            state["command"] = stream.take()

    def _move(self, relative):
        point = self._point(relative)
        state = self._state
        state.finish_subpath()
        state["current"] = point
        state["start"] = point
        state["points"] = [point]
        state["command"] = "l" if relative else "L"
        return False

    def _line(self, relative):
        point = self._point(relative)
        state = self._state
        state["current"] = point
        state.append(point)
        return False

    def _horizontal(self, relative):
        stream = self._stream
        state = self._state
        horizontal = stream.number()
        current_horizontal, current_vertical = state["current"]
        if relative:
            horizontal += current_horizontal
        point = horizontal, current_vertical
        state["current"] = point
        state.append(point)
        return False

    def _vertical(self, relative):
        stream = self._stream
        state = self._state
        vertical = stream.number()
        current_horizontal, current_vertical = state["current"]
        if relative:
            vertical += current_vertical
        point = current_horizontal, vertical
        state["current"] = point
        state.append(point)
        return False

    def _cubic(self, relative):
        state = self._state
        command_value = state["command"]
        command = command_value.upper()
        first_control = self._cubic_first_control(command, relative)
        second_control = self._point(relative)
        endpoint = self._point(relative)
        current = state["current"]
        points = BezierCurve.points([
            current, first_control, second_control, endpoint])
        state.extend(points)
        state["previous_control"] = second_control
        state["current"] = endpoint
        return True

    def _cubic_first_control(self, command, relative):
        if command == "C":
            return self._point(relative)
        return self._reflected_control()

    def _quadratic(self, relative):
        state = self._state
        command_value = state["command"]
        command = command_value.upper()
        control = self._quadratic_control(command, relative)
        endpoint = self._point(relative)
        current = state["current"]
        points = BezierCurve.points([current, control, endpoint])
        state.extend(points)
        state["previous_control"] = control
        state["current"] = endpoint
        return True

    def _quadratic_control(self, command, relative):
        if command == "Q":
            return self._point(relative)
        return self._reflected_control()

    def _reflected_control(self):
        state = self._state
        current_horizontal, current_vertical = state["current"]
        previous = state["previous_control"]
        if previous is None:
            return state["current"]
        return (
            2 * current_horizontal - previous[0],
            2 * current_vertical - previous[1],
        )

    def _arc(self, relative):
        stream = self._stream
        state = self._state
        radii = stream.number(), stream.number()
        rotation = stream.number()
        large_arc = int(stream.number())
        sweep = int(stream.number())
        endpoint = self._point(relative)
        arc = SvgArc(
            state["current"], endpoint, radii,
            rotation, large_arc, sweep)
        points = arc.points()
        state.extend(points)
        state["current"] = endpoint
        return False

    def _close(self, _relative):
        state = self._state
        state.close_subpath()
        state["command"] = None
        return False

    def _unknown(self, _relative):
        stream = self._stream
        stream.take()
        return False

    def _point(self, relative):
        stream = self._stream
        horizontal = stream.number()
        vertical = stream.number()
        if not relative:
            return horizontal, vertical
        state = self._state
        current_horizontal, current_vertical = state["current"]
        return horizontal + current_horizontal, vertical + current_vertical


def _svg_subpaths(path):
    """Expand SVG path data to lists of sampled points."""
    return SvgPathParser(path).subpaths()


def _point_in_poly(point, polygon):
    horizontal, vertical = point
    inside = False
    previous_index = len(polygon) - 1
    for index in range(len(polygon)):
        inside = _crossing_state(
            horizontal, vertical, polygon, index, previous_index, inside)
        previous_index = index
    return inside


def _crossing_state(horizontal, vertical, polygon, index,
                    previous_index, inside):
    first_horizontal, first_vertical = polygon[index]
    previous_horizontal, previous_vertical = polygon[previous_index]
    crosses_vertical = (first_vertical > vertical) != (previous_vertical > vertical)
    denominator = (previous_vertical - first_vertical) or 1e-9
    boundary = (previous_horizontal - first_horizontal)
    boundary *= (vertical - first_vertical) / denominator
    boundary += first_horizontal
    if crosses_vertical and horizontal < boundary:
        return not inside
    return inside


def svg_path_mask(path, width, height, viewbox=None):
    """Rasterize SVG path data into an even-odd Pillow mask."""
    subpaths = [subpath for subpath in _svg_subpaths(path) if len(subpath) >= 3]
    if not subpaths:
        return None
    resolved_viewbox = viewbox or _subpath_viewbox(subpaths)
    view_horizontal, view_vertical, view_width, view_height = resolved_viewbox
    scale_horizontal = width / view_width
    scale_vertical = height / view_height
    scaled = [[(
        (point[0] - view_horizontal) * scale_horizontal,
        (point[1] - view_vertical) * scale_vertical,
    ) for point in subpath] for subpath in subpaths]
    mask = Image.new("L", (width, height), 0)
    drawing = ImageDraw.Draw(mask)
    for index, polygon in enumerate(scaled):
        _paint_even_odd_polygon(drawing, scaled, index, polygon)
    return mask


def _subpath_viewbox(subpaths):
    horizontal_values = [point[0] for subpath in subpaths for point in subpath]
    vertical_values = [point[1] for subpath in subpaths for point in subpath]
    horizontal = min(horizontal_values)
    vertical = min(vertical_values)
    width = max(horizontal_values) - horizontal or 1
    height = max(vertical_values) - vertical or 1
    return horizontal, vertical, width, height


def _paint_even_odd_polygon(drawing, polygons, index, polygon):
    containers = (
        other for other_index, other in enumerate(polygons)
        if other_index != index and _point_in_poly(polygon[0], other)
    )
    parity = sum(1 for _container in containers)
    drawing.polygon(polygon, fill=0 if parity % 2 else 255)


def decode_kustom_icon(icon):
    """Decode Kustom's ``name#base64-gzip-svg`` icon representation."""
    if not isinstance(icon, str) or "#" not in icon:
        return icon, None, None
    name, payload = icon.split("#", 1)
    try:
        svg = gzip.decompress(base64.b64decode(payload)).decode("utf-8")
    except Exception:
        return name, None, None
    paths = re.findall(r'\bd="([^"]+)"', svg)
    viewbox_match = re.search(r'viewBox="([\d.\s-]+)"', svg)
    viewbox = _decoded_viewbox(viewbox_match)
    return name, paths or None, viewbox


def _decoded_viewbox(match):
    if match is None:
        return None
    return tuple(float(value) for value in match.group(1).split())
