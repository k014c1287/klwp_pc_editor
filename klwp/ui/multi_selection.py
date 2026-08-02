"""Commands that operate on every module selected in the tree."""

from ..shared import (
    APP_TITLE, messagebox, module_label,
)
from ..clipboard import ModuleClipboard
from ..commands import (
    AddModulesCommand, MoveModulesCommand, NudgeModulesCommand,
    RemoveModulesCommand,
)
from ..positioning import KeyboardNudge, PositionMutation
from ..selection import ModuleSelection
from .command_execution import execute_editor_command


class MultiSelectionMixin:
    def _module_selection(self):
        return ModuleSelection.from_memory(self.memory)

    def _selected_iid(self):
        tree = self.memory["tree"]
        selection = tree.selection()
        if not selection:
            return None
        focused = tree.focus()
        if focused in selection:
            return focused
        return selection[-1]

    def cmd_copy(self):
        selection = self._module_selection()
        if selection.empty():
            self._set_status("コピーする要素を選択してください")
            return
        archive = self.memory["archive"]
        package = ModuleClipboard.capture(selection.items(), archive)
        self.memory["module_clipboard"] = package
        self._set_status(f"{package.count()}件の要素をコピーしました")

    def cmd_paste(self):
        memory = self.memory
        package = memory.optional("module_clipboard")
        if package is None:
            self._set_status("貼り付ける要素がありません")
            return
        archive = self.memory["archive"]
        target = self._target_list()
        clones = package.paste_into(archive)
        self._prepare_pasted_items(clones, target)
        insertion_index = self._paste_index(target)
        status = f"{len(clones)}件の要素を貼り付けました"
        command = AddModulesCommand(target, clones, insertion_index, status)
        execute_editor_command(self, command)

    def _prepare_pasted_items(self, items, target):
        archive = self.memory["archive"]
        is_root = target is archive.modules()
        for item in items:
            self._prepare_item_position(item, target)
            PositionMutation(item, is_root).move_by(30.0, 30.0)

    def _paste_index(self, target):
        selection = self._module_selection()
        if not selection.same_parent() or selection.parent() is not target:
            return len(target)
        targets = selection.ordered_targets()
        return target.index(targets[-1][0]) + 1

    def _select_modules(self, items):
        memory = self.memory
        memory["selected_items"] = tuple(items)
        memory["selected"] = items[-1] if items else None

    def _on_copy_shortcut(self, _event=None):
        self.cmd_copy()
        return "break"

    def _on_paste_shortcut(self, _event=None):
        self.cmd_paste()
        return "break"

    def _on_nudge_shortcut(self, event):
        selection = self._module_selection()
        nudge = KeyboardNudge.from_event(event)
        if selection.empty() or nudge is None:
            return None
        self._nudge_selection(selection, nudge)
        return "break"

    def _nudge_selection(self, selection, nudge):
        archive = self.memory["archive"]
        root_items = archive.modules()
        targets = selection.ordered_targets()
        command = NudgeModulesCommand(targets, root_items, nudge)
        execute_editor_command(self, command)

    def cmd_duplicate(self):
        selection = self._module_selection()
        if selection.empty():
            return
        if not selection.same_parent():
            self._set_status("複製は同じレイヤー内の要素を選択してください")
            return
        archive = self.memory["archive"]
        package = ModuleClipboard.capture(selection.items(), archive)
        clones = package.paste_into(archive)
        parent = selection.parent()
        self._prepare_pasted_items(clones, parent)
        insertion_index = parent.index(selection.ordered_targets()[-1][0]) + 1
        for clone in clones:
            self._name_duplicate(clone)
        command = AddModulesCommand(parent, clones, insertion_index)
        execute_editor_command(self, command)

    @staticmethod
    def _name_duplicate(item):
        title = item.get("internal_title") or ""
        item["internal_title"] = title + " copy"

    def cmd_delete(self):
        selection = self._module_selection()
        if selection.empty():
            return
        if not self._confirmed_selection_deletion(selection):
            return
        self._delete_selection(selection)

    @staticmethod
    def _confirmed_selection_deletion(selection):
        if selection.count() == 1:
            label = module_label(selection.items()[0])
            return messagebox.askyesno(APP_TITLE, f"「{label}」を削除しますか？")
        question = f"選択した{selection.count()}件の要素を削除しますか？"
        return messagebox.askyesno(APP_TITLE, question)

    def _on_delete_shortcut(self, _event=None):
        selection = self._module_selection()
        if not selection.empty():
            self._delete_selection(selection)
        return "break"

    def _delete_selection(self, selection):
        count = selection.count()
        targets = selection.ordered_targets()
        status = f"{count}件の要素を削除しました"
        command = RemoveModulesCommand(targets, status)
        execute_editor_command(self, command)

    def cmd_move(self, difference):
        selection = self._module_selection()
        if selection.empty() or not selection.same_parent():
            self._set_status("同じレイヤー内の要素を選択してください")
            return
        parent = selection.parent()
        items = [target[0] for target in selection.ordered_targets()]
        command = MoveModulesCommand(parent, items, difference)
        execute_editor_command(self, command)
