"""Build the main menu and the compact primary toolbar."""

from ..shared import *  # noqa: F401,F403


class EditorCommandCatalog:
    def __init__(self, owner):
        self._owner = owner

    def menu_groups(self):
        return (
            ("ファイル", self._file_items()),
            ("編集", self._edit_items()),
            ("追加", self._add_items()),
            ("配置", self._arrange_items()),
            ("プロジェクト", self._project_items()),
            ("デバイス", self._device_items()),
        )

    def toolbar_items(self):
        owner = self._owner
        return (
            ("button", "新規", owner.cmd_new),
            ("button", "開く", owner.cmd_open),
            ("button", "保存", owner.cmd_save),
            ("separator", "", None),
            ("button", "元に戻す", owner.cmd_undo),
            ("button", "やり直す", owner.cmd_redo),
            ("separator", "", None),
            ("menu", "＋追加", self._add_items()),
            ("separator", "", None),
            ("button", "コピー", owner.cmd_copy),
            ("button", "貼付", owner.cmd_paste),
            ("button", "複製", owner.cmd_duplicate),
            ("button", "削除", owner.cmd_delete),
            ("separator", "", None),
            ("button", "Androidへ転送", owner.cmd_adb_transfer),
        )

    def _file_items(self):
        owner = self._owner
        return (
            ("新規", owner.cmd_new, ""),
            ("開く", owner.cmd_open, ""),
            (None, None, ""),
            ("保存", owner.cmd_save, ""),
            ("名前を付けて保存", owner.cmd_save_as, ""),
        )

    def _edit_items(self):
        owner = self._owner
        return (
            ("元に戻す", owner.cmd_undo, "Ctrl+Z"),
            ("やり直す", owner.cmd_redo, "Ctrl+Y"),
            (None, None, ""),
            ("コピー", owner.cmd_copy, "Ctrl+C"),
            ("貼付", owner.cmd_paste, "Ctrl+V"),
            ("複製", owner.cmd_duplicate, ""),
            ("削除", owner.cmd_delete, "Delete"),
        )

    def _add_items(self):
        owner = self._owner
        return (
            ("テキスト", lambda: owner.cmd_add("text"), ""),
            ("図形", owner.cmd_add_shape, ""),
            ("アイコン", lambda: owner.cmd_add("icon"), ""),
            ("画像", lambda: owner.cmd_add("bitmap"), ""),
            ("レイヤー", lambda: owner.cmd_add("layer"), ""),
        )

    def _arrange_items(self):
        owner = self._owner
        return (
            ("グループ化", owner.cmd_group_selection, ""),
            ("グループ解除", owner.cmd_ungroup_selection, ""),
            (None, None, ""),
            ("背面へ", lambda: owner.cmd_move(-1), ""),
            ("前面へ", lambda: owner.cmd_move(1), ""),
        )

    def _project_items(self):
        owner = self._owner
        return (
            ("グローバル管理", owner._edit_globals, ""),
            ("プレビュー値", owner._edit_preview_values, ""),
            (None, None, ""),
            ("背景設定", owner.cmd_background, ""),
            ("画像管理", owner.cmd_images, ""),
            ("端末解像度", owner.cmd_device_res, ""),
        )

    def _device_items(self):
        owner = self._owner
        return (("Androidへ転送", owner.cmd_adb_transfer, ""),)


class EditorMenuBuilder:
    def __init__(self, owner):
        self._owner = owner

    def build(self):
        owner = self._owner
        menu_bar = tk.Menu(owner)
        catalog = EditorCommandCatalog(owner)
        for label, entries in catalog.menu_groups():
            self._cascade(menu_bar, label, entries)
        owner.configure(menu=menu_bar)
        owner.memory["menu_bar"] = menu_bar

    def _cascade(self, menu_bar, label, entries):
        menu = tk.Menu(menu_bar, tearoff=False)
        for entry in entries:
            self._entry(menu, entry)
        menu_bar.add_cascade(label=label, menu=menu)

    @staticmethod
    def _entry(menu, entry):
        label, command, accelerator = entry
        if label is None:
            menu.add_separator()
            return
        options = {"label": label, "command": command}
        if accelerator:
            options["accelerator"] = accelerator
        menu.add_command(**options)


class PrimaryToolbarBuilder:
    def __init__(self, owner):
        self._owner = owner

    def build(self):
        owner = self._owner
        toolbar = ttk.Frame(owner)
        toolbar.pack(side="top", fill="x", padx=6, pady=4)
        catalog = EditorCommandCatalog(owner)
        for item in catalog.toolbar_items():
            self._item(toolbar, item)
        owner.memory["primary_toolbar"] = toolbar

    def _item(self, toolbar, item):
        kind, label, action = item
        if kind == "separator":
            self._separator(toolbar)
            return
        if kind == "menu":
            self._menu_button(toolbar, label, action)
            return
        self._button(toolbar, label, action)

    @staticmethod
    def _separator(toolbar):
        separator = ttk.Separator(toolbar, orient="vertical")
        separator.pack(side="left", fill="y", padx=6)

    def _button(self, toolbar, label, command):
        button = ttk.Button(toolbar, text=label, command=command)
        button.pack(side="left", padx=2)
        self._remember_history_button(label, button)

    def _menu_button(self, toolbar, label, entries):
        button = ttk.Menubutton(toolbar, text=f"{label} ▼")
        menu = tk.Menu(button, tearoff=False)
        for entry in entries:
            EditorMenuBuilder._entry(menu, entry)
        button.configure(menu=menu)
        button.pack(side="left", padx=2)

    def _remember_history_button(self, label, button):
        owner = self._owner
        memory = owner.memory
        if label == "元に戻す":
            memory["undo_button"] = button
            return
        if label == "やり直す":
            memory["redo_button"] = button
