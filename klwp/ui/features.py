"""Owner-bound feature controllers composed into the editor."""

from .alignment import AlignmentMixin
from .adb_transfer import AdbTransferMixin
from .command_palette import CommandPaletteMixin
from .export_png import PngExportMixin
from .layer_actions import LayerActionsMixin
from .time_preview import TimePreviewMixin


class BoundEditorFeature:
    def __init__(self, owner):
        self._owner = owner

    def __getattr__(self, name):
        owner = self._owner
        return getattr(owner, name)


class AlignmentController(AlignmentMixin, BoundEditorFeature):
    pass


class AdbTransferController(AdbTransferMixin, BoundEditorFeature):
    pass


class CommandPaletteController(CommandPaletteMixin, BoundEditorFeature):
    pass


class PngExportController(PngExportMixin, BoundEditorFeature):
    pass


class LayerActionsController(LayerActionsMixin, BoundEditorFeature):
    pass


class TimePreviewController(TimePreviewMixin, BoundEditorFeature):
    pass


class EditorFeatures:
    def __init__(self, owner):
        self._values = {
            "adb": AdbTransferController(owner),
            "alignment": AlignmentController(owner),
            "command_palette": CommandPaletteController(owner),
            "png": PngExportController(owner),
            "layer_actions": LayerActionsController(owner),
            "time_preview": TimePreviewController(owner),
        }

    def __getitem__(self, name):
        return self._values[name]
