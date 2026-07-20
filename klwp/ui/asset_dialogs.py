"""Background and bitmap-management dialogs."""

from ..shared import *  # noqa: F401,F403


class BackgroundDialog:
    def __init__(self, owner):
        self._owner = owner
        self._widgets = ApplicationMemory()

    def show(self):
        owner = self._owner
        memory = owner.memory
        archive = memory['archive']
        self._widgets['root'] = archive.root_module()
        window = tk.Toplevel(self._owner)
        window.title("背景設定")
        window.grab_set()
        self._widgets['window'] = window
        mode = tk.StringVar(
            value=self._widgets['root'].get("background_type", "SOLID"))
        self._widgets['mode'] = mode
        self._radio_buttons(window, mode)
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
            window, text="画像ファイルを選ぶ", command=self._pick_image).pack(
                fill="x", padx=10, pady=4)
        ttk.Button(
            window, text="適用して閉じる", command=self._apply).pack(
                fill="x", padx=10, pady=8)

    def _pick_color(self):
        color = colorchooser.askcolor(parent=self._widgets['window'])[1]
        if not color:
            return
        self._widgets['root']["background_color"] = "#FF" + color[1:].upper()
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
        self._apply()

    def _apply(self):
        self._widgets['root']["background_type"] = self._widgets['mode'].get()
        owner = self._owner
        memory = owner.memory
        owner._mark_dirty()
        memory['photo_cache'].clear()
        owner._render()
        self._widgets['window'].destroy()


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
