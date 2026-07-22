"""Modal forms for one animation or one tap event."""

from ..shared import *  # noqa: F401,F403
from .setting_values import TouchActionValues, first_or_empty


class AnimationFormDialog:
    INVALID = object()
    KNOWN_ACTIONS = {
        "SCROLL", "SCROLL_INVERTED", "FADE", "FADE_IN", "FADE_OUT",
        "ROTATE", "ROTATE_INVERTED", "SCALE", "SCALE_INVERTED",
        "COLOR_INVERT", "COLOR_SEPIA", "COLOR_BRIGHTEN", "COLOR_SATURATE",
    }

    def __init__(self, owner, parent, initial=None):
        self._context = {
            "owner": owner, "parent": parent,
            "original": copy.deepcopy(initial or {}), "result": None,
        }

    def show(self):
        self._window()
        self._variables()
        self._fields()
        self._description()
        self._buttons()
        window = self._context["window"]
        window.wait_window()
        return self._context["result"]

    def _window(self):
        parent = self._context["parent"]
        window = tk.Toplevel(parent)
        window.title("アニメーション設定")
        window.geometry("450x500")
        window.transient(parent)
        window.grab_set()
        frame = ttk.Frame(window, padding=12)
        frame.pack(fill="both", expand=True)
        self._context["window"] = window
        self._context["frame"] = frame

    def _variables(self):
        original = self._context["original"]
        switch_names = self._context["owner"]._switch_global_names()
        default_switch = first_or_empty(switch_names)
        variables = {
            "type": tk.StringVar(value=str(original.get("type", "SCROLL"))),
            "action": tk.StringVar(value=str(original.get("action") or "SCROLL")),
            "trigger": tk.StringVar(value=str(original.get("trigger", default_switch))),
            "center": tk.StringVar(value=str(original.get("center", ""))),
            "rule": tk.StringVar(value=str(original.get("rule", "CENTER"))),
            "speed": tk.StringVar(value=str(original.get("speed", 100.0))),
            "angle": tk.StringVar(value=str(original.get("angle", 0.0))),
            "amount": tk.StringVar(value=str(original.get("amount", 100.0))),
            "duration": tk.StringVar(value=str(original.get("duration", 10.0))),
            "limit": tk.StringVar(value=str(original.get("limit", 0.0))),
            "ease": tk.StringVar(value=str(original.get("ease", "NORMAL"))),
        }
        self._context["switch_names"] = switch_names
        self._context["variables"] = variables

    def _fields(self):
        frame = self._context["frame"]
        for row, specification in enumerate(self._field_specifications()):
            self._field(frame, row, specification)
        frame.columnconfigure(1, weight=1)

    def _field_specifications(self):
        return (
            ("type", "反応元"), ("action", "動作"),
            ("trigger", "Switch"), ("center", "中心ページ"),
            ("rule", "適用範囲"), ("speed", "速度 / 移動量"),
            ("angle", "角度"), ("amount", "適用量 (0-100)"),
            ("duration", "往復時間 (×0.1秒)"),
            ("limit", "移動上限 (0=なし)"), ("ease", "補間"),
        )

    def _field(self, frame, row, specification):
        key, label = specification
        ttk.Label(frame, text=label).grid(
            row=row, column=0, sticky="w", pady=3)
        variable = self._context["variables"][key]
        values = self._combobox_values().get(key)
        widget = ttk.Entry(frame, textvariable=variable)
        if values is not None:
            widget = ttk.Combobox(
                frame, textvariable=variable, values=values, state="readonly")
        widget.grid(row=row, column=1, sticky="ew", pady=3)

    def _combobox_values(self):
        owner = self._context["owner"]
        variables = self._context["variables"]
        types = self._with_existing(
            ["SCROLL", "SWITCH", "LOOP_2W"], variables["type"].get())
        actions = self._with_existing(
            list(self.KNOWN_ACTIONS), variables["action"].get())
        page_count = max(3, owner._preview_page_count())
        centers = ("",) + tuple(
            f"SCREEN{index}" for index in range(1, page_count + 1))
        return {
            "type": tuple(types), "action": tuple(actions),
            "trigger": tuple(self._context["switch_names"]),
            "center": centers,
            "rule": ("CENTER", "BEFORE_CENTER", "AFTER_CENTER"),
            "ease": (
                "NORMAL", "STRAIGHT", "ACCELERATE", "DECELERATE",
                "OVERSHOOT", "BOUNCE"),
        }

    @staticmethod
    def _with_existing(values, existing):
        if existing not in values:
            values.append(existing)
        return values

    def _description(self):
        labels = self._field_specifications()
        ttk.Label(
            self._context["frame"],
            text="SCROLL: ページ追従 / SWITCH: タップ連動 / LOOP_2W: 往復ループ",
            foreground="#666", wraplength=400).grid(
                row=len(labels), column=0, columnspan=2,
                sticky="w", pady=(8, 4))

    def _buttons(self):
        labels = self._field_specifications()
        buttons = ttk.Frame(self._context["frame"])
        buttons.grid(
            row=len(labels) + 1, column=0, columnspan=2,
            sticky="e", pady=(12, 0))
        window = self._context["window"]
        ttk.Button(buttons, text="キャンセル", command=window.destroy).pack(
            side="left", padx=4)
        ttk.Button(buttons, text="OK", command=self._save).pack(
            side="left", padx=4)

    def _save(self):
        variables = self._context["variables"]
        reaction = variables["type"].get()
        action = variables["action"].get()
        if reaction == "SWITCH" and not variables["trigger"].get():
            self._error("先にSwitchを作成して選択してください。")
            return
        data = copy.deepcopy(self._context["original"])
        if action not in self.KNOWN_ACTIONS:
            self._save_unknown(data, reaction, action)
            return
        self._remove_known_values(data)
        data["type"] = reaction
        data["action"] = action
        if not self._apply_reaction(data, reaction):
            return
        if not self._apply_numeric_values(data, action):
            return
        ease = variables["ease"].get()
        if ease:
            data["ease"] = ease
        self._finish(data)

    def _save_unknown(self, data, reaction, action):
        data["type"] = reaction
        data["action"] = action
        if reaction == "SWITCH":
            data["trigger"] = self._context["variables"]["trigger"].get()
        self._finish(data)

    @staticmethod
    def _remove_known_values(data):
        names = (
            "type", "action", "trigger", "center", "rule",
            "speed", "angle", "amount", "duration", "limit", "ease",
        )
        for name in names:
            data.pop(name, None)

    def _apply_reaction(self, data, reaction):
        handlers = {
            "SWITCH": self._apply_switch,
            "SCROLL": self._apply_scroll,
            "LOOP_2W": self._apply_loop,
        }
        handler = handlers.get(reaction, self._accept_reaction)
        return handler(data)

    def _apply_switch(self, data):
        data["trigger"] = self._context["variables"]["trigger"].get()
        return True

    def _apply_scroll(self, data):
        variables = self._context["variables"]
        center = variables["center"].get()
        if center:
            data["center"] = center
        data["rule"] = variables["rule"].get()
        return True

    def _apply_loop(self, data):
        duration = self._number("duration")
        if duration is self.INVALID:
            self._error("往復時間は数値で指定してください。")
            return False
        data["duration"] = duration
        return True

    @staticmethod
    def _accept_reaction(_data):
        return True

    def _apply_numeric_values(self, data, action):
        names = ("amount",)
        if action in ("SCROLL", "SCROLL_INVERTED"):
            names = ("speed", "angle", "limit")
        values = [self._number(name) for name in names]
        if self.INVALID in values:
            self._error("速度・角度・適用量・上限は数値で指定してください。")
            return False
        data.update(zip(names, values))
        return True

    def _number(self, name):
        try:
            return float(self._context["variables"][name].get())
        except ValueError:
            return self.INVALID

    def _finish(self, data):
        self._context["result"] = data
        self._context["window"].destroy()

    def _error(self, message):
        messagebox.showerror(
            APP_TITLE, message, parent=self._context["window"])


class EventFormDialog:
    def __init__(self, owner, parent, initial=None):
        self._context = {
            "owner": owner, "parent": parent,
            "original": copy.deepcopy(initial or {}), "result": None,
        }

    def show(self):
        self._window()
        self._fields()
        self._buttons()
        window = self._context["window"]
        window.wait_window()
        return self._context["result"]

    def _window(self):
        parent = self._context["parent"]
        window = tk.Toplevel(parent)
        window.title("タップイベント設定")
        window.geometry("540x340")
        window.transient(parent)
        window.grab_set()
        frame = ttk.Frame(window, padding=12)
        frame.pack(fill="both", expand=True)
        self._context["window"] = window
        self._context["frame"] = frame

    def _fields(self):
        original = self._context["original"]
        existing_action = str(original.get("action", "SWITCH_GLOBAL"))
        actions = AnimationFormDialog._with_existing(
            ["SWITCH_GLOBAL", "LAUNCH_APP", "LAUNCH_SHORTCUT", "OPEN_LINK",
             "MUSIC", "KUSTOM_ACTION", "NONE"], existing_action)
        switches = self._context["owner"]._switch_global_names()
        variables = {
            "action": tk.StringVar(value=existing_action),
            "switch": tk.StringVar(value=str(
                original.get("switch", first_or_empty(switches)))),
            "intent": tk.StringVar(value=str(
                original.get("intent", original.get("kustom_action", "")))),
            "music": tk.StringVar(value=str(original.get("music_action", ""))),
        }
        self._context["variables"] = variables
        frame = self._context["frame"]
        self._combobox(frame, 0, "動作", variables["action"], actions)
        self._combobox(frame, 1, "Switch", variables["switch"], switches)
        self._entry(frame, 2, "Intent / URI / Kustom動作", variables["intent"])
        music_actions = ("", "PLAY_PAUSE", "PLAY", "PAUSE", "NEXT", "PREVIOUS", "STOP")
        self._combobox(frame, 3, "音楽操作", variables["music"], music_actions)
        ttk.Label(
            frame, foreground="#666", wraplength=370,
            text="アプリ・ショートカットはKLWP互換の intent:#Intent;...;end を、"
                 "リンクはURIを入力します。PCプレビューでは外部実行しません。").grid(
                     row=4, column=0, columnspan=2, sticky="w", pady=8)
        frame.columnconfigure(1, weight=1)

    @staticmethod
    def _entry(frame, row, label, variable):
        ttk.Label(frame, text=label).grid(
            row=row, column=0, sticky="w", pady=5)
        ttk.Entry(frame, textvariable=variable).grid(
            row=row, column=1, sticky="ew", pady=5)

    @staticmethod
    def _combobox(frame, row, label, variable, values):
        ttk.Label(frame, text=label).grid(
            row=row, column=0, sticky="w", pady=5)
        ttk.Combobox(
            frame, textvariable=variable, values=values,
            state="readonly").grid(
                row=row, column=1, sticky="ew", pady=5)

    def _buttons(self):
        buttons = ttk.Frame(self._context["frame"])
        buttons.grid(row=5, column=0, columnspan=2, sticky="e")
        window = self._context["window"]
        ttk.Button(buttons, text="キャンセル", command=window.destroy).pack(
            side="left", padx=4)
        ttk.Button(buttons, text="OK", command=self._save).pack(
            side="left", padx=4)

    def _save(self):
        variables = self._context["variables"]
        action = variables["action"].get()
        switch = variables["switch"].get()
        if action == "SWITCH_GLOBAL" and not switch:
            messagebox.showerror(
                APP_TITLE, "先にSwitchを作成して選択してください。",
                parent=self._context["window"])
            return
        event = TouchActionValues.update(
            self._context["original"], action, switch,
            variables["intent"].get(), variables["music"].get())
        self._context["result"] = event
        self._context["window"].destroy()
