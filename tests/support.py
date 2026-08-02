import copy
import io
import json
import tempfile
import unittest
from unittest.mock import Mock, patch
import zipfile
from datetime import datetime
from pathlib import Path

import klwp_editor as ke
from klwp.ui.property_panel import AnchorChoices, PropertyPanelBuilder
from klwp.ui.color_control import KlwpColor
from klwp.resize import ResizeHandleSet, ResizeSession
from klwp.positioning import KeyboardNudge, PositionMutation
from klwp.alignment import AlignmentLayout
from klwp.snap import SnapEngine, SnapTargets
from klwp.background import BackgroundImageBinding, BitmapGlobalCollection
from klwp.icons import IconCatalog, MATERIAL_ICON_SET
from klwp.svg import decode_kustom_icon
from klwp.ui.global_dialog import GlobalEntryValues
from klwp.ui.setting_values import TouchActionValues
from klwp.ui.kode_dialog import (
    KodeInspector, KodeSyntax, KodeTargetCollection,
)
from klwp.ui.document import DocumentMixin
from klwp.ui.interaction import InteractionMixin
from klwp.ui.multi_selection import MultiSelectionMixin
from klwp.ui.grouping import GroupingMixin
from klwp.ui.alignment import AlignmentMixin
from klwp.ui.menu_toolbar import EditorCommandCatalog, ToolbarPresentation
from klwp.ui.theme import EditorPalette, EditorTheme
from klwp.ui.window import EditorWindowBuilder
from klwp.adb import AdbDevices, AdbTransfer
from klwp.preview.pages import PresetPageCount, PreviewPageCounter
from klwp.preview.values import PREVIEW_VALUE_FIELDS, default_preview_values
from klwp.pixel_diff import (
    ComparableImages, ComparisonRegion, PixelDiff, PixelDiffThresholds,
    PresetPreview)
from klwp.runtime import Resampling
from klwp.preview.zoom import CachedPreviewImage, PreviewPan, PreviewZoom
from klwp.recent import RecentFileStore
from klwp.preview.timeline import PreviewTimeline
from klwp.ui.tree import ModuleTreePresentation, ModuleVisibility
from klwp.ui.tree_drag import TreeDragMixin, TreeReorder
from klwp.clipboard import ModuleClipboard
from klwp.selection import ModuleSelection
from klwp.ui.zoom import PreviewZoomMixin
from klwp.ui.export_png import PngExportMixin
from klwp.ui.command_palette import (
    CommandPaletteDialog, CommandPaletteEntries,
)
from klwp.ui.layer_actions import LayerActionsMixin
from klwp.ui.welcome import TemplateCatalog
from klwp.ui.time_preview import TimePreviewMixin


ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "sample"


class _TreeEditor(DocumentMixin, TreeDragMixin):
    pass


class _MultiEditor(
        MultiSelectionMixin, GroupingMixin, AlignmentMixin, DocumentMixin):
    def _set_status(self, text):
        self.memory["last_status"] = text


class _TimeEditor(TimePreviewMixin):
    def _set_status(self, text):
        self.memory["last_status"] = text


class _LayerEditor(
        MultiSelectionMixin, LayerActionsMixin, DocumentMixin):
    def _set_status(self, text):
        self.memory["last_status"] = text


class _PngExportEditor(PngExportMixin):
    def _set_status(self, text):
        self.memory["last_status"] = text

class _WidgetStub:
    def __init__(self):
        self.options = {}

    def config(self, **kwargs):
        self.options.update(kwargs)

    configure = config

__all__ = [name for name in globals() if not name.startswith('__')]
