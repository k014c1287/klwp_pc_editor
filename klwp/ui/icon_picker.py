"""Searchable grid picker for self-contained KLWP FontIcon values."""

from ..shared import (
    HAS_PIL, Image, ImageChops, ImageTk,
    decode_kustom_icon, svg_path_mask, tk, ttk,
)
from ..icons import IconCatalog


class IconPickerDialog:
    COLUMN_COUNT = 4

    def __init__(self, owner, item):
        archive = owner.memory["archive"]
        self._context = {
            "owner": owner, "item": item,
            "catalog": IconCatalog.from_archive(archive), "photos": [],
        }

    def show(self):
        self._create_window()
        self._search_controls()
        self._grid_controls()
        self._refresh_grid()

    def _create_window(self):
        context = self._context
        owner = context["owner"]
        window = tk.Toplevel(owner)
        window.title("FontIcon を選択")
        window.geometry("720x620")
        window.transient(owner)
        window.grab_set()
        frame = ttk.Frame(window, padding=10)
        frame.pack(fill="both", expand=True)
        frame.rowconfigure(1, weight=1)
        frame.columnconfigure(0, weight=1)
        context.update(window=window, frame=frame)

    def _search_controls(self):
        context = self._context
        frame = context["frame"]
        row = ttk.Frame(frame)
        row.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(row, text="検索").pack(side="left")
        variable = tk.StringVar()
        entry = ttk.Entry(row, textvariable=variable)
        entry.pack(side="left", fill="x", expand=True, padx=(8, 0))
        entry.bind("<KeyRelease>", self._refresh_grid)
        context["search_variable"] = variable

    def _grid_controls(self):
        context = self._context
        frame = context["frame"]
        canvas = tk.Canvas(frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(frame, command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=1, column=0, sticky="nsew")
        scrollbar.grid(row=1, column=1, sticky="ns")
        grid = ttk.Frame(canvas)
        window_identifier = canvas.create_window(
            (0, 0), window=grid, anchor="nw")
        grid.bind("<Configure>", lambda _event: self._resize_scroll())
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(
                window_identifier, width=event.width))
        context.update(canvas=canvas, grid=grid)

    def _resize_scroll(self):
        context = self._context
        canvas = context["canvas"]
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _refresh_grid(self, _event=None):
        context = self._context
        grid = context["grid"]
        for widget in grid.winfo_children():
            widget.destroy()
        context["photos"] = []
        query = context["search_variable"].get().strip()
        entries = context["catalog"].search(query)
        for index, entry in enumerate(entries):
            self._add_icon_button(index, entry)
        self._empty_message(entries)

    def _add_icon_button(self, index, entry):
        context = self._context
        grid = context["grid"]
        photo = self._icon_photo(entry)
        options = {
            "text": entry.label() + "\n" + entry.set_label(),
            "compound": "top",
            "command": lambda selected=entry: self._choose(selected),
        }
        if photo is not None:
            options["image"] = photo
            context["photos"].append(photo)
        button = ttk.Button(grid, **options)
        row, column = divmod(index, self.COLUMN_COUNT)
        button.grid(row=row, column=column, sticky="nsew", padx=4, pady=4)
        grid.columnconfigure(column, weight=1)

    @staticmethod
    def _icon_photo(entry):
        if not HAS_PIL:
            return None
        _name, paths, viewbox = decode_kustom_icon(entry.encoded_value())
        if not paths:
            return None
        size = 58
        mask = Image.new("L", (size, size), 0)
        masks = map(
            lambda path: svg_path_mask(path, size, size, viewbox=viewbox),
            paths)
        for path_mask in filter(None, masks):
            mask = ImageChops.lighter(mask, path_mask)
        image = Image.new("RGBA", (size, size), (50, 55, 70, 255))
        image.putalpha(mask)
        return ImageTk.PhotoImage(image)

    def _empty_message(self, entries):
        if entries:
            return
        grid = self._context["grid"]
        ttk.Label(
            grid, text="一致するアイコンがありません。"
        ).grid(row=0, column=0, padx=20, pady=20)

    def _choose(self, entry):
        context = self._context
        item = context["item"]
        context["catalog"].apply(item, entry)
        owner = context["owner"]
        memory = owner.memory
        owner._mark_dirty()
        memory["photo_cache"].clear()
        owner._refresh_all(select=item)
        context["window"].destroy()
