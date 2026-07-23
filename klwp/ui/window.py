"""Construct the Tk widgets owned by the main editor window."""

from ..shared import *  # noqa: F401,F403


class EditorWindowBuilder:
    def __init__(self, owner):
        self._owner = owner

    def build(self):
        self._toolbar()
        self._keyboard_shortcuts()
        body = ttk.PanedWindow(self._owner, orient="horizontal")
        body.pack(fill="both", expand=True)
        self._module_tree(body)
        self._preview(body)
        self._property_panel(body)

    def _toolbar(self):
        toolbar = ttk.Frame(self._owner)
        toolbar.pack(side="top", fill="x", padx=4, pady=4)
        for label, command in self._toolbar_commands():
            self._toolbar_item(toolbar, label, command)

    def _toolbar_commands(self):
        owner = self._owner
        return [
            ("Androidへ転送", owner.cmd_adb_transfer),
            ("グローバル管理", owner._edit_globals),
            ("プレビュー値", owner._edit_preview_values),
            ("新規", owner.cmd_new), ("開く", owner.cmd_open),
            ("保存", owner.cmd_save), ("名前を付けて保存", owner.cmd_save_as),
            ("｜", None),
            ("元に戻す", owner.cmd_undo), ("やり直す", owner.cmd_redo),
            ("｜", None),
            ("＋テキスト", lambda: owner.cmd_add("text")),
            ("＋図形", owner.cmd_add_shape),
            ("＋アイコン", lambda: owner.cmd_add("icon")),
            ("＋画像", lambda: owner.cmd_add("bitmap")),
            ("＋レイヤー", lambda: owner.cmd_add("layer")),
            ("｜", None),
            ("複製", owner.cmd_duplicate), ("削除", owner.cmd_delete),
            ("背面へ", lambda: owner.cmd_move(-1)),
            ("前面へ", lambda: owner.cmd_move(1)),
            ("｜", None),
            ("背景設定", owner.cmd_background),
            ("画像管理", owner.cmd_images),
            ("端末解像度", owner.cmd_device_res),
        ]

    def _toolbar_item(self, toolbar, label, command):
        if command is None:
            separator = ttk.Separator(toolbar, orient="vertical")
            separator.pack(side="left", fill="y", padx=6)
            return
        button = ttk.Button(toolbar, text=label, command=command)
        button.pack(side="left", padx=2)
        self._remember_history_button(label, button)

    def _remember_history_button(self, label, button):
        owner = self._owner
        memory = owner.memory
        if label == "元に戻す":
            memory['undo_button'] = button
            return
        if label == "やり直す":
            memory['redo_button'] = button

    def _keyboard_shortcuts(self):
        owner = self._owner
        owner.bind_all("<Control-z>", owner._on_undo_shortcut)
        owner.bind_all("<Control-y>", owner._on_redo_shortcut)
        owner.bind_all("<Control-Shift-Z>", owner._on_redo_shortcut)
        owner.bind("<Escape>", owner._on_clear_selection_shortcut)

    def _module_tree(self, body):
        owner = self._owner
        frame = ttk.Frame(body)
        self._module_tree_header(frame)
        tree = ttk.Treeview(
            frame, columns=("kind", "priority"),
            show="tree headings", selectmode="browse")
        self._configure_module_tree(tree)
        tree.pack(fill="both", expand=True)
        tree.bind("<<TreeviewSelect>>", owner._on_tree_select)
        tree.bind("<ButtonPress-1>", owner._on_tree_press, add="+")
        tree.bind("<B1-Motion>", owner._on_tree_drag, add="+")
        tree.bind("<ButtonRelease-1>", owner._on_tree_release, add="+")
        owner.memory['tree'] = tree
        body.add(frame, weight=1)

    def _module_tree_header(self, frame):
        owner = self._owner
        header = ttk.Frame(frame, padding=(6, 5))
        header.pack(fill="x")
        ttk.Label(
            header, text="要素（下ほど前面）  ドラッグで順序変更"
        ).pack(side="left")
        ttk.Button(
            header, text="選択解除（ルート）",
            command=owner.cmd_clear_selection
        ).pack(side="right")

    @staticmethod
    def _configure_module_tree(tree):
        tree.heading("#0", text="要素", anchor="w")
        tree.heading("kind", text="種類", anchor="w")
        tree.heading("priority", text="前面順", anchor="center")
        tree.column("#0", width=190, minwidth=120, stretch=True)
        tree.column("kind", width=92, minwidth=72, stretch=False)
        tree.column("priority", width=62, minwidth=55, stretch=False)
        tree.tag_configure("hidden", foreground="#808080")
        tree.tag_configure(
            "drop_before", background="#dbeafe", foreground="#1d4ed8")
        tree.tag_configure(
            "drop_after", background="#dcfce7", foreground="#166534")

    def _preview(self, body):
        frame = ttk.Frame(body)
        self._canvas(frame)
        self._animation_controls(frame)
        status = ttk.Label(frame, text="")
        status.pack(fill="x", padx=8)
        owner = self._owner
        memory = owner.memory
        memory['status'] = status
        body.add(frame, weight=0)

    def _canvas(self, frame):
        owner = self._owner
        canvas = tk.Canvas(
            frame, width=owner.CANVAS_W, height=owner.CANVAS_H,
            bg="#101018", highlightthickness=0)
        canvas.pack(padx=8, pady=8)
        canvas.bind("<ButtonPress-1>", owner._on_canvas_press)
        canvas.bind("<B1-Motion>", owner._on_canvas_drag)
        canvas.bind("<ButtonRelease-1>", owner._on_canvas_release)
        canvas.bind("<Motion>", owner._on_canvas_motion)
        owner.memory['canvas'] = canvas

    def _animation_controls(self, frame):
        controls = ttk.Frame(frame)
        controls.pack(fill="x", padx=8, pady=(0, 4))
        self._interaction_toggle(controls)
        self._page_control(controls)
        self._loop_button(controls)

    def _interaction_toggle(self, controls):
        owner = self._owner
        mode = tk.BooleanVar(value=False)
        owner.memory['interaction_mode'] = mode
        toggle = ttk.Checkbutton(
            controls, text="操作プレビュー", variable=mode,
            command=owner._on_interaction_mode_changed)
        toggle.pack(side="left")

    def _page_control(self, controls):
        owner = self._owner
        ttk.Label(controls, text="ページ").pack(side="left", padx=(10, 2))
        variable = tk.DoubleVar(value=1.0)
        owner.memory['preview_page_var'] = variable
        scale = ttk.Scale(
            controls, from_=1.0, to=3.0, variable=variable,
            command=owner._on_preview_page_changed, length=150)
        scale.pack(side="left", fill="x", expand=True)
        owner.memory['preview_page_scale'] = scale
        label = ttk.Label(controls, text="1.00 / 3")
        label.pack(side="left", padx=(4, 8))
        owner.memory['preview_page_label'] = label

    def _loop_button(self, controls):
        owner = self._owner
        button = ttk.Button(
            controls, text="ループ再生", command=owner.cmd_toggle_loop,
            width=10)
        button.pack(side="left")
        owner.memory['loop_button'] = button

    def _property_panel(self, body):
        frame = ttk.Frame(body)
        property_frame = ttk.Frame(frame)
        property_frame.pack(fill="both", expand=True, padx=6, pady=6)
        owner = self._owner
        memory = owner.memory
        memory['prop_frame'] = property_frame
        body.add(frame, weight=1)
