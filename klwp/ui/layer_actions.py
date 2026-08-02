"""Direct visibility and context-menu actions for the module tree."""

from ..shared import *  # noqa: F401,F403
from .tree import ModuleVisibility


class LayerActionsMixin:
    def _on_tree_visibility_click(self, event):
        tree = self.memory["tree"]
        column = tree.identify_column(event.x)
        if column != "#1":
            return None
        identifier = tree.identify_row(event.y)
        tree_map = self.memory["tree_map"]
        if not identifier or identifier not in tree_map:
            return None
        item, _parent = tree_map[identifier]
        tree.selection_set(identifier)
        tree.focus(identifier)
        self._toggle_visibility((item,))
        return "break"

    def cmd_toggle_visibility(self):
        selection = self._module_selection()
        if selection.empty():
            self._set_status("表示を切り替える要素を選択してください")
            return
        self._toggle_visibility(selection.items())

    def _toggle_visibility(self, items):
        target = ModuleVisibility.toggled_value(items)
        for item in items:
            item["config_visible"] = target
        self._select_modules(items)
        self._mark_dirty()
        self._refresh_all(select=tuple(items))
        state = "表示" if target else "非表示"
        self._set_status(f"{len(items)}件を{state}にしました")

    def _on_tree_context_menu(self, event):
        tree = self.memory["tree"]
        identifier = tree.identify_row(event.y)
        if not identifier or identifier not in self.memory["tree_map"]:
            return None
        self._select_context_row(tree, identifier)
        menu = self._context_menu(tree)
        self._popup_context_menu(menu, event.x_root, event.y_root)
        return "break"

    def _select_context_row(self, tree, identifier):
        selection = tree.selection()
        if identifier in selection:
            return
        tree.selection_set(identifier)
        tree.focus(identifier)
        self._on_tree_select(None)

    def _context_menu(self, tree):
        menu = tk.Menu(tree, tearoff=False)
        menu.add_command(
            label=self._visibility_menu_label(),
            command=self.cmd_toggle_visibility)
        menu.add_separator()
        menu.add_command(label="複製", command=self.cmd_duplicate)
        menu.add_command(label="削除", command=self._delete_context_selection)
        menu.add_separator()
        menu.add_command(label="背面へ", command=lambda: self.cmd_move(-1))
        menu.add_command(label="前面へ", command=lambda: self.cmd_move(1))
        return menu

    def _visibility_menu_label(self):
        selection = self._module_selection()
        target = ModuleVisibility.toggled_value(selection.items())
        if target:
            return "表示する"
        return "非表示にする"

    def _delete_context_selection(self):
        self._on_delete_shortcut()

    @staticmethod
    def _popup_context_menu(menu, horizontal, vertical):
        try:
            menu.tk_popup(horizontal, vertical)
        finally:
            menu.grab_release()
