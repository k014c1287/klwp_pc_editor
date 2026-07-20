"""List editors for animations and tap events attached to one module."""

from ..shared import *  # noqa: F401,F403


class ModuleSettingListDialog:
    def __init__(self, owner, item, setting_type):
        self._context = {
            "owner": owner, "item": item, "type": setting_type,
            "working": copy.deepcopy(self._initial_values(item, setting_type)),
        }

    @staticmethod
    def _initial_values(item, setting_type):
        field = ModuleSettingListDialog._configuration(setting_type)["field"]
        return item.get(field, []) or []

    @staticmethod
    def _configuration(setting_type):
        return {
            "animation": {
                "field": "internal_animations", "title": "アニメーション",
                "size": "570x400", "duplicate": True,
            },
            "event": {
                "field": "internal_events", "title": "タップイベント",
                "size": "540x350", "duplicate": False,
            },
        }[setting_type]

    def show(self):
        self._window()
        self._listbox()
        self._controls()
        self._bottom_buttons()
        self._refresh()

    def _window(self):
        owner = self._context["owner"]
        item = self._context["item"]
        configuration = self._configuration(self._context["type"])
        window = tk.Toplevel(owner)
        window.title(f"{configuration['title']} - {module_label(item)}")
        window.geometry(configuration["size"])
        window.transient(owner)
        window.grab_set()
        frame = ttk.Frame(window, padding=10)
        frame.pack(fill="both", expand=True)
        self._context["window"] = window
        self._context["frame"] = frame

    def _listbox(self):
        listbox = tk.Listbox(self._context["frame"])
        listbox.pack(fill="both", expand=True)
        self._context["listbox"] = listbox

    def _controls(self):
        frame = ttk.Frame(self._context["frame"])
        frame.pack(fill="x", pady=6)
        commands = [("追加", self._add), ("編集", self._edit)]
        if self._configuration(self._context["type"])["duplicate"]:
            commands.append(("複製", self._duplicate))
        commands.append(("削除", self._delete))
        for label, command in commands:
            ttk.Button(frame, text=label, command=command).pack(
                side="left", padx=2)

    def _bottom_buttons(self):
        frame = ttk.Frame(self._context["frame"])
        frame.pack(fill="x", pady=(6, 0))
        window = self._context["window"]
        ttk.Button(frame, text="キャンセル", command=window.destroy).pack(
            side="right", padx=4)
        ttk.Button(frame, text="適用", command=self._apply).pack(
            side="right", padx=4)

    def _refresh(self, selected=None):
        listbox = self._context["listbox"]
        listbox.delete(0, "end")
        for index, value in enumerate(self._context["working"], 1):
            listbox.insert("end", f"{index}. {self._summary(value)}")
        if self._context["working"]:
            index = min(
                len(self._context["working"]) - 1,
                self._selection_default(selected))
            listbox.selection_set(index)

    @staticmethod
    def _selection_default(selected):
        if selected is None:
            return 0
        return selected

    def _summary(self, value):
        owner = self._context["owner"]
        if self._context["type"] == "animation":
            return owner._animation_summary(value)
        return owner._event_summary(value)

    def _selected_index(self):
        selection = self._context["listbox"].curselection()
        if not selection:
            return None
        return selection[0]

    def _add(self):
        value = self._form()
        self._context["window"].grab_set()
        if value is None:
            return
        self._context["working"].append(value)
        self._refresh(len(self._context["working"]) - 1)

    def _edit(self):
        index = self._selected_index()
        if index is None:
            return
        value = self._form(self._context["working"][index])
        self._context["window"].grab_set()
        if value is None:
            return
        self._context["working"][index] = value
        self._refresh(index)

    def _form(self, initial=None):
        owner = self._context["owner"]
        window = self._context["window"]
        if self._context["type"] == "animation":
            return owner._animation_form(window, initial)
        return owner._event_form(window, initial)

    def _duplicate(self):
        index = self._selected_index()
        if index is None:
            return
        duplicate = copy.deepcopy(self._context["working"][index])
        self._context["working"].insert(index + 1, duplicate)
        self._refresh(index + 1)

    def _delete(self):
        index = self._selected_index()
        if index is None:
            return
        del self._context["working"][index]
        self._refresh(max(0, index - 1))

    def _apply(self):
        item = self._context["item"]
        field = self._configuration(self._context["type"])["field"]
        if self._context["working"]:
            item[field] = self._context["working"]
        if not self._context["working"]:
            item.pop(field, None)
        owner = self._context["owner"]
        owner._mark_dirty()
        owner._reset_preview_state()
        owner._refresh_all(select=item)
        self._context["window"].destroy()
