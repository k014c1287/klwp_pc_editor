"""Build the module tree without nested traversal logic in the editor."""

from ..shared import MODULE_LABELS, module_label


class ModuleTreePresentation:
    @staticmethod
    def title(item):
        title = str(item.get("internal_title") or "").strip()
        if title:
            return title
        return module_label(item)

    @staticmethod
    def kind(item):
        module_type = item.get("internal_type", "?")
        return MODULE_LABELS.get(module_type, module_type)

    @staticmethod
    def priority(index, count):
        rank = count - index
        if rank == 1:
            return "1・最前面"
        return str(rank)

    @staticmethod
    def tags(item):
        visible = item.get("config_visible", True)
        if visible is False or str(visible).lower() == "false":
            return ("hidden",)
        return ()


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
        for index, item in enumerate(items):
            found = self._add_item(
                item, items, index, parent_identifier)
            selected_identifier = found or selected_identifier
        return selected_identifier

    def _add_item(self, item, siblings, index, parent_identifier):
        owner = self._owner
        memory = owner.memory
        tree = memory['tree']
        presentation = ModuleTreePresentation
        identifier = tree.insert(
            parent_identifier, "end", text=presentation.title(item),
            values=(presentation.kind(item),
                    presentation.priority(index, len(siblings))),
            tags=presentation.tags(item),
            open=parent_identifier == "" and bool(item.get("viewgroup_items")))
        memory['tree_map'][identifier] = (item, siblings)
        selected_identifier = identifier if item is self._selected else None
        nested = self._add_items(item.get("viewgroup_items", []), identifier)
        return nested or selected_identifier
