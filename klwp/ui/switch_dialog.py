"""Manage SWITCH entries in the root KLWP global collection."""

from ..shared import *  # noqa: F401,F403


class SwitchManagerDialog:
    def __init__(self, owner):
        archive = owner.memory['archive']
        root_module = archive.root_module()
        existing = root_module.get("globals_list", {})
        working = copy.deepcopy(existing) if isinstance(existing, dict) else {}
        self._context = {
            "owner": owner, "root": root_module, "working": working,
        }

    def show(self):
        self._window()
        self._listbox()
        self._controls()
        self._bottom_buttons()
        self._refresh()

    def _window(self):
        owner = self._context["owner"]
        window = tk.Toplevel(owner)
        window.title("Switchグローバル管理")
        window.geometry("520x380")
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
        controls = ttk.Frame(self._context["frame"])
        controls.pack(fill="x", pady=6)
        commands = (
            ("追加", self._add), ("表示名編集", self._edit_title),
            ("初期ON/OFF", self._toggle), ("削除", self._delete),
        )
        for label, command in commands:
            ttk.Button(controls, text=label, command=command).pack(
                side="left", padx=2)

    def _bottom_buttons(self):
        bottom = ttk.Frame(self._context["frame"])
        bottom.pack(fill="x", pady=(6, 0))
        window = self._context["window"]
        ttk.Button(bottom, text="キャンセル", command=window.destroy).pack(
            side="right", padx=4)
        ttk.Button(bottom, text="適用", command=self._apply).pack(
            side="right", padx=4)

    def _names(self):
        return self._context["owner"]._switch_global_names(
            self._context["working"])

    def _refresh(self, selected=None):
        names = self._names()
        listbox = self._context["listbox"]
        listbox.delete(0, "end")
        for name in names:
            self._insert_switch(listbox, name)
        if names:
            index = min(len(names) - 1, self._selection_default(selected))
            listbox.selection_set(index)

    @staticmethod
    def _selection_default(selected):
        if selected is None:
            return 0
        return selected

    def _insert_switch(self, listbox, name):
        entry = self._context["working"][name]
        enabled = self._context["owner"]._preview_bool(entry.get("value"))
        state = "OFF"
        if enabled:
            state = "ON"
        title = entry.get("title") or name
        listbox.insert("end", f"{name}  [{state}]  {title}")

    def _selected(self):
        selection = self._context["listbox"].curselection()
        if not selection:
            return None
        return self._names()[selection[0]]

    def _add(self):
        window = self._context["window"]
        name = simpledialog.askstring(
            APP_TITLE, "Switch識別名（空白・$・括弧・カンマは不可）:",
            parent=window)
        if not name:
            return
        name = name.strip()
        if re.search(r"[\s$(),]", name):
            self._error("Switch識別名に使用できない文字があります。")
            return
        if name in self._context["working"]:
            self._error("同じ識別名が既にあります。")
            return
        self._context["working"][name] = self._new_switch(name)
        self._refresh(self._names().index(name))

    def _new_switch(self, name):
        indices = [
            int(entry.get("index", 0) or 0)
            for entry in self._context["working"].values()
            if isinstance(entry, dict)
        ]
        return {
            "index": max(indices or [0]) + 1,
            "type": "SWITCH", "title": name,
            "description": "", "global_formula": "", "value": 0,
        }

    def _edit_title(self):
        name = self._selected()
        if not name:
            return
        working = self._context["working"]
        title = simpledialog.askstring(
            APP_TITLE, "表示名:",
            initialvalue=str(working[name].get("title", name)),
            parent=self._context["window"])
        if title is None:
            return
        working[name]["title"] = title
        self._refresh(self._names().index(name))

    def _toggle(self):
        name = self._selected()
        if not name:
            return
        working = self._context["working"]
        enabled = self._context["owner"]._preview_bool(
            working[name].get("value"))
        working[name]["value"] = int(not enabled)
        self._refresh(self._names().index(name))

    def _delete(self):
        name = self._selected()
        if not name:
            return
        references = self._context["owner"]._switch_reference_count(name)
        if references:
            self._error(
                f"「{name}」は{references}箇所から参照されています。\n"
                "先にアニメーション・タップ・数式の参照を外してください。")
            return
        del self._context["working"][name]
        self._refresh()

    def _apply(self):
        self._context["root"]["globals_list"] = self._context["working"]
        owner = self._context["owner"]
        owner._mark_dirty()
        owner._reset_preview_state()
        owner._refresh_all(select=owner.memory['selected'])
        self._context["window"].destroy()

    def _error(self, message):
        messagebox.showerror(
            APP_TITLE, message, parent=self._context["window"])
