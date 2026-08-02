"""Commands for aligning and distributing selected modules."""

from ..alignment import AlignmentLayout
from ..commands import ArrangeModulesCommand
from .command_execution import execute_editor_command


class AlignmentMixin:
    def cmd_align_left(self):
        self._arrange_selection("left", 2, "左揃え")

    def cmd_align_center_horizontal(self):
        self._arrange_selection("center_horizontal", 2, "水平方向中央揃え")

    def cmd_align_right(self):
        self._arrange_selection("right", 2, "右揃え")

    def cmd_align_top(self):
        self._arrange_selection("top", 2, "上揃え")

    def cmd_align_center_vertical(self):
        self._arrange_selection("center_vertical", 2, "垂直方向中央揃え")

    def cmd_align_bottom(self):
        self._arrange_selection("bottom", 2, "下揃え")

    def cmd_distribute_horizontal(self):
        self._arrange_selection("distribute_horizontal", 3, "水平均等配置")

    def cmd_distribute_vertical(self):
        self._arrange_selection("distribute_vertical", 3, "垂直均等配置")

    def _arrange_selection(self, operation, minimum, label):
        selection = self._module_selection()
        if not self._arrangeable(selection, minimum):
            self._arrangement_error(minimum)
            return
        entries = self._alignment_entries(selection)
        if entries is None:
            self._set_status("非表示要素を含むため配置できません")
            return
        layout = AlignmentLayout(entries)
        movements = layout.movements(operation)
        self._apply_alignment(selection, movements, label)

    @staticmethod
    def _arrangeable(selection, minimum):
        return selection.count() >= minimum and selection.same_parent()

    def _arrangement_error(self, minimum):
        self._set_status(
            f"同じレイヤー内の要素を{minimum}件以上選択してください")

    def _alignment_entries(self, selection):
        targets = selection.ordered_targets()
        entries = tuple(map(self._alignment_entry, targets))
        if any(entry is None for entry in entries):
            return None
        return entries

    def _alignment_entry(self, target):
        item, _parent = target
        bounds = self._bounds(item)
        if bounds is None:
            return None
        return item, bounds

    def _apply_alignment(self, selection, movements, label):
        archive = self.memory["archive"]
        root_items = archive.modules()
        parent = selection.parent()
        command = ArrangeModulesCommand(movements, root_items, parent, label)
        execute_editor_command(self, command)
