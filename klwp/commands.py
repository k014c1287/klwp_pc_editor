"""Model-level edit commands with UI-neutral outcomes."""

from .positioning import PositionMutation


class EditOutcome:
    def __init__(self, changed, selection=None, status="", refresh="all"):
        self._values = {
            "changed": bool(changed), "selection": selection,
            "status": status, "refresh": refresh,
        }

    def __getitem__(self, name):
        return self._values[name]

    @staticmethod
    def unchanged():
        return EditOutcome(False)


class AddModulesCommand:
    def __init__(self, parent, items, index=None, status=""):
        self._values = {
            "parent": parent, "items": tuple(items),
            "index": index, "status": status,
        }

    def execute(self):
        values = self._values
        parent = values["parent"]
        items = values["items"]
        index = values["index"]
        if index is None:
            index = len(parent)
        for offset, item in enumerate(items):
            parent.insert(index + offset, item)
        return EditOutcome(True, items, values["status"])


class RemoveModulesCommand:
    def __init__(self, targets, status=""):
        self._values = (tuple(targets), status)

    def execute(self):
        targets, status = self._values
        for item, parent in reversed(targets):
            parent.remove(item)
        return EditOutcome(True, (), status)


class MoveModulesCommand:
    def __init__(self, parent, items, difference):
        self._values = (parent, tuple(items), int(difference))

    def execute(self):
        parent, items, difference = self._values
        index = self._target_index(parent, items, difference)
        if index is None:
            return EditOutcome.unchanged()
        for item in items:
            parent.remove(item)
        for offset, item in enumerate(items):
            parent.insert(index + offset, item)
        return EditOutcome(True, items)

    @staticmethod
    def _target_index(parent, items, difference):
        indexes = tuple(parent.index(item) for item in items)
        if difference < 0 and min(indexes) == 0:
            return None
        if difference > 0 and max(indexes) == len(parent) - 1:
            return None
        return min(indexes) + difference


class SetVisibilityCommand:
    def __init__(self, items, visible):
        self._values = (tuple(items), bool(visible))

    def execute(self):
        items, visible = self._values
        for item in items:
            item["config_visible"] = visible
        state = "表示" if visible else "非表示"
        status = f"{len(items)}件を{state}にしました"
        return EditOutcome(True, items, status)


class ArrangeModulesCommand:
    def __init__(self, movements, root_items, parent, label):
        self._values = {
            "movements": tuple(movements), "root": root_items,
            "parent": parent, "label": label,
        }

    def execute(self):
        values = self._values
        is_root = values["parent"] is values["root"]
        movements = values["movements"]
        for item, horizontal, vertical in movements:
            mutation = PositionMutation(item, is_root)
            mutation.move_by(horizontal, vertical)
        status = f"{len(movements)}件を{values['label']}しました"
        return EditOutcome(True, status=status, refresh="preview")


class NudgeModulesCommand:
    def __init__(self, targets, root_items, nudge):
        self._values = (tuple(targets), root_items, nudge)

    def execute(self):
        targets, root_items, nudge = self._values
        for item, parent in targets:
            mutation = PositionMutation(item, parent is root_items)
            nudge.apply_to(mutation)
        return EditOutcome(True, refresh="preview")


class GroupModulesCommand:
    def __init__(self, parent, items, group, index):
        self._values = (parent, tuple(items), group, int(index))

    def execute(self):
        parent, items, group, index = self._values
        for item in items:
            parent.remove(item)
        parent.insert(index, group)
        status = f"{len(items)}件の要素をグループ化しました"
        return EditOutcome(True, (group,), status)


class UngroupModulesCommand:
    def __init__(self, parent, group, children, index):
        self._values = (parent, group, tuple(children), int(index))

    def execute(self):
        parent, group, children, index = self._values
        parent.remove(group)
        for offset, child in enumerate(children):
            parent.insert(index + offset, child)
        status = f"{len(children)}件の要素へグループ解除しました"
        return EditOutcome(True, children, status)
