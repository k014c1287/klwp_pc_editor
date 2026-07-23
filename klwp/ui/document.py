"""Document lifecycle, history commands and module-list operations."""

from ..shared import *  # noqa: F401,F403
from ..positioning import PositionMutation
from .asset_dialogs import BackgroundDialog, ImageManagerDialog
from .shape_dialog import ShapeDialog
from .tree import ModuleTreeBuilder


class DocumentLifecycleMixin:
    def _confirm_discard(self):
        if not self.memory['dirty']:
            return True
        return messagebox.askyesno(
            APP_TITLE, "未保存の変更があります。破棄して続行しますか？")

    def cmd_new(self):
        if not self._confirm_discard():
            return
        archive = self.memory['archive']
        archive.new()
        information = archive["preset"]["preset_info"]
        self.memory['preview_ts'] = information["ts"]
        self.memory['device_res'] = (1080, 2400)
        self._after_document_loaded()

    def cmd_open(self):
        if not self._confirm_discard():
            return
        path = filedialog.askopenfilename(
            filetypes=[("KLWP preset", "*.klwp"), ("All files", "*.*")])
        if not path:
            return
        if not self._load_archive(path):
            return
        information = self.memory['archive']["preset"].get("preset_info", {})
        self._apply_document_dimensions(information)
        self.memory['preview_ts'] = information.get("ts")
        self._after_document_loaded()

    def _load_archive(self, path):
        try:
            self.memory['archive'].load(path)
            return True
        except Exception as error:
            messagebox.showerror(
                APP_TITLE, f"読み込みに失敗しました:\n{error}")
            return False

    def _apply_document_dimensions(self, information):
        width = int(information.get("width", 0) or 0)
        height = int(information.get("height", 0) or 0)
        if width > 0 and height > 0:
            self.memory['device_res'] = (width, height)

    def _after_document_loaded(self):
        self.memory['selected'] = None
        self.memory['drag_state'] = None
        self.memory['resize_state'] = None
        self.memory['photo_cache'].clear()
        self.memory['font_cache'].clear()
        self._reset_preview_state()
        self._reset_history()
        self._refresh_all()

    def cmd_save(self):
        path = self.memory['archive']['path']
        if path:
            self._do_save(path)
            return
        self.cmd_save_as()

    def cmd_save_as(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".klwp",
            filetypes=[("KLWP preset", "*.klwp")])
        if path:
            self._do_save(path)

    def _do_save(self, path):
        try:
            self._save_archive(path)
        except Exception as error:
            messagebox.showerror(APP_TITLE, f"保存に失敗しました:\n{error}")

    def _save_archive(self, path):
        self.memory['archive'].save(path)
        self.memory['history'].saved(self._snapshot_archive())
        self.memory['dirty'] = False
        self._update_history_ui()
        name = basename(path)
        self.memory['status'].config(text=f"保存しました: {name}")

class DocumentMixin(DocumentLifecycleMixin):
    def _snapshot_archive(self):
        archive = self.memory['archive']
        return ArchiveSnapshot(
            preset=copy.deepcopy(archive["preset"]),
            bitmaps=dict(archive["bitmaps"]),
            fonts=dict(archive["fonts"]),
            extras=dict(archive["extras"]),
        )

    def _restore_archive_snapshot(self, snapshot):
        archive = self.memory['archive']
        archive["preset"] = copy.deepcopy(snapshot["preset"])
        archive["bitmaps"] = dict(snapshot["bitmaps"])
        archive["fonts"] = dict(snapshot["fonts"])
        archive["extras"] = dict(snapshot["extras"])
        self.memory['selected'] = None
        self.memory['drag_state'] = None
        self.memory['resize_state'] = None
        self.memory['photo_cache'].clear()
        self.memory['font_cache'].clear()
        self._reset_preview_state()

    def _reset_history(self):
        self.memory['history'].reset(self._snapshot_archive())
        self.memory['dirty'] = False
        self._update_history_ui()

    def _update_title(self):
        mark = ""
        if self.memory['dirty']:
            mark = "*"
        path = self.memory['archive']['path'] or "無題"
        name = basename(path)
        self.title(f"{APP_TITLE} - {name}{mark}")

    def _update_history_ui(self):
        history = self.memory['history']
        self._configure_history_button("undo_button", history.can_undo())
        self._configure_history_button("redo_button", history.can_redo())
        self._update_title()

    def _configure_history_button(self, button_name, enabled):
        memory = self.memory
        button = memory.optional(button_name)
        if button is None:
            return
        state = "disabled"
        if enabled:
            state = "normal"
        button.configure(state=state)

    def cmd_undo(self):
        target = self.memory['history'].undo()
        if target is None:
            return
        self._apply_history_target(target)
        self.memory['status'].config(text="元に戻しました")

    def cmd_redo(self):
        target = self.memory['history'].redo()
        if target is None:
            return
        self._apply_history_target(target)
        self.memory['status'].config(text="やり直しました")

    def _apply_history_target(self, target):
        self._restore_archive_snapshot(target)
        self.memory['dirty'] = self.memory['history'].dirty()
        self._update_history_ui()
        self._refresh_all()

    def _on_undo_shortcut(self, _event=None):
        self.cmd_undo()
        return "break"

    def _on_redo_shortcut(self, _event=None):
        self.cmd_redo()
        return "break"

    def _on_delete_shortcut(self, _event=None):
        target = self._deletion_target()
        if target is not None:
            self._delete_target(target)
        return "break"

    def _target_list(self):
        selected = self.memory['selected']
        if selected is not None and "viewgroup_items" in selected:
            return selected.setdefault("viewgroup_items", [])
        identifier = self._selected_iid()
        if identifier and identifier in self.memory['tree_map']:
            _item, parent = self.memory['tree_map'][identifier]
            return parent
        return self.memory['archive'].modules()

    def cmd_add(self, kind):
        item = make_module(kind)
        target = self._target_list()
        self._prepare_item_position(item, target)
        target.append(item)
        self.memory['selected'] = item
        self._mark_dirty()
        self._refresh_all(select=item)

    def _prepare_item_position(self, item, target):
        archive = self.memory['archive']
        if target is archive.modules():
            return
        item.pop("position_offset_x", None)
        item.pop("position_offset_y", None)

    def cmd_add_shape(self):
        ShapeDialog(self).show()

    def cmd_duplicate(self):
        identifier = self._selected_iid()
        if not identifier:
            return
        item, parent = self.memory['tree_map'][identifier]
        clone = copy.deepcopy(item)
        clone["internal_title"] = (item.get("internal_title") or "") + " copy"
        archive = self.memory['archive']
        mutation = PositionMutation(clone, parent is archive.modules())
        mutation.move_by(30.0, 30.0)
        parent.insert(parent.index(item) + 1, clone)
        self.memory['selected'] = clone
        self._mark_dirty()
        self._refresh_all(select=clone)

    def cmd_delete(self):
        target = self._deletion_target()
        if target is None:
            return
        item, _parent = target
        if not self._confirmed_deletion(item):
            return
        self._delete_target(target)

    def _deletion_target(self):
        identifier = self._selected_iid()
        if not identifier:
            return None
        tree_map = self.memory['tree_map']
        return tree_map.get(identifier)

    @staticmethod
    def _confirmed_deletion(item):
        question = f"「{module_label(item)}」を削除しますか？"
        return messagebox.askyesno(APP_TITLE, question)

    def _delete_target(self, target):
        item, parent = target
        parent.remove(item)
        self.memory['selected'] = None
        self._mark_dirty()
        self._refresh_all()

    def cmd_move(self, difference):
        identifier = self._selected_iid()
        if not identifier:
            return
        item, parent = self.memory['tree_map'][identifier]
        current_index = parent.index(item)
        target_index = current_index + difference
        if 0 <= target_index < len(parent):
            parent[current_index], parent[target_index] = \
                parent[target_index], parent[current_index]
            self._mark_dirty()
            self._refresh_all(select=item)

    def cmd_background(self):
        BackgroundDialog(self).show()

    def cmd_images(self):
        ImageManagerDialog(self).show()

    def _refresh_all(self, select=None):
        self._rebuild_tree(select)
        self._render()
        self._build_props()
        self._update_title()

    def _rebuild_tree(self, select=None):
        ModuleTreeBuilder(self, select).build()

    def _selected_iid(self):
        selection = self.memory['tree'].selection()
        if not selection:
            return None
        return selection[0]

    def cmd_clear_selection(self):
        memory = self.memory
        tree = memory['tree']
        selection = tree.selection()
        if selection:
            tree.selection_remove(*selection)
        memory['selected'] = None
        memory['drag_state'] = None
        memory['resize_state'] = None
        self._render()
        self._build_props()
        memory['status'].config(
            text="選択を解除しました。次の要素はルートへ追加されます")

    def _on_clear_selection_shortcut(self, _event=None):
        self.cmd_clear_selection()
        return "break"

    def _on_tree_select(self, _event):
        identifier = self._selected_iid()
        self.memory['selected'] = None
        if identifier:
            self.memory['selected'] = self.memory['tree_map'][identifier][0]
        self._render()
        self._build_props()
