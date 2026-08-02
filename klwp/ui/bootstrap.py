"""Initialize the editor window and its first-class application memory."""

from ..shared import (
    APP_TITLE, ApplicationMemory, HistoryTimeline, KlwpArchive,
)
from ..preview.values import default_preview_values
from ..recent import RecentFileStore
from .welcome import WelcomeDialog
from .theme import EditorTheme
from .window import EditorWindowBuilder
from .services import EditorServices


class BootstrapMixin:
    def __init__(self):
        super().__init__()
        EditorTheme(self).apply()
        self.memory = ApplicationMemory()
        self.services = EditorServices(self)
        self.title(APP_TITLE)
        self.geometry("1280x820")
        self._initialize_document_memory()
        self._initialize_preview_memory()
        self._initialize_history_memory()
        EditorWindowBuilder(self).build()
        self._reset_preview_state()
        self._reset_history()
        services = self.services
        services.start_preview_clock()
        self._refresh_all()
        self.after_idle(self._show_welcome)

    def _initialize_document_memory(self):
        memory = self.memory
        archive = KlwpArchive()
        archive.new()
        information = archive["preset"]["preset_info"]
        memory.initialize_document({
            "archive": archive, "module_clipboard": None,
            "photo_cache": {}, "font_cache": {},
            "device_res": (1080, 2400),
            "preview_values": default_preview_values(),
            "recent_files": RecentFileStore(),
        })
        memory.initialize_selection({
            "selected": None, "selected_items": (), "tree_map": {},
            "tree_drag": None, "drag_state": None, "resize_state": None,
            "snap_guides": (), "snap_correction": (0.0, 0.0),
        })
        memory.initialize_viewport({
            "_view_pan_state": None, "preview_zoom": 1.0,
            "_view_origin": (0.0, 0.0), "_quality_preview": None,
        })
        memory["preview_ts"] = information["ts"]

    def _initialize_preview_memory(self):
        memory = self.memory
        memory.initialize_preview({
            "interaction_drag": None, "preview_scroll": 0.0,
            "preview_switches": {}, "preview_switch_progress": {},
            "_switch_transitions": {}, "_scroll_transition": None,
            "_animation_after_id": None, "_loop_started_at": None,
            "_event_regions": [], "_time_after_id": None,
            "_updating_time_control": False,
        })
        memory["_zoom_render_after_id"] = None

    def _initialize_history_memory(self):
        memory = self.memory
        memory.initialize_history({
            "history": HistoryTimeline(self.HISTORY_LIMIT), "dirty": False,
        })

    def _show_welcome(self):
        WelcomeDialog(self).show()
