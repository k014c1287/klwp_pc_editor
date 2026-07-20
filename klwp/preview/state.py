"""Initialize the transient, unsaved preview interaction state."""


def preview_boolean(value):
    if not isinstance(value, str):
        return bool(value)
    normalized = value.strip()
    normalized = normalized.lower()
    return normalized not in ("", "0", "false", "off", "no")


class PreviewStateResetter:
    def __init__(self, owner):
        self._owner = owner

    def reset(self):
        self._cancel_timer()
        self._clear_animation_state()
        self._configure_loop_button()
        self._clear_switches()
        self._load_switches()
        self._configure_page_control()
        owner = self._owner
        owner._update_preview_page_label()

    def _cancel_timer(self):
        owner = self._owner
        memory = owner.memory
        timer_identifier = memory.optional("_animation_after_id")
        if timer_identifier is None:
            return
        attributes = owner.__dict__
        if attributes.get("tk") is None:
            return
        try:
            owner.after_cancel(timer_identifier)
        except Exception:
            return

    def _clear_animation_state(self):
        owner = self._owner
        memory = owner.memory
        memory['_animation_after_id'] = None
        memory['_scroll_transition'] = None
        memory['_switch_transitions'] = {}
        memory['_loop_started_at'] = None
        memory['_event_regions'] = []

    def _configure_loop_button(self):
        owner = self._owner
        memory = owner.memory
        loop_button = memory.optional("loop_button")
        if loop_button is not None:
            loop_button.configure(text="ループ再生")

    def _clear_switches(self):
        owner = self._owner
        memory = owner.memory
        memory['preview_scroll'] = 0.0
        memory['preview_switches'] = {}
        memory['preview_switch_progress'] = {}

    def _load_switches(self):
        owner = self._owner
        memory = owner.memory
        archive = memory['archive']
        root_module = archive.root_module()
        global_values = root_module.get("globals_list", {})
        if not isinstance(global_values, dict):
            return
        for name, entry in global_values.items():
            self._load_switch(name, entry)

    def _load_switch(self, name, entry):
        if not isinstance(entry, dict):
            return
        if entry.get("type") != "SWITCH":
            return
        enabled = preview_boolean(entry.get("value", False))
        owner = self._owner
        memory = owner.memory
        memory['preview_switches'][str(name)] = enabled
        memory['preview_switch_progress'][str(name)] = float(enabled)

    def _configure_page_control(self):
        owner = self._owner
        memory = owner.memory
        page_count = owner._preview_page_count()
        page_scale = memory.optional("preview_page_scale")
        if page_scale is not None:
            page_scale.configure(to=float(page_count))
        page_variable = memory.optional("preview_page_var")
        if page_variable is not None:
            page_variable.set(1.0)
