"""Background and bitmap-management dialogs."""

from ..shared import *  # noqa: F401,F403
from ..background import BackgroundImageBinding, BitmapGlobalCollection


class BackgroundDialog:
    def __init__(self, owner):
        self._owner = owner
        self._widgets = ApplicationMemory()

    def show(self):
        owner = self._owner
        memory = owner.memory
        archive = memory['archive']
        root_module = archive.root_module()
        self._widgets['root'] = root_module
        self._widgets['binding'] = BackgroundImageBinding(root_module)
        self._widgets['globals'] = BitmapGlobalCollection(root_module)
        window = tk.Toplevel(self._owner)
        window.title("背景設定")
        window.geometry("620x470")
        window.grab_set()
        self._widgets['window'] = window
        mode = tk.StringVar(
            value=root_module.get("background_type", "SOLID"))
        self._widgets['mode'] = mode
        self._radio_buttons(window, mode)
        self._dynamic_image_fields(window)
        self._buttons(window)

    @staticmethod
    def _radio_buttons(window, mode):
        ttk.Radiobutton(
            window, text="単色", variable=mode, value="SOLID").pack(
                anchor="w", padx=10, pady=2)
        ttk.Radiobutton(
            window, text="画像", variable=mode, value="IMAGE").pack(
                anchor="w", padx=10, pady=2)

    def _buttons(self, window):
        ttk.Button(window, text="色を選ぶ", command=self._pick_color).pack(
            fill="x", padx=10, pady=4)
        ttk.Button(
            window, text="固定画像ファイルを選ぶ", command=self._pick_image).pack(
                fill="x", padx=10, pady=4)
        ttk.Button(
            window, text="適用して閉じる", command=self._apply).pack(
            fill="x", padx=10, pady=8)

    def _dynamic_image_fields(self, window):
        frame = ttk.LabelFrame(window, text="Global・数式による背景画像", padding=8)
        frame.pack(fill="both", expand=True, padx=10, pady=8)
        binding = self._widgets['binding']
        formula, global_name = binding.form_values()
        self._global_selector(frame, global_name)
        ttk.Label(frame, text="背景画像の数式").pack(anchor="w", pady=(8, 2))
        text = tk.Text(frame, height=7, wrap="word", font=("Consolas", 9))
        text.insert("1.0", formula)
        text.pack(fill="both", expand=True)
        self._widgets['formula'] = text
        ttk.Label(
            frame,
            text="例: $if(df(H)>19, gv(night), gv(day))$\n"
                 "日時の確認はツールバーの「プレビュー値」から変更できます。",
            foreground="#666").pack(anchor="w", pady=(5, 0))

    def _global_selector(self, frame, global_name):
        ttk.Label(frame, text="背景画像Global（数式未指定時、または式の予備値）").pack(
            anchor="w")
        collection = self._widgets['globals']
        choices = self._global_choices(collection.names(), global_name)
        variable = tk.StringVar(value=global_name)
        selector = ttk.Combobox(
            frame, textvariable=variable, values=choices, state="readonly")
        selector.pack(fill="x", pady=3)
        self._widgets['global_variable'] = variable
        self._widgets['global_selector'] = selector
        ttk.Button(
            frame, text="画像ファイルを背景用Globalとして追加",
            command=self._pick_global_image).pack(fill="x", pady=3)

    @staticmethod
    def _global_choices(names, current):
        values = tuple(names)
        if current and current not in values:
            values += (current,)
        return ("",) + values

    def _pick_color(self):
        color = colorchooser.askcolor(parent=self._widgets['window'])[1]
        if not color:
            return
        self._widgets['root']["background_color"] = "#FF" + color[1:].upper()
        self._widgets['mode'].set("SOLID")
        self._apply()

    def _pick_image(self):
        path = filedialog.askopenfilename(
            parent=self._widgets['window'],
            filetypes=[("画像", "*.png *.jpg *.jpeg *.webp"), ("All", "*.*")])
        if not path:
            return
        owner = self._owner
        memory = owner.memory
        archive = memory['archive']
        self._widgets['root']["background_bitmap"] = archive.add_bitmap(path)
        self._widgets['root']["background_type"] = "IMAGE"
        self._widgets['mode'].set("IMAGE")
        self._clear_dynamic_binding()
        self._apply()

    def _pick_global_image(self):
        path = filedialog.askopenfilename(
            parent=self._widgets['window'],
            filetypes=[("画像", "*.png *.jpg *.jpeg *.webp"), ("All", "*.*")])
        if not path:
            return
        name = simpledialog.askstring(
            APP_TITLE, "Globalの識別名:", parent=self._widgets['window'])
        if not self._valid_global_name(name):
            self._error("識別名には空白・$・括弧・カンマを使用できません。")
            return
        collection = self._widgets['globals']
        if collection.contains(name):
            self._error("同じ識別名が既にあります。")
            return
        self._add_global_image(collection, name, path)

    def _add_global_image(self, collection, name, path):
        owner = self._owner
        memory = owner.memory
        archive = memory['archive']
        reference = archive.add_bitmap(path)
        collection.add(name, reference)
        choices = self._global_choices(collection.names(), name)
        self._widgets['global_selector'].configure(values=choices)
        self._widgets['global_variable'].set(name)
        self._widgets['mode'].set("IMAGE")
        owner._mark_dirty()

    def _clear_dynamic_binding(self):
        self._widgets['global_variable'].set("")
        text = self._widgets['formula']
        text.delete("1.0", "end")

    @staticmethod
    def _valid_global_name(name):
        return bool(name) and re.search(r"[\s$(),]", name) is None

    def _apply(self):
        widgets = self._widgets
        widgets['root']["background_type"] = widgets['mode'].get()
        formula = widgets['formula'].get("1.0", "end-1c").strip()
        global_name = widgets['global_variable'].get().strip()
        widgets['binding'].apply(formula, global_name)
        owner = self._owner
        memory = owner.memory
        owner._mark_dirty()
        memory['photo_cache'].clear()
        owner._render()
        widgets['window'].destroy()

    def _error(self, message):
        messagebox.showerror(
            APP_TITLE, message, parent=self._widgets['window'])


class ImageManagerDialog:
    def __init__(self, owner):
        self._owner = owner
        self._widgets = ApplicationMemory()

    def show(self):
        window = tk.Toplevel(self._owner)
        window.title("画像管理")
        window.geometry("560x420")
        window.grab_set()
        self._widgets['window'] = window
        self._image_list(window)
        self._preview_panel(window)

    def _image_list(self, window):
        listbox = tk.Listbox(window)
        listbox.pack(side="left", fill="both", expand=True, padx=6, pady=6)
        owner = self._owner
        memory = owner.memory
        archive = memory['archive']
        names = sorted(archive["bitmaps"].keys())
        self._widgets['names'] = names
        self._widgets['listbox'] = listbox
        references = archive.bitmap_refs()
        for name in names:
            self._insert_image(listbox, archive, references, name)
        listbox.bind("<<ListboxSelect>>", self._show_preview)

    @staticmethod
    def _insert_image(listbox, archive, references, name):
        reference = KFILE_PREFIX + name.split("/", 1)[1]
        marker = "●" if reference in references else "○"
        size_kilobytes = len(archive["bitmaps"][name]) // 1024
        listbox.insert("end", f"{marker} {name}  ({size_kilobytes} KB)")

    def _preview_panel(self, window):
        panel = ttk.Frame(window)
        panel.pack(side="right", fill="y", padx=6, pady=6)
        preview = ttk.Label(panel)
        preview.pack(pady=4)
        self._widgets['preview'] = preview
        ttk.Button(
            panel, text="選択画像を差し替え", command=self._replace).pack(
                fill="x", pady=4)
        ttk.Label(
            panel, text="● = 使用中 / ○ = 未参照",
            foreground="#666").pack(pady=8)

    def _current_name(self):
        selection = self._widgets['listbox'].curselection()
        if not selection:
            return None
        return self._widgets['names'][selection[0]]

    def _show_preview(self, _event=None):
        name = self._current_name()
        if not name or not HAS_PIL:
            return
        try:
            self._load_preview(name)
        except Exception:
            self._widgets['preview'].configure(
                image="", text="(プレビュー不可)")

    def _load_preview(self, name):
        owner = self._owner
        memory = owner.memory
        archive = memory['archive']
        stream = io.BytesIO(archive["bitmaps"][name])
        image = Image.open(stream)
        image.thumbnail((220, 220))
        photo = ImageTk.PhotoImage(image)
        preview = self._widgets['preview']
        preview.configure(image=photo)
        preview.image = photo

    def _replace(self):
        name = self._current_name()
        if not name:
            return
        path = filedialog.askopenfilename(
            parent=self._widgets['window'],
            filetypes=[("画像", "*.png *.jpg *.jpeg *.webp"), ("All", "*.*")])
        if not path:
            return
        owner = self._owner
        memory = owner.memory
        archive = memory['archive']
        archive.replace_bitmap(name, path)
        owner._mark_dirty()
        memory['photo_cache'].clear()
        self._show_preview()
        owner._render()
