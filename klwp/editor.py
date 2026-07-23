"""Composition root for the desktop editor window."""

from .shared import *  # noqa: F401,F403
from .ui.bootstrap import BootstrapMixin
from .ui.document import DocumentMixin
from .preview.model import PreviewModelMixin
from .render.canvas import CanvasRendererMixin
from .render.layout import LayoutMixin
from .render.compositor import CompositorMixin
from .render.shapes import ShapeRendererMixin
from .render.content import ContentRendererMixin
from .render.text import TextRendererMixin
from .ui.interaction import InteractionMixin
from .ui.settings import SettingsMixin
from .ui.properties import PropertyPanelMixin
from .ui.preview_values import PreviewValuesMixin
from .ui.adb_transfer import AdbTransferMixin
from .ui.tree_drag import TreeDragMixin
from .ui.zoom import PreviewZoomMixin


if HAS_TK:
    class EditorApp(BootstrapMixin,
            DocumentMixin,
            PreviewModelMixin,
            CanvasRendererMixin,
            LayoutMixin,
            CompositorMixin,
            ShapeRendererMixin,
            ContentRendererMixin,
            TextRendererMixin,
            InteractionMixin,
            SettingsMixin,
            PropertyPanelMixin,
            PreviewValuesMixin,
            AdbTransferMixin,
            TreeDragMixin,
            PreviewZoomMixin,
            tk.Tk):
        CANVAS_W, CANVAS_H = 420, 760
        HISTORY_LIMIT = 50
        ICON_GLYPHS = {
            "play": "▶", "pause": "⏸", "next": "⏭", "skip": "⏭",
            "previous": "⏮", "wifi": "≋", "camera": "◎", "star": "★",
            "airplane": "✈", "signal": "⟟",
        }
        _TEXT_SPACING_U = 4.0
        PROP_FIELDS = [
            ("internal_title", "名前"), ("position_anchor", "アンカー"),
            ("position_offset_x", "横オフセット"),
            ("position_offset_y", "縦オフセット"),
            ("position_padding_left", "左余白"),
            ("position_padding_right", "右余白"),
            ("position_padding_top", "上余白"),
            ("position_padding_bottom", "下余白"),
            ("shape_type", "図形種別"), ("shape_width", "幅"),
            ("shape_height", "高さ"), ("shape_corners", "角丸"),
            ("shape_offset", "扇形・弧の角度"),
            ("paint_color", "色"),
            ("text_size", "文字サイズ"), ("text_family", "フォント"),
            ("icon_icon", "アイコン名"), ("icon_size", "アイコンサイズ"),
            ("bitmap_width", "画像幅"),
            ("bitmap_alpha", "画像不透明度 (0-100)"),
        ]

