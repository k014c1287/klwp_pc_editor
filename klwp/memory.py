"""Responsibility-based application state with mapping compatibility."""


DOCUMENT_KEYS = (
    "archive", "device_res", "module_clipboard", "preview_values",
    "recent_files", "photo_cache", "font_cache",
)
SELECTION_KEYS = (
    "selected", "selected_items", "tree_map", "tree_drag", "drag_state",
    "resize_state", "snap_guides", "snap_correction",
)
PREVIEW_KEYS = (
    "preview_ts", "interaction_drag", "interaction_mode", "preview_scroll",
    "preview_switches", "preview_switch_progress", "_switch_transitions",
    "_scroll_transition", "_animation_after_id", "_loop_started_at",
    "_event_regions", "_time_after_id", "_updating_time_control",
    "_updating_page_control", "_doc", "_item_bounds", "_photo", "_scale",
)
VIEWPORT_KEYS = (
    "preview_zoom", "preview_zoom_label", "_view_origin", "_view_pan_state",
    "_quality_preview", "_zoom_render_after_id", "_viewport_size",
    "snap_enabled",
)
INTERFACE_KEYS = (
    "canvas", "tree", "status", "prop_frame", "_prop_color_controls",
    "_prop_vars", "menu_bar", "primary_toolbar", "undo_button",
    "redo_button", "loop_button", "preview_page_label",
    "preview_page_scale", "preview_page_var", "preview_time_label",
    "preview_time_live_var", "preview_time_var",
)
HISTORY_KEYS = ("history", "dirty")


class MemoryKeys:
    def __init__(self, names=(), accepts_unknown=False):
        self._values = (frozenset(names), bool(accepts_unknown))

    def accepts(self, name):
        names, accepts_unknown = self._values
        return accepts_unknown or name in names


class MemoryValues:
    def __init__(self):
        self._values = {}

    def __getitem__(self, name):
        return self._values[name]

    def __setitem__(self, name, value):
        self._values[name] = value

    def optional(self, name, default=None):
        values = self._values
        return values.get(name, default)

    def contains(self, name):
        return name in self._values

    def replace(self, values):
        current = self._values
        current.update(values)


class MemoryPartition:
    def __init__(self, keys):
        self._keys = keys
        self._values = MemoryValues()

    def accepts(self, name):
        keys = self._keys
        return keys.accepts(name)

    def __getitem__(self, name):
        return self._values[name]

    def __setitem__(self, name, value):
        self._values[name] = value

    def optional(self, name, default=None):
        values = self._values
        return values.optional(name, default)

    def contains(self, name):
        values = self._values
        return values.contains(name)

    def replace(self, values):
        current = self._values
        current.replace(values)


class MemoryPartitions:
    def __init__(self):
        self._values = {
            "document": MemoryPartition(MemoryKeys(DOCUMENT_KEYS)),
            "selection": MemoryPartition(MemoryKeys(SELECTION_KEYS)),
            "preview": MemoryPartition(MemoryKeys(PREVIEW_KEYS)),
            "viewport": MemoryPartition(MemoryKeys(VIEWPORT_KEYS)),
            "interface": MemoryPartition(MemoryKeys(INTERFACE_KEYS)),
            "history": MemoryPartition(MemoryKeys(HISTORY_KEYS)),
            "extension": MemoryPartition(MemoryKeys(accepts_unknown=True)),
        }

    def partition(self, name):
        values = self._values
        partitions = values.values()
        accepted = filter(lambda partition: partition.accepts(name), partitions)
        return next(accepted)

    def initialize(self, domain, values):
        partitions = self._values
        partition = partitions[domain]
        partition.replace(values)


class ApplicationMemory:
    """Routes mutable state to responsibility-specific partitions."""

    def __init__(self):
        self._partitions = MemoryPartitions()

    def __getitem__(self, name):
        partitions = self._partitions
        partition = partitions.partition(name)
        return partition[name]

    def __setitem__(self, name, value):
        partitions = self._partitions
        partition = partitions.partition(name)
        partition[name] = value

    def optional(self, name, default=None):
        partitions = self._partitions
        partition = partitions.partition(name)
        return partition.optional(name, default)

    def contains(self, name):
        partitions = self._partitions
        partition = partitions.partition(name)
        return partition.contains(name)

    def initialize_document(self, values):
        self._initialize("document", values)

    def initialize_selection(self, values):
        self._initialize("selection", values)

    def initialize_preview(self, values):
        self._initialize("preview", values)

    def initialize_viewport(self, values):
        self._initialize("viewport", values)

    def initialize_interface(self, values):
        self._initialize("interface", values)

    def initialize_history(self, values):
        self._initialize("history", values)

    def _initialize(self, domain, values):
        partitions = self._partitions
        partitions.initialize(domain, values)
