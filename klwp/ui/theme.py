"""Apply the editor's dark visual theme and lightweight tooltips."""

from ..shared import (
    tk, ttk,
)


class EditorPalette:
    @staticmethod
    def colors():
        return {
            "background": "#171923",
            "surface": "#202331",
            "raised": "#2a2e3f",
            "hover": "#34394d",
            "border": "#3c4258",
            "text": "#f3f4f6",
            "muted": "#aeb4c3",
            "accent": "#5b8cff",
            "accent_hover": "#76a0ff",
            "canvas": "#101018",
        }


class EditorTheme:
    def __init__(self, owner):
        self._owner = owner

    def apply(self):
        owner = self._owner
        palette = EditorPalette.colors()
        style = ttk.Style(owner)
        self._select_theme(style)
        self._configure_surfaces(style, palette)
        self._configure_controls(style, palette)
        self._configure_tree(style, palette)
        self._configure_tk_defaults(owner, palette)

    @staticmethod
    def _select_theme(style):
        themes = style.theme_names()
        if "clam" in themes:
            style.theme_use("clam")

    @staticmethod
    def _configure_surfaces(style, palette):
        base = palette["background"]
        text = palette["text"]
        style.configure(".", background=base, foreground=text)
        style.configure("TFrame", background=base)
        style.configure("TLabel", background=base, foreground=text)
        style.configure("TPanedwindow", background=palette["border"])
        style.configure("TSeparator", background=palette["border"])

    @staticmethod
    def _configure_controls(style, palette):
        options = {
            "background": palette["raised"],
            "foreground": palette["text"],
            "bordercolor": palette["border"],
            "lightcolor": palette["raised"],
            "darkcolor": palette["raised"],
            "padding": (8, 5),
        }
        for name in ("TButton", "TMenubutton", "TCheckbutton"):
            style.configure(name, **options)
            EditorTheme._map_control(style, name, palette)
        EditorTheme._configure_inputs(style, palette)

    @staticmethod
    def _map_control(style, name, palette):
        style.map(
            name,
            background=[("active", palette["hover"]),
                        ("pressed", palette["accent"])],
            foreground=[("disabled", palette["muted"]),
                        ("active", palette["text"])],
        )

    @staticmethod
    def _configure_inputs(style, palette):
        input_options = {
            "fieldbackground": palette["surface"],
            "background": palette["surface"],
            "foreground": palette["text"],
            "bordercolor": palette["border"],
            "insertcolor": palette["text"],
        }
        for name in ("TEntry", "TCombobox", "TSpinbox"):
            style.configure(name, **input_options)
        style.configure("TScale", background=palette["background"])

    @staticmethod
    def _configure_tree(style, palette):
        style.configure(
            "Treeview", background=palette["surface"],
            fieldbackground=palette["surface"], foreground=palette["text"],
            bordercolor=palette["border"], rowheight=25)
        style.map(
            "Treeview", background=[("selected", palette["accent"])],
            foreground=[("selected", "#ffffff")])
        style.configure(
            "Treeview.Heading", background=palette["raised"],
            foreground=palette["text"], relief="flat", padding=(6, 5))
        style.map(
            "Treeview.Heading",
            background=[("active", palette["hover"])])

    @staticmethod
    def _configure_tk_defaults(owner, palette):
        owner.configure(background=palette["background"])
        options = {
            "*Menu.background": palette["surface"],
            "*Menu.foreground": palette["text"],
            "*Menu.activeBackground": palette["accent"],
            "*Menu.activeForeground": "#ffffff",
            "*Listbox.background": palette["surface"],
            "*Listbox.foreground": palette["text"],
            "*Text.background": palette["surface"],
            "*Text.foreground": palette["text"],
        }
        for pattern, value in options.items():
            owner.option_add(pattern, value)


class Tooltip:
    def __init__(self, widget, message):
        self._state = {"widget": widget, "message": message, "window": None}
        widget.bind("<Enter>", self._show, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _show(self, _event=None):
        state = self._state
        if state["window"] is not None:
            return
        widget = state["widget"]
        x_position = widget.winfo_rootx() + 12
        y_position = widget.winfo_rooty() + widget.winfo_height() + 6
        window = tk.Toplevel(widget)
        window.wm_overrideredirect(True)
        window.wm_geometry(f"+{x_position}+{y_position}")
        self._label(window, state["message"])
        state["window"] = window

    @staticmethod
    def _label(window, message):
        palette = EditorPalette.colors()
        label = tk.Label(
            window, text=message, justify="left",
            background=palette["raised"], foreground=palette["text"],
            relief="solid", borderwidth=1, padx=8, pady=5)
        label.pack()

    def _hide(self, _event=None):
        state = self._state
        window = state["window"]
        if window is None:
            return
        window.destroy()
        state["window"] = None
