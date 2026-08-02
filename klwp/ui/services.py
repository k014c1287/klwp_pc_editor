"""Composed feature services exposed to editor UI builders."""

from .command_execution import EditCommandExecutor
from .features import EditorFeatures


class EditorServices:
    def __init__(self, owner):
        self._commands = EditCommandExecutor(owner)
        self._features = EditorFeatures(owner)

    def execute(self, command):
        commands = self._commands
        return commands.execute(command)

    def cmd_export_png(self):
        return self._call("png", "cmd_export_png")

    def cmd_adb_transfer(self):
        return self._call("adb", "cmd_adb_transfer")

    def cmd_command_palette(self):
        return self._call("command_palette", "cmd_command_palette")

    def on_command_palette_shortcut(self, event=None):
        return self._call(
            "command_palette", "_on_command_palette_shortcut", event)

    def on_tree_visibility_click(self, event):
        return self._call(
            "layer_actions", "_on_tree_visibility_click", event)

    def cmd_toggle_visibility(self):
        return self._call("layer_actions", "cmd_toggle_visibility")

    def on_tree_context_menu(self, event):
        return self._call("layer_actions", "_on_tree_context_menu", event)

    def start_preview_clock(self):
        return self._call("time_preview", "_start_preview_clock")

    def on_live_time_changed(self):
        return self._call("time_preview", "_on_live_time_changed")

    def on_preview_time_changed(self, value):
        return self._call(
            "time_preview", "_on_preview_time_changed", value)

    def cmd_align_left(self):
        return self._call("alignment", "cmd_align_left")

    def cmd_align_center_horizontal(self):
        return self._call("alignment", "cmd_align_center_horizontal")

    def cmd_align_right(self):
        return self._call("alignment", "cmd_align_right")

    def cmd_align_top(self):
        return self._call("alignment", "cmd_align_top")

    def cmd_align_center_vertical(self):
        return self._call("alignment", "cmd_align_center_vertical")

    def cmd_align_bottom(self):
        return self._call("alignment", "cmd_align_bottom")

    def cmd_distribute_horizontal(self):
        return self._call("alignment", "cmd_distribute_horizontal")

    def cmd_distribute_vertical(self):
        return self._call("alignment", "cmd_distribute_vertical")

    def _call(self, feature_name, command_name, *arguments):
        features = self._features
        feature = features[feature_name]
        command = getattr(feature, command_name)
        return command(*arguments)
