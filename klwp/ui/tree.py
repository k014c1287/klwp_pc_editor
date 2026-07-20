"""Build the module tree without nested traversal logic in the editor."""

from ..shared import module_label


class ModuleTreeBuilder:
    def __init__(self, owner, selected):
        self._owner = owner
        self._selected = selected

    def build(self):
        owner = self._owner
        memory = owner.memory
        tree = memory['tree']
        tree.delete(*tree.get_children())
        memory['tree_map'].clear()
        selected_identifier = self._add_items(
            memory['archive'].modules(), "")
        if selected_identifier is not None:
            tree.selection_set(selected_identifier)
            tree.see(selected_identifier)

    def _add_items(self, items, parent_identifier):
        selected_identifier = None
        for item in items:
            found = self._add_item(item, items, parent_identifier)
            selected_identifier = found or selected_identifier
        return selected_identifier

    def _add_item(self, item, siblings, parent_identifier):
        owner = self._owner
        memory = owner.memory
        identifier = memory['tree'].insert(
            parent_identifier, "end", text=module_label(item), open=False)
        memory['tree_map'][identifier] = (item, siblings)
        selected_identifier = identifier if item is self._selected else None
        nested = self._add_items(item.get("viewgroup_items", []), identifier)
        return nested or selected_identifier
