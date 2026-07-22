"""Edit all KLWP global variable types without discarding unknown fields."""

from ..shared import *  # noqa: F401,F403
from .color_control import KlwpColor


GLOBAL_TYPES = ("TEXT", "NUMBER", "COLOR", "SWITCH", "BITMAP", "FONT")


class GlobalEntryValues:
    @staticmethod
    def create(name, global_type, value, index):
        return {
            "index": index, "type": global_type, "title": name,
            "description": "", "global_formula": "",
            "value": GlobalEntryValues.convert(global_type, value),
        }

    @staticmethod
    def update(entry, global_type, title, value, formula):
        updated = copy.deepcopy(entry)
        updated["type"] = global_type
        updated["title"] = title
        updated["global_formula"] = formula
        updated["value"] = GlobalEntryValues.convert(global_type, value)
        return updated

    @staticmethod
    def convert(global_type, value):
        if global_type == "NUMBER":
            return float(value)
        if global_type == "SWITCH":
            normalized = str(value).strip().lower()
            return int(normalized not in ("", "0", "false", "off", "no"))
        if global_type == "COLOR":
            return KlwpColor(value).encoded()
        return str(value)


class GlobalEntryDialog:
    INVALID = object()

    def __init__(self, parent, name, entry, new_entry=False):
        self._context = {
            "parent": parent, "name": name, "entry": copy.deepcopy(entry),
            "new": new_entry, "result": None, "variables": {},
        }

    def show(self):
        self._window()
        self._variables()
        self._fields()
        self._buttons()
        window = self._context["window"]
        window.wait_window()
        return self._context["result"]

    def _window(self):
        parent = self._context["parent"]
        window = tk.Toplevel(parent)
        window.title("グローバル変数")
        window.geometry("460x300")
        window.transient(parent)
        window.grab_set()
        frame = ttk.Frame(window, padding=12)
        frame.pack(fill="both", expand=True)
        context = self._context
        context["window"] = window
        context["frame"] = frame

    def _variables(self):
        entry = self._context["entry"]
        values = {
            "name": self._context["name"],
            "type": entry.get("type", "TEXT"),
            "title": entry.get("title", self._context["name"]),
            "value": entry.get("value", ""),
            "formula": entry.get("global_formula", ""),
        }
        variables = {name: tk.StringVar(value=str(value))
                     for name, value in values.items()}
        self._context["variables"] = variables

    def _fields(self):
        specifications = (
            ("name", "識別名"), ("type", "型"), ("title", "表示名"),
            ("value", "値"), ("formula", "式"),
        )
        frame = self._context["frame"]
        for row, specification in enumerate(specifications):
            self._field(frame, row, specification)
        frame.columnconfigure(1, weight=1)

    def _field(self, frame, row, specification):
        name, label = specification
        ttk.Label(frame, text=label).grid(
            row=row, column=0, sticky="w", pady=5)
        variable = self._context["variables"][name]
        widget = ttk.Entry(frame, textvariable=variable)
        if name == "type":
            widget = ttk.Combobox(
                frame, textvariable=variable,
                values=GLOBAL_TYPES, state="readonly")
        if name == "name" and not self._context["new"]:
            widget.configure(state="disabled")
        widget.grid(row=row, column=1, sticky="ew", pady=5)

    def _buttons(self):
        frame = self._context["frame"]
        buttons = ttk.Frame(frame)
        buttons.grid(row=5, column=0, columnspan=2, sticky="e", pady=12)
        window = self._context["window"]
        ttk.Button(buttons, text="キャンセル", command=window.destroy).pack(
            side="left", padx=4)
        ttk.Button(buttons, text="OK", command=self._save).pack(
            side="left", padx=4)

    def _save(self):
        variables = self._context["variables"]
        name = variables["name"].get().strip()
        if not self._valid_name(name):
            self._error("識別名には空白・$・括弧・カンマを使用できません。")
            return
        global_type = variables["type"].get()
        entry = self._converted_entry(global_type, variables)
        if entry is self.INVALID:
            return
        self._context["result"] = name, entry
        self._context["window"].destroy()

    def _converted_entry(self, global_type, variables):
        try:
            return GlobalEntryValues.update(
                self._context["entry"], global_type,
                variables["title"].get(), variables["value"].get(),
                variables["formula"].get())
        except ValueError:
            self._error("NUMBERの値は数値で入力してください。")
            return self.INVALID

    @staticmethod
    def _valid_name(name):
        return bool(name) and re.search(r"[\s$(),]", name) is None

    def _error(self, message):
        messagebox.showerror(
            APP_TITLE, message, parent=self._context["window"])


class GlobalManagerDialog:
    def __init__(self, owner, scope):
        existing = scope.get("globals_list", {})
        working = copy.deepcopy(existing) if isinstance(existing, dict) else {}
        root_module = owner.memory["archive"].root_module()
        self._context = {
            "owner": owner, "scope": scope, "working": working,
            "root": scope is root_module,
        }

    def show(self):
        self._window()
        self._listbox()
        self._controls()
        self._buttons()
        self._refresh()

    def _window(self):
        owner = self._context["owner"]
        window = tk.Toplevel(owner)
        title = "グローバル変数管理"
        if not self._context["root"]:
            title = "ローカルGlobal管理"
        window.title(title)
        window.geometry("620x430")
        window.transient(owner)
        window.grab_set()
        frame = ttk.Frame(window, padding=10)
        frame.pack(fill="both", expand=True)
        context = self._context
        context["window"] = window
        context["frame"] = frame

    def _listbox(self):
        listbox = tk.Listbox(self._context["frame"])
        listbox.pack(fill="both", expand=True)
        self._context["listbox"] = listbox

    def _controls(self):
        controls = ttk.Frame(self._context["frame"])
        controls.pack(fill="x", pady=6)
        commands = (("追加", self._add), ("編集", self._edit), ("削除", self._delete))
        for label, command in commands:
            ttk.Button(controls, text=label, command=command).pack(
                side="left", padx=2)

    def _buttons(self):
        bottom = ttk.Frame(self._context["frame"])
        bottom.pack(fill="x", pady=(6, 0))
        window = self._context["window"]
        ttk.Button(bottom, text="キャンセル", command=window.destroy).pack(
            side="right", padx=4)
        ttk.Button(bottom, text="適用", command=self._apply).pack(
            side="right", padx=4)

    def _names(self):
        working = self._context["working"]
        return sorted(working, key=lambda name: (
            int(working[name].get("index", 0)), name))

    def _refresh(self, selected=0):
        listbox = self._context["listbox"]
        listbox.delete(0, "end")
        names = self._names()
        for name in names:
            entry = self._context["working"][name]
            listbox.insert(
                "end", f"{name}  [{entry.get('type', '?')}]  {entry.get('value', '')}")
        if names:
            listbox.selection_set(min(selected, len(names) - 1))

    def _selected(self):
        selection = self._context["listbox"].curselection()
        if not selection:
            return None
        return self._names()[selection[0]]

    def _add(self):
        working = self._context["working"]
        indices = [int(entry.get("index", 0)) for entry in working.values()]
        entry = GlobalEntryValues.create("global", "TEXT", "", max(indices or [0]) + 1)
        result = GlobalEntryDialog(
            self._context["window"], "global", entry, True).show()
        if result is None:
            return
        name, entry = result
        if name in working:
            self._error("同じ識別名が既にあります。")
            return
        working[name] = entry
        self._refresh(self._names().index(name))

    def _edit(self):
        name = self._selected()
        if name is None:
            return
        working = self._context["working"]
        result = GlobalEntryDialog(
            self._context["window"], name, working[name]).show()
        if result is None:
            return
        _same_name, entry = result
        working[name] = entry
        self._refresh(self._names().index(name))

    def _delete(self):
        name = self._selected()
        if name is None:
            return
        owner = self._context["owner"]
        if owner._switch_reference_count(name):
            self._error("この変数は要素から参照されているため削除できません。")
            return
        del self._context["working"][name]
        self._refresh()

    def _apply(self):
        self._context["scope"]["globals_list"] = self._context["working"]
        owner = self._context["owner"]
        owner._mark_dirty()
        owner._reset_preview_state()
        owner._refresh_all(select=owner.memory["selected"])
        self._context["window"].destroy()

    def _error(self, message):
        messagebox.showerror(
            APP_TITLE, message, parent=self._context["window"])
