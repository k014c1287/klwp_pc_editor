"""Editor-facing facade for animation, event and switch settings."""

from ..shared import *  # noqa: F401,F403
from .setting_forms import AnimationFormDialog, EventFormDialog
from .setting_lists import ModuleSettingListDialog
from .setting_values import SwitchReferenceCounter, switch_global_names
from .global_dialog import GlobalManagerDialog


class SettingsMixin:
    @staticmethod
    def _animation_summary(animation):
        reaction = str(animation.get("type", "?"))
        action = str(animation.get("action") or "SCROLL")
        detail = ""
        if reaction == "SWITCH":
            detail = f" / {animation.get('trigger', '未選択')}"
        if reaction == "SCROLL":
            detail = f" / {animation.get('center', '自動')}"
        return f"{reaction} → {action}{detail}"

    @staticmethod
    def _event_summary(event):
        action = str(event.get("action", "NONE"))
        if action == "SWITCH_GLOBAL":
            return f"タップ → Switch「{event.get('switch', '未選択')}」"
        return f"タップ → {action}"

    def _switch_global_names(self, globals_=None):
        global_values = globals_
        if global_values is None:
            archive = self.memory['archive']
            root_module = archive.root_module()
            global_values = root_module.get("globals_list", {})
        return switch_global_names(global_values)

    def _switch_reference_count(self, name):
        archive = self.memory['archive']
        root_module = archive.root_module()
        modules = root_module.get("viewgroup_items", [])
        return SwitchReferenceCounter(name).count(modules)

    def _animation_form(self, parent, initial=None):
        return AnimationFormDialog(self, parent, initial).show()

    def _edit_animations(self):
        item = self.memory['selected']
        if item is not None:
            ModuleSettingListDialog(self, item, "animation").show()

    def _event_form(self, parent, initial=None):
        return EventFormDialog(self, parent, initial).show()

    def _edit_tap_events(self):
        item = self.memory['selected']
        if item is not None:
            ModuleSettingListDialog(self, item, "event").show()

    def _edit_globals(self):
        scope = self.memory["archive"].root_module()
        GlobalManagerDialog(self, scope).show()

    def _edit_local_globals(self):
        selected = self.memory["selected"]
        if not isinstance(selected, dict) or "globals_list" not in selected:
            return
        GlobalManagerDialog(self, selected).show()
