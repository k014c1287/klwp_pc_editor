"""Reusable visual editor for KLWP AARRGGBB colors."""

from ..shared import *  # noqa: F401,F403


class KlwpColor:
    DEFAULT = "#FFFFFFFF"

    def __init__(self, value):
        self._encoded = self._normalized(value)

    @staticmethod
    def _normalized(value):
        if not isinstance(value, str):
            return KlwpColor.DEFAULT
        text = value.strip()
        if len(text) == 7 and text.startswith("#"):
            text = "#FF" + text[1:]
        if len(text) != 9 or not text.startswith("#"):
            return KlwpColor.DEFAULT
        try:
            int(text[1:], 16)
        except ValueError:
            return KlwpColor.DEFAULT
        return text.upper()

    def encoded(self):
        return self._encoded

    def chooser_color(self):
        encoded = self._encoded
        return "#" + encoded[3:]

    def opacity_percentage(self):
        encoded = self._encoded
        alpha = int(encoded[1:3], 16)
        return round(alpha * 100 / 255)

    def replace_chooser_color(self, value):
        selected = KlwpColor(value)
        selected_rgb = selected.chooser_color()
        encoded = self._encoded
        self._encoded = encoded[:3] + selected_rgb[1:]

    def replace_opacity_percentage(self, value):
        try:
            percentage = float(value)
        except (TypeError, ValueError):
            return
        percentage = max(0.0, min(100.0, percentage))
        alpha = round(percentage * 255 / 100)
        encoded = self._encoded
        self._encoded = f"#{alpha:02X}{encoded[3:]}"


class ColorControl:
    """Combine a swatch, color chooser, opacity and raw code entry."""

    def __init__(self, parent, initial_color, changed=None):
        self._context = {
            "parent": parent,
            "color": KlwpColor(initial_color),
            "changed": changed,
        }

    def build(self):
        context = self._context
        frame = ttk.Frame(context["parent"])
        color = context["color"]
        context["color_variable"] = tk.StringVar(value=color.encoded())
        context["opacity_variable"] = tk.IntVar(
            value=color.opacity_percentage())
        self._build_picker_row(frame)
        self._build_value_row(frame)
        self._synchronize(False)
        return frame

    def _build_picker_row(self, frame):
        context = self._context
        swatch = tk.Label(frame, width=4, relief="sunken", borderwidth=1)
        swatch.grid(row=0, column=0, padx=(0, 4), pady=1, sticky="ns")
        button = ttk.Button(frame, text="色を選ぶ", command=self._pick)
        button.grid(row=0, column=1, columnspan=2, sticky="ew", pady=1)
        context["swatch"] = swatch

    def _build_value_row(self, frame):
        context = self._context
        entry = ttk.Entry(
            frame, textvariable=context["color_variable"], width=11)
        entry.grid(row=1, column=0, columnspan=2, sticky="ew", pady=1)
        entry.bind("<Return>", self._apply_code)
        entry.bind("<FocusOut>", self._apply_code)
        opacity = ttk.Spinbox(
            frame, from_=0, to=100, width=5,
            textvariable=context["opacity_variable"],
            command=self._apply_opacity)
        opacity.grid(row=1, column=2, padx=(4, 0), pady=1)
        opacity.bind("<Return>", self._apply_opacity)
        opacity.bind("<FocusOut>", self._apply_opacity)
        ttk.Label(frame, text="不透明度% ").grid(
            row=2, column=0, columnspan=3, sticky="e")

    def _pick(self):
        context = self._context
        color = context["color"]
        selected = colorchooser.askcolor(
            color=color.chooser_color(), parent=context["parent"])[1]
        if not selected:
            return
        color.replace_chooser_color(selected)
        self._synchronize(True)

    def _apply_code(self, _event=None):
        context = self._context
        variable = context["color_variable"]
        context["color"] = KlwpColor(variable.get())
        self._synchronize(True)

    def _apply_opacity(self, _event=None):
        context = self._context
        color = context["color"]
        variable = context["opacity_variable"]
        color.replace_opacity_percentage(variable.get())
        self._synchronize(True)

    def _synchronize(self, notify):
        context = self._context
        color = context["color"]
        context["color_variable"].set(color.encoded())
        context["opacity_variable"].set(color.opacity_percentage())
        context["swatch"].configure(background=color.chooser_color())
        if not notify:
            return
        callback = context["changed"]
        if callback is not None:
            callback(color.encoded())

    def replace_color(self, value):
        self._context["color"] = KlwpColor(value)
        self._synchronize(False)

    def encoded_color(self):
        context = self._context
        color = context["color"]
        return color.encoded()
