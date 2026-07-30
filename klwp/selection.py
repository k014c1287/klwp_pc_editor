"""First-class collection for the module rows selected in the tree."""


class ModuleSelection:
    def __init__(self, targets, focused=None):
        self._values = {"targets": tuple(targets), "focused": focused}

    @staticmethod
    def from_memory(memory):
        tree = memory["tree"]
        tree_map = memory["tree_map"]
        identifiers = tree.selection()
        targets = tuple(filter(None, map(tree_map.get, identifiers)))
        focused = tree_map.get(tree.focus())
        return ModuleSelection(targets, focused)

    def count(self):
        return len(self._values["targets"])

    def empty(self):
        return not self._values["targets"]

    def items(self):
        return tuple(target[0] for target in self._values["targets"])

    def primary_item(self):
        focused = self._values["focused"]
        if focused is not None:
            return focused[0]
        targets = self._values["targets"]
        if not targets:
            return None
        return targets[-1][0]

    def same_parent(self):
        targets = self._values["targets"]
        if not targets:
            return False
        parent = targets[0][1]
        return all(target[1] is parent for target in targets)

    def parent(self):
        if not self.same_parent():
            return None
        return self._values["targets"][0][1]

    def ordered_targets(self):
        parent = self.parent()
        if parent is None:
            return self._values["targets"]
        return tuple(sorted(
            self._values["targets"],
            key=lambda target: parent.index(target[0])))

    def remove_all(self):
        targets = reversed(self.ordered_targets())
        for item, parent in targets:
            parent.remove(item)


class SelectedItemCollection:
    def __init__(self, items=()):
        self._items = tuple(items)

    def items(self):
        return self._items

    def primary(self):
        if not self._items:
            return None
        return self._items[-1]
