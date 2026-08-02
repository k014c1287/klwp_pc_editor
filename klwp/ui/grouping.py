"""Create and dissolve static OverlapLayer groups without visual jumps."""

from ..shared import (
    make_module,
)
from ..commands import GroupModulesCommand, UngroupModulesCommand
from .command_execution import execute_editor_command


POSITION_NAMES = {
    "position_anchor", "position_offset_x", "position_offset_y",
    "position_padding_left", "position_padding_right",
    "position_padding_top", "position_padding_bottom",
}


class GroupCompatibility:
    @staticmethod
    def movable(item):
        if item.get("internal_animations"):
            return False
        formulas = item.get("internal_formulas", {})
        globals_ = item.get("internal_globals", {})
        dynamic_names = set(formulas) | set(globals_)
        return not bool(dynamic_names & POSITION_NAMES)

    @staticmethod
    def dissolvable(item):
        names = (
            "internal_animations", "internal_events",
            "internal_formulas", "internal_globals", "globals_list",
        )
        return not any(item.get(name) for name in names)


class GroupGeometry:
    def __init__(self, owner, items):
        self._values = {"owner": owner, "items": tuple(items)}

    def item_bounds(self):
        owner = self._values["owner"]
        bounds = tuple(map(owner._bounds, self._values["items"]))
        if any(value is None for value in bounds):
            return None
        return bounds

    @staticmethod
    def union(bounds):
        left = min(value[0] for value in bounds)
        top = min(value[1] for value in bounds)
        right = max(value[0] + value[2] for value in bounds)
        bottom = max(value[1] + value[3] for value in bounds)
        return left, top, right - left, bottom - top


class GroupPosition:
    @staticmethod
    def inside(item, bounds, container):
        left, top, width, height = bounds
        container_left, container_top, container_width, container_height = container
        item["position_anchor"] = "TOPLEFT"
        item.pop("position_offset_x", None)
        item.pop("position_offset_y", None)
        item["position_padding_left"] = round(left - container_left, 1)
        item["position_padding_top"] = round(top - container_top, 1)
        item["position_padding_right"] = round(
            container_left + container_width - left - width, 1)
        item["position_padding_bottom"] = round(
            container_top + container_height - top - height, 1)

    @staticmethod
    def root(item, bounds):
        left, top, _width, _height = bounds
        item["position_anchor"] = "TOPLEFT"
        item["position_offset_x"] = round(left, 1)
        item["position_offset_y"] = round(top, 1)
        for name in (
                "position_padding_left", "position_padding_right",
                "position_padding_top", "position_padding_bottom"):
            item.pop(name, None)


class ParentModuleLocator:
    @staticmethod
    def find(root_items, child_list):
        modules = ParentModuleLocator._all_modules(root_items)
        matches = filter(
            lambda module: module.get("viewgroup_items") is child_list,
            modules)
        return next(matches, None)

    @staticmethod
    def _all_modules(root_items):
        pending = list(root_items)
        modules = []
        while pending:
            module = pending.pop()
            modules.append(module)
            pending.extend(module.get("viewgroup_items", []))
        return tuple(modules)


class GroupingMixin:
    def cmd_group_selection(self):
        selection = self._module_selection()
        if selection.count() < 2 or not selection.same_parent():
            self._set_status("同じレイヤー内の要素を2件以上選択してください")
            return
        items = [target[0] for target in selection.ordered_targets()]
        if not all(map(GroupCompatibility.movable, items)):
            self._set_status("動的位置設定またはアニメーション付き要素はグループ化できません")
            return
        geometry = GroupGeometry(self, items)
        item_bounds = geometry.item_bounds()
        if item_bounds is None:
            self._set_status("非表示要素を含むためグループ化できません")
            return
        self._create_group(selection, items, item_bounds)

    def _create_group(self, selection, items, item_bounds):
        parent = selection.parent()
        insertion_index = min(parent.index(item) for item in items)
        group_bounds = GroupGeometry.union(item_bounds)
        group = make_module("layer")
        group["internal_title"] = "グループ"
        group["viewgroup_items"] = items
        for item, bounds in zip(items, item_bounds):
            GroupPosition.inside(item, bounds, group_bounds)
        self._position_group(group, group_bounds, parent)
        command = GroupModulesCommand(parent, items, group, insertion_index)
        execute_editor_command(self, command)

    def _position_group(self, group, group_bounds, parent):
        archive = self.memory["archive"]
        root_items = archive.modules()
        if parent is root_items:
            GroupPosition.root(group, group_bounds)
            return
        parent_item = ParentModuleLocator.find(root_items, parent)
        parent_bounds = self._bounds(parent_item)
        GroupPosition.inside(group, group_bounds, parent_bounds)

    def cmd_ungroup_selection(self):
        selection = self._module_selection()
        if selection.count() != 1:
            self._set_status("解除する重ねレイヤーを1件選択してください")
            return
        group = selection.primary_item()
        children = group.get("viewgroup_items", [])
        if not children or not GroupCompatibility.dissolvable(group):
            self._set_status("設定を持つレイヤーまたは空レイヤーは解除できません")
            return
        if not all(map(GroupCompatibility.movable, children)):
            self._set_status("動的位置設定またはアニメーション付きの子要素があります")
            return
        self._dissolve_group(selection, group, children)

    def _dissolve_group(self, selection, group, children):
        geometry = GroupGeometry(self, children)
        child_bounds = geometry.item_bounds()
        if child_bounds is None:
            self._set_status("非表示要素を含むためグループ解除できません")
            return
        parent = selection.parent()
        insertion_index = parent.index(group)
        self._position_ungrouped(children, child_bounds, parent)
        command = UngroupModulesCommand(
            parent, group, children, insertion_index)
        execute_editor_command(self, command)

    def _position_ungrouped(self, children, child_bounds, parent):
        archive = self.memory["archive"]
        root_items = archive.modules()
        if parent is root_items:
            self._position_root_children(children, child_bounds)
            return
        parent_item = ParentModuleLocator.find(root_items, parent)
        parent_bounds = self._bounds(parent_item)
        for child, bounds in zip(children, child_bounds):
            GroupPosition.inside(child, bounds, parent_bounds)

    @staticmethod
    def _position_root_children(children, child_bounds):
        for child, bounds in zip(children, child_bounds):
            GroupPosition.root(child, bounds)
