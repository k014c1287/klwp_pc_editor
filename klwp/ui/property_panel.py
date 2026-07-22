"""Build the selected module's property controls."""

from ..shared import *  # noqa: F401,F403
from .color_control import ColorControl


class AnchorChoices:
    """Translate user-facing anchor names to KLWP anchor identifiers."""

    VALUES = (
        ("左上", "TOPLEFT"),
        ("上", "TOP"),
        ("右上", "TOPRIGHT"),
        ("左中央", "CENTERLEFT"),
        ("中央", "CENTER"),
        ("右中央", "CENTERRIGHT"),
        ("左下", "BOTTOMLEFT"),
        ("下", "BOTTOM"),
        ("右下", "BOTTOMRIGHT"),
    )

    @staticmethod
    def display_values():
        return tuple(label for label, _value in AnchorChoices.VALUES)

    @staticmethod
    def to_display(internal_value):
        pairs = map(AnchorChoices._reversed_pair, AnchorChoices.VALUES)
        labels = dict(pairs)
        text = str(internal_value or DEFAULT_ANCHOR)
        normalized = text.upper()
        return labels.get(normalized, "上")

    @staticmethod
    def _reversed_pair(choice):
        label, value = choice
        return value, label

    @staticmethod
    def to_internal(display_value):
        values = dict(AnchorChoices.VALUES)
        return values.get(display_value, DEFAULT_ANCHOR)


class PropertyPanelBuilder:
    def __init__(self, owner, item):
        self._owner = owner
        self._item = item

    def build(self):
        self._clear()
        if self._item is None:
            self._empty_message()
            return
        self._heading()
        self._property_fields()
        self._text_editor()
        self._image_button()
        self._interaction_buttons()
        self._json_button()

    def _clear(self):
        owner = self._owner
        memory = owner.memory
        frame = memory['prop_frame']
        for widget in frame.winfo_children():
            widget.destroy()

    def _empty_message(self):
        owner = self._owner
        memory = owner.memory
        ttk.Label(
            memory['prop_frame'],
            text="左のツリーまたはプレビューから\n要素を選択してください"
        ).pack(pady=20)

    def _heading(self):
        owner = self._owner
        item = self._item
        memory = owner.memory
        ttk.Label(
            memory['prop_frame'], text=module_label(item),
            font=("", 11, "bold")).pack(anchor="w", pady=(0, 6))

    def _property_fields(self):
        owner = self._owner
        memory = owner.memory
        memory['_prop_vars'] = {}
        memory['_prop_color_controls'] = {}
        grid = ttk.Frame(memory['prop_frame'])
        grid.pack(fill="x")
        row = 0
        for key, label in owner.PROP_FIELDS:
            row += self._property_field(grid, row, key, label)
        grid.columnconfigure(1, weight=1)

    def _property_field(self, grid, row, key, label):
        owner = self._owner
        item = self._item
        always_visible = (
            "internal_title", "position_anchor",
            "position_offset_x", "position_offset_y")
        if key not in item and key not in always_visible:
            return 0
        ttk.Label(grid, text=label).grid(
            row=row, column=0, sticky="w", pady=2)
        builders = {
            "position_anchor": self._anchor_field,
            "paint_color": self._color_field,
        }
        builder = builders.get(key, self._entry_field)
        builder(grid, row, key)
        return 1

    def _entry_field(self, grid, row, key):
        owner = self._owner
        item = self._item
        memory = owner.memory
        variable = tk.StringVar(value=str(item.get(key, "")))
        entry = ttk.Entry(grid, textvariable=variable, width=24)
        entry.grid(row=row, column=1, sticky="ew", pady=2)
        callback = self._property_callback(key, variable)
        entry.bind("<Return>", callback)
        entry.bind("<FocusOut>", callback)
        memory['_prop_vars'][key] = variable

    def _anchor_field(self, grid, row, key):
        owner = self._owner
        item = self._item
        memory = owner.memory
        internal_value = item.get(key) or DEFAULT_ANCHOR
        display_value = AnchorChoices.to_display(internal_value)
        variable = tk.StringVar(value=display_value)
        choices = AnchorChoices.display_values()
        selector = ttk.Combobox(
            grid, textvariable=variable, values=choices,
            state="readonly", width=22)
        selector.grid(row=row, column=1, sticky="ew", pady=2)
        selector.bind(
            "<<ComboboxSelected>>", self._property_callback(key, variable))
        memory['_prop_vars'][key] = variable

    def _color_field(self, grid, row, key):
        owner = self._owner
        item = self._item
        memory = owner.memory
        callback = lambda value: owner._apply_property_value(key, value)
        control = ColorControl(grid, item.get(key, "#FFFFFFFF"), callback)
        frame = control.build()
        frame.grid(row=row, column=1, sticky="ew", pady=2)
        memory['_prop_color_controls'][key] = control

    def _property_callback(self, key, variable):
        owner = self._owner
        return lambda _event: owner._apply_prop(key, variable)

    def _text_editor(self):
        owner = self._owner
        item = self._item
        memory = owner.memory
        if item.get("internal_type") != "TextModule":
            return
        frame = memory['prop_frame']
        ttk.Label(frame, text="テキスト / 数式 ($...$):").pack(
            anchor="w", pady=(8, 2))
        text = tk.Text(frame, height=6, wrap="word", font=("Consolas", 10))
        text.insert("1.0", item.get("text_expression", ""))
        text.pack(fill="both", expand=False)
        callback = lambda _event=None: self._apply_text(text)
        text.bind("<FocusOut>", callback)
        ttk.Button(frame, text="数式を適用", command=callback).pack(
            anchor="e", pady=4)

    def _apply_text(self, text):
        owner = self._owner
        item = self._item
        item["text_expression"] = text.get("1.0", "end-1c")
        owner._mark_dirty()
        owner._render()
        owner._rebuild_tree(select=item)

    def _image_button(self):
        owner = self._owner
        memory = owner.memory
        ttk.Button(
            memory['prop_frame'],
            text="この要素に画像を割り当て",
            command=self._set_image).pack(fill="x", pady=(10, 2))

    def _set_image(self):
        owner = self._owner
        item = self._item
        memory = owner.memory
        path = filedialog.askopenfilename(filetypes=[
            ("画像", "*.png *.jpg *.jpeg *.webp"), ("All", "*.*")])
        if not path:
            return
        archive = memory['archive']
        reference = archive.add_bitmap(path)
        handlers = {
            "ShapeModule": self._set_shape_image,
            "BitmapModule": self._set_bitmap_image,
        }
        handler = handlers.get(
            item.get("internal_type"), self._set_style_image)
        handler(reference)
        owner._mark_dirty()
        owner._render()

    def _set_shape_image(self, reference):
        self._item["fx_gradient"] = "BITMAP"
        self._item["fx_gradient_bitmap"] = reference

    def _set_bitmap_image(self, reference):
        self._item["bitmap_bitmap"] = reference

    def _set_style_image(self, reference):
        self._item["style_bitmap"] = reference

    def _interaction_buttons(self):
        owner = self._owner
        item = self._item
        memory = owner.memory
        frame = ttk.LabelFrame(
            memory['prop_frame'],
            text="アニメーション・タップ", padding=6)
        frame.pack(fill="x", pady=(10, 4))
        animation_count = len(item.get("internal_animations", []) or [])
        event_count = len(item.get("internal_events", []) or [])
        ttk.Label(
            frame, text=f"アニメーション {animation_count}件 / タップ {event_count}件"
        ).pack(anchor="w", pady=(0, 4))
        self._interaction_button(frame, "アニメーション設定", owner._edit_animations)
        self._interaction_button(frame, "タップイベント設定", owner._edit_tap_events)
        self._interaction_button(frame, "グローバル変数管理", owner._edit_globals)
        if "globals_list" in item:
            self._interaction_button(
                frame, "この要素のローカルGlobal管理",
                owner._edit_local_globals)

    @staticmethod
    def _interaction_button(frame, label, command):
        ttk.Button(frame, text=label, command=command).pack(
            fill="x", pady=2)

    def _json_button(self):
        owner = self._owner
        memory = owner.memory
        ttk.Button(
            memory['prop_frame'], text="詳細 (JSON を直接編集)",
            command=owner._edit_json).pack(fill="x", pady=2)


class JsonEditorDialog:
    def __init__(self, owner, item):
        self._context = {"owner": owner, "item": item}

    def show(self):
        owner = self._context["owner"]
        window = tk.Toplevel(owner)
        window.title("JSON 直接編集")
        window.geometry("620x520")
        window.grab_set()
        text = tk.Text(window, wrap="none", font=("Consolas", 10))
        text.pack(fill="both", expand=True)
        text.insert("1.0", json.dumps(
            self._context["item"], ensure_ascii=False, indent=2))
        self._context["window"] = window
        self._context["text"] = text
        ttk.Button(window, text="適用", command=self._apply).pack(pady=4)

    def _apply(self):
        text = self._context["text"].get("1.0", "end-1c")
        try:
            updated = json.loads(text)
        except Exception as error:
            messagebox.showerror(
                APP_TITLE, f"JSON エラー:\n{error}",
                parent=self._context["window"])
            return
        item = self._context["item"]
        item.clear()
        item.update(updated)
        owner = self._context["owner"]
        owner._mark_dirty()
        owner._refresh_all(select=item)
        self._context["window"].destroy()
