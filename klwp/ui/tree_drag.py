"""Drag-and-drop ordering for module rows in the left tree."""

from ..shared import module_label


class TreeReorder:
    @staticmethod
    def move(siblings, source, target, after):
        if source is target:
            return False
        siblings.remove(source)
        target_index = siblings.index(target)
        siblings.insert(target_index + int(after), source)
        return True


class TreeDragMixin:
    def _on_tree_press(self, event):
        tree = self.memory["tree"]
        identifier = tree.identify_row(event.y)
        self.memory["tree_drag"] = self._new_tree_drag(identifier, event.y)
        if identifier:
            return None
        self.cmd_clear_selection()
        return "break"

    def _new_tree_drag(self, identifier, vertical):
        tree_map = self.memory["tree_map"]
        if not identifier or identifier not in tree_map:
            return None
        item, siblings = tree_map[identifier]
        return {
            "source_identifier": identifier, "source_item": item,
            "siblings": siblings, "start_vertical": vertical,
            "active": False, "target": None,
        }

    def _on_tree_drag(self, event):
        state = self.memory["tree_drag"]
        if state is None:
            return
        distance = abs(event.y - state["start_vertical"])
        if distance < 5 and not state["active"]:
            return
        state["active"] = True
        self.memory["tree"].configure(cursor="hand2")
        target = self._tree_drop_target(state, event.y)
        self._show_tree_drop_target(state, target)

    def _tree_drop_target(self, state, vertical):
        tree = self.memory["tree"]
        identifier = tree.identify_row(vertical)
        tree_map = self.memory["tree_map"]
        if not identifier or identifier not in tree_map:
            return None
        item, siblings = tree_map[identifier]
        if siblings is not state["siblings"] or item is state["source_item"]:
            return None
        bounds = tree.bbox(identifier)
        if not bounds:
            return None
        after = vertical >= bounds[1] + bounds[3] / 2
        return {"identifier": identifier, "item": item, "after": after}

    def _show_tree_drop_target(self, state, target):
        self._restore_tree_drop_target(state)
        if target is None:
            self._tree_drop_unavailable(state)
            return
        tree = self.memory["tree"]
        identifier = target["identifier"]
        original_tags = tree.item(identifier, "tags")
        target["original_tags"] = original_tags
        tag = "drop_after" if target["after"] else "drop_before"
        tree.item(identifier, tags=tuple(original_tags) + (tag,))
        state["target"] = target
        self._tree_drop_status(target)

    def _tree_drop_unavailable(self, state):
        message = "同じレイヤー内の別要素へドロップしてください"
        if not state["active"]:
            message = ""
        self.memory["status"].configure(text=message)

    def _tree_drop_status(self, target):
        position = "後（前面側）" if target["after"] else "前（背面側）"
        label = module_label(target["item"])
        self.memory["status"].configure(
            text=f"「{label}」の{position}へ移動")

    def _restore_tree_drop_target(self, state):
        target = state.get("target")
        if target is None:
            return
        tree = self.memory["tree"]
        identifier = target["identifier"]
        if tree.exists(identifier):
            tree.item(identifier, tags=target["original_tags"])
        state["target"] = None

    def _on_tree_release(self, _event):
        state = self.memory["tree_drag"]
        if state is None:
            return
        moved = self._commit_tree_drop(state)
        self._restore_tree_drop_target(state)
        self.memory["tree"].configure(cursor="")
        self.memory["tree_drag"] = None
        if not moved:
            return
        item = state["source_item"]
        self._mark_dirty()
        self._refresh_all(select=item)
        self.memory["status"].configure(text="表示優先度を変更しました")
        return "break"

    @staticmethod
    def _commit_tree_drop(state):
        if not state["active"]:
            return False
        target = state["target"]
        if target is None:
            return False
        return TreeReorder.move(
            state["siblings"], state["source_item"],
            target["item"], target["after"])
