"""Dialog for editing formula inputs without an Android device."""

from datetime import datetime

from ..shared import *  # noqa: F401,F403
from ..preview.values import (
    PREVIEW_VALUE_FIELDS, converted_preview_value, default_preview_values,
)


class PreviewValuesDialog:
    def __init__(self, owner):
        self._context = {"owner": owner, "variables": {}}

    def show(self):
        self._create_window()
        self._date_field()
        self._value_fields()
        self._buttons()

    def _create_window(self):
        owner = self._context["owner"]
        window = tk.Toplevel(owner)
        window.title("プレビュー値")
        window.geometry("560x700")
        window.transient(owner)
        window.grab_set()
        canvas = tk.Canvas(window, highlightthickness=0)
        scrollbar = ttk.Scrollbar(window, command=canvas.yview)
        frame = ttk.Frame(canvas, padding=12)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        canvas.create_window((0, 0), window=frame, anchor="nw")
        frame.bind("<Configure>", lambda _event: self._resize_scroll(canvas))
        context = self._context
        context.update(window=window, frame=frame)

    @staticmethod
    def _resize_scroll(canvas):
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _date_field(self):
        owner = self._context["owner"]
        memory = owner.memory
        timestamp = memory.optional("preview_ts")
        date_time = datetime.fromtimestamp(float(timestamp) / 1000.0)
        variable = tk.StringVar(
            value=date_time.strftime("%Y-%m-%d %H:%M:%S"))
        self._context["date_variable"] = variable
        self._field_row(0, "日時", variable)

    def _value_fields(self):
        owner = self._context["owner"]
        values = owner.memory["preview_values"]
        variables = self._context["variables"]
        for row, field in enumerate(PREVIEW_VALUE_FIELDS, start=1):
            section, name, label = field
            variable = tk.StringVar(value=str(values[section][name]))
            variables[(section, name)] = variable
            self._field_row(row, label, variable)

    def _field_row(self, row, label, variable):
        frame = self._context["frame"]
        ttk.Label(frame, text=label).grid(
            row=row, column=0, sticky="w", padx=(0, 8), pady=3)
        ttk.Entry(frame, textvariable=variable, width=34).grid(
            row=row, column=1, sticky="ew", pady=3)
        frame.columnconfigure(1, weight=1)

    def _buttons(self):
        frame = self._context["frame"]
        row = len(PREVIEW_VALUE_FIELDS) + 1
        buttons = ttk.Frame(frame)
        buttons.grid(row=row, column=0, columnspan=2, sticky="e", pady=12)
        ttk.Button(
            buttons, text="既定値", command=self._restore_defaults).pack(
                side="left", padx=3)
        window = self._context["window"]
        ttk.Button(buttons, text="キャンセル", command=window.destroy).pack(
            side="left", padx=3)
        ttk.Button(buttons, text="適用", command=self._apply).pack(
            side="left", padx=3)

    def _restore_defaults(self):
        defaults = default_preview_values()
        variables = self._context["variables"]
        for section, name, _label in PREVIEW_VALUE_FIELDS:
            variables[(section, name)].set(str(defaults[section][name]))

    def _apply(self):
        owner = self._context["owner"]
        values = owner.memory["preview_values"]
        variables = self._context["variables"]
        for section, name, _label in PREVIEW_VALUE_FIELDS:
            default = values[section][name]
            entered = variables[(section, name)].get()
            values[section][name] = converted_preview_value(entered, default)
        if not self._apply_date(owner):
            return
        owner._render()
        self._context["window"].destroy()

    def _apply_date(self, owner):
        entered = self._context["date_variable"].get()
        try:
            date_time = datetime.strptime(entered, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            messagebox.showerror(
                APP_TITLE, "日時は YYYY-MM-DD HH:MM:SS 形式で入力してください。",
                parent=self._context["window"])
            return False
        owner.memory["preview_ts"] = int(date_time.timestamp() * 1000)
        return True


class PreviewValuesMixin:
    def _edit_preview_values(self):
        PreviewValuesDialog(self).show()
