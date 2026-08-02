"""Build the module tree without nested traversal logic in the editor."""

from ..shared import MODULE_LABELS, module_label


class ModuleVisibility:
    def __init__(self, item):
        self._item = item

    def shown(self):
        item = self._item
        value = item.get("config_visible", True)
        text = str(value)
        return value is not False and text.lower() != "false"

    def symbol(self):
        if self.shown():
            return "●"
        return "○"

    @staticmethod
    def toggled_value(items):
        states = map(lambda item: ModuleVisibility(item).shown(), items)
        return not any(states)


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
    def visibility(item):
        return ModuleVisibility(item).symbol()

    @staticmethod
    def tags(item):
        if not ModuleVisibility(item).shown():
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
        selected_identifiers = self._add_items(
            memory['archive'].modules(), "")
        if selected_identifiers:
            tree.selection_set(*selected_identifiers)
            tree.see(selected_identifiers[-1])

    def _add_items(self, items, parent_identifier):
        selected_identifiers = []
        for index, item in enumerate(items):
            found = self._add_item(
                item, items, index, parent_identifier)
            selected_identifiers.extend(found)
        return selected_identifiers

    def _add_item(self, item, siblings, index, parent_identifier):
        owner = self._owner
        memory = owner.memory
        tree = memory['tree']
        presentation = ModuleTreePresentation
        identifier = tree.insert(
            parent_identifier, "end", text=presentation.title(item),
            values=(presentation.visibility(item), presentation.kind(item),
                    presentation.priority(index, len(siblings))),
            tags=presentation.tags(item),
            open=parent_identifier == "" and bool(item.get("viewgroup_items")))
        memory['tree_map'][identifier] = (item, siblings)
        selected_identifiers = []
        if self._is_selected(item):
            selected_identifiers.append(identifier)
        nested = self._add_items(item.get("viewgroup_items", []), identifier)
        selected_identifiers.extend(nested)
        return selected_identifiers

    def _is_selected(self, item):
        selected = self._selected
        if isinstance(selected, tuple):
            return any(candidate is item for candidate in selected)
        return selected is item
