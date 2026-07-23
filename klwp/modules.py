"""KLWP editor core responsibility."""

from .runtime import *  # noqa: F401,F403
from .formula import sample_eval


DEFAULT_ANCHOR = "CENTER"

# ----------------------------------------------------------------------------
# 新規要素テンプレート
# ----------------------------------------------------------------------------
SHAPE_TYPE_OPTIONS = (
    "正方形", "円", "長方形", "楕円形", "三角形", "直角三角形",
    "六角形", "扇形", "弧型", "角丸四角形", "Path",
)

SHAPE_TYPE_SPECS = {
    # KLWPでは正方形がShapeModuleの既定値で、shape_type自体を省略する。
    "正方形": {"shape_width": 140.0, "shape_height": 140.0},
    "円": {"shape_type": "CIRCLE", "shape_width": 140.0,
          "shape_height": 140.0},
    "長方形": {"shape_type": "RECT", "shape_width": 200.0,
            "shape_height": 100.0, "shape_corners": 0.0},
    "楕円形": {"shape_type": "OVAL", "shape_width": 200.0,
            "shape_height": 110.0},
    "三角形": {"shape_type": "TRIANGLE", "shape_width": 150.0,
            "shape_height": 130.0},
    "直角三角形": {"shape_type": "RTRIANGLE", "shape_width": 150.0,
              "shape_height": 130.0},
    "六角形": {"shape_type": "EXAGON", "shape_width": 160.0,
            "shape_height": 140.0},
    "扇形": {"shape_type": "SLICE", "shape_width": 140.0,
           "shape_height": 140.0, "shape_offset": 90.0},
    "弧型": {"shape_type": "ARC", "shape_width": 140.0,
           "shape_height": 140.0, "shape_offset": 90.0,
           "paint_style": "STROKE", "paint_stroke": 12.0},
    "角丸四角形": {"shape_type": "SQUIRCLE", "shape_width": 160.0,
              "shape_height": 160.0},
    "Path": {"shape_type": "PATH", "shape_width": 160.0,
             "shape_height": 160.0,
             "shape_path": "M 10,10 H 90 V 90 H 10 Z"},
}


def make_module(kind):
    builders = {
        "text": _text_module,
        "shape": _shape_module,
        "icon": _icon_module,
        "bitmap": _bitmap_module,
        "layer": _layer_module,
    }
    builder = builders.get(kind)
    if builder is None:
        raise ValueError(kind)
    module = builder()
    module.update(_position_defaults())
    return module


def _position_defaults():
    return {
        "position_anchor": "TOPLEFT",
        "position_offset_x": 100.0,
        "position_offset_y": 100.0,
    }


def _text_module():
    return {
        "internal_type": "TextModule", "internal_title": "新規テキスト",
        "text_expression": "Hello", "text_size": 40.0,
        "text_family": "Roboto-Regular", "paint_color": "#FFFFFFFF",
    }


def _shape_module():
    return {
        "internal_type": "ShapeModule", "internal_title": "新規図形",
        "shape_type": "RECT", "shape_width": 200.0, "shape_height": 100.0,
        "shape_corners": 20.0, "paint_color": "#80FFFFFF",
    }


def _icon_module():
    return {
        "internal_type": "FontIconModule", "internal_title": "新規アイコン",
        "icon_set": "material", "icon_icon": "star", "icon_size": 60.0,
        "paint_color": "#FFFFFFFF",
    }


def _bitmap_module():
    return {
        "internal_type": "BitmapModule", "internal_title": "新規画像",
        "bitmap_bitmap": "", "bitmap_width": 240.0, "bitmap_alpha": 100.0,
    }


def _layer_module():
    return {
        "internal_type": "OverlapLayerModule", "internal_title": "新規レイヤー",
        "viewgroup_items": [],
    }


def make_shape_module(shape_name):
    """日本語UI上の図形名からKLWP ShapeModuleを作る。"""
    if shape_name not in SHAPE_TYPE_SPECS:
        raise ValueError(shape_name)
    module = make_module("shape")
    for key in ("shape_type", "shape_width", "shape_height", "shape_corners",
                "shape_offset", "shape_path", "paint_style", "paint_stroke"):
        module.pop(key, None)
    module.update(copy.deepcopy(SHAPE_TYPE_SPECS[shape_name]))
    module["internal_title"] = f"新規{shape_name}"
    return module


MODULE_LABELS = {
    "TextModule": "テキスト", "ShapeModule": "図形",
    "FontIconModule": "アイコン", "OverlapLayerModule": "重ねレイヤー",
    "StackLayerModule": "並べレイヤー", "ProgressModule": "プログレス",
    "BitmapModule": "画像", "RootLayerModule": "ルート",
    "KomponentModule": "コンポーネント",
}


def module_label(item):
    module_type = item.get("internal_type", "?")
    name = item.get("internal_title") or ""
    label = MODULE_LABELS.get(module_type, module_type)
    if module_type == "TextModule" and not name:
        name = sample_eval(item.get("text_expression", ""))[:14]
    return f"{label}  {name}".rstrip()


def parse_color(color, default="#FFFFFF"):
    """KLWP の #AARRGGBB / #RRGGBB を Tk 用 #RRGGBB と不透明度に分解。"""
    if not isinstance(color, str) or not color.startswith("#"):
        return default, 255
    hexadecimal = color[1:]
    if len(hexadecimal) == 8:
        return _parse_argb(hexadecimal, default)
    if len(hexadecimal) == 6:
        return "#" + hexadecimal, 255
    return default, 255


def _parse_argb(hexadecimal, default):
    try:
        return "#" + hexadecimal[2:], int(hexadecimal[:2], 16)
    except ValueError:
        return default, 255

