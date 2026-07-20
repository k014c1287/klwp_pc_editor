"""Dialog used to create one of the supported KLWP shape modules."""

from ..shared import *  # noqa: F401,F403


class ShapeDialog:
    INVALID = object()

    def __init__(self, owner):
        self._owner = owner
        self._widgets = ApplicationMemory()

    def show(self):
        window = tk.Toplevel(self._owner)
        window.title("図形を追加")
        window.geometry("440x430")
        window.transient(self._owner)
        window.grab_set()
        self._widgets['window'] = window
        form = ttk.Frame(window, padding=12)
        form.pack(fill="both", expand=True)
        self._shape_selector(form)
        self._numeric_fields(form)
        self._path_field(form)
        self._buttons(form)
        self._load_defaults()

    def _shape_selector(self, form):
        ttk.Label(form, text="図形種別").grid(
            row=0, column=0, sticky="w", pady=4)
        variable = tk.StringVar(value="長方形")
        selector = ttk.Combobox(
            form, textvariable=variable, values=SHAPE_TYPE_OPTIONS,
            state="readonly", width=24)
        selector.grid(row=0, column=1, sticky="ew", pady=4)
        selector.bind("<<ComboboxSelected>>", self._load_defaults)
        self._widgets['shape_variable'] = variable

    def _numeric_fields(self, form):
        fields = {}
        specifications = (
            ("shape_width", "幅"), ("shape_height", "高さ"),
            ("shape_corners", "角丸"),
            ("shape_offset", "扇形・弧の角度"),
        )
        for row, specification in enumerate(specifications, start=1):
            self._numeric_field(form, fields, row, specification)
        self._widgets['fields'] = fields

    @staticmethod
    def _numeric_field(form, fields, row, specification):
        key, label = specification
        ttk.Label(form, text=label).grid(
            row=row, column=0, sticky="w", pady=4)
        variable = tk.StringVar()
        ttk.Entry(form, textvariable=variable).grid(
            row=row, column=1, sticky="ew", pady=4)
        fields[key] = variable

    def _path_field(self, form):
        ttk.Label(form, text="Path（100×100 SVG座標）").grid(
            row=5, column=0, columnspan=2, sticky="w", pady=(10, 2))
        text = tk.Text(form, height=7, wrap="word", font=("Consolas", 9))
        text.grid(row=6, column=0, columnspan=2, sticky="nsew", pady=(0, 6))
        form.columnconfigure(1, weight=1)
        form.rowconfigure(6, weight=1)
        self._widgets['path_text'] = text

    def _buttons(self, form):
        buttons = ttk.Frame(form)
        buttons.grid(row=7, column=0, columnspan=2, sticky="e", pady=(8, 0))
        window = self._widgets['window']
        ttk.Button(buttons, text="キャンセル", command=window.destroy).pack(
            side="left", padx=4)
        ttk.Button(buttons, text="追加", command=self._add).pack(
            side="left", padx=4)

    def _load_defaults(self, _event=None):
        shape_name = self._widgets['shape_variable'].get()
        specification = SHAPE_TYPE_SPECS[shape_name]
        for key, variable in self._widgets['fields'].items():
            variable.set(str(specification.get(key, 0.0)))
        text = self._widgets['path_text']
        text.delete("1.0", "end")
        text.insert("1.0", specification.get("shape_path", ""))

    def _add(self):
        shape_name = self._widgets['shape_variable'].get()
        item = make_shape_module(shape_name)
        valid = all(
            self._apply_numeric_field(item, key, variable)
            for key, variable in self._widgets['fields'].items())
        if not valid or not self._apply_path(item):
            return
        owner = self._owner
        memory = owner.memory
        target = owner._target_list()
        target.append(item)
        memory['selected'] = item
        owner._mark_dirty()
        owner._refresh_all(select=item)
        self._widgets['window'].destroy()

    def _apply_numeric_field(self, item, key, variable):
        value = self._number(key, variable)
        if value is self.INVALID:
            return False
        if key in ("shape_width", "shape_height") and value <= 0:
            self._error("幅と高さは0より大きくしてください。")
            return False
        if key in item or value:
            item[key] = value
        return True

    def _number(self, key, variable):
        try:
            return float(variable.get())
        except ValueError:
            self._error(f"{key} は数値で指定してください。")
            return self.INVALID

    def _apply_path(self, item):
        if item.get("shape_type") != "PATH":
            return True
        path = self._widgets['path_text'].get("1.0", "end-1c").strip()
        if not path:
            self._error("Pathデータを入力してください。")
            return False
        item["shape_path"] = path
        return True

    def _error(self, message):
        messagebox.showerror(
            APP_TITLE, message, parent=self._widgets['window'])
