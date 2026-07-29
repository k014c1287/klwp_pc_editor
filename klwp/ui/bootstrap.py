"""Initialize the editor window and its first-class application memory."""

from ..shared import *  # noqa: F401,F403
from ..preview.values import default_preview_values
from .window import EditorWindowBuilder


class BootstrapMixin:
    def __init__(self):
        super().__init__()
        self.memory = ApplicationMemory()
        self.title(APP_TITLE)
        self.geometry("1280x820")
        self._initialize_document_memory()
        self._initialize_preview_memory()
        self._initialize_history_memory()
        EditorWindowBuilder(self).build()
        self._reset_preview_state()
        self._reset_history()
        self._refresh_all()

    def _initialize_document_memory(self):
        memory = self.memory
        memory['archive'] = KlwpArchive()
        memory['archive'].new()
        information = memory['archive']["preset"]["preset_info"]
        memory['preview_ts'] = information["ts"]
        memory['selected'] = None
        memory['tree_map'] = {}
        memory['tree_drag'] = None
        memory['photo_cache'] = {}
        memory['font_cache'] = {}
        memory['device_res'] = (1080, 2400)
        memory['preview_values'] = default_preview_values()
        memory['drag_state'] = None
        memory['resize_state'] = None
        memory['_view_pan_state'] = None
        memory['preview_zoom'] = 1.0
        memory['_view_origin'] = (0.0, 0.0)
        memory['_quality_preview'] = None

    def _initialize_preview_memory(self):
        memory = self.memory
        memory['interaction_drag'] = None
        memory['preview_scroll'] = 0.0
        memory['preview_switches'] = {}
        memory['preview_switch_progress'] = {}
        memory['_switch_transitions'] = {}
        memory['_scroll_transition'] = None
        memory['_animation_after_id'] = None
        memory['_zoom_render_after_id'] = None
        memory['_loop_started_at'] = None
        memory['_event_regions'] = []

    def _initialize_history_memory(self):
        memory = self.memory
        memory['history'] = HistoryTimeline(self.HISTORY_LIMIT)
        memory['dirty'] = False
