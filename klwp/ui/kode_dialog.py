"""Live editing, validation, completion and preview for KLWP Kode."""

from ..shared import (
    APP_TITLE, eval_formula, json, messagebox,
    re, tk, ttk,
)


SUPPORTED_KODE_FUNCTIONS = (
    "ai", "bi", "br", "ce", "ci", "df", "gv", "if", "li",
    "mi", "mu", "nc", "rm", "tc", "tf", "wf", "wi",
)

KODE_CANDIDATES = (
    ("条件分岐 if", "$if(condition, true, false)$"),
    ("日時 df", "$df(HH:mm)$"),
    ("Global gv", "$gv(name)$"),
    ("バッテリー bi", "$bi(level)$"),
    ("天気 wi", "$wi(temp)$"),
    ("天気予報 wf", "$wf(max, 0)$"),
    ("音楽 mi", "$mi(title)$"),
    ("位置 li", "$li(loc)$"),
    ("通信 nc", "$nc(wifi)$"),
    ("端末情報 rm", "$rm(cused)$"),
    ("数学 mu", "$mu(round, value, 0)$"),
    ("文字列 tc", "$tc(up, text)$"),
    ("色 ce", "$ce(#FFFFFFFF, alpha, 50)$"),
    ("時間差 tf", "$tf(value)$"),
    ("カレンダー ci", "$ci(title)$"),
    ("天文 ai", "$ai(seasonc)$"),
    ("Broadcast br", "$br(tasker, value)$"),
)


class KodeFormulaScanner:
    def __init__(self):
        self._state = {
            "depth": 0, "quote": "", "escaped": False, "problem": "",
        }

    def consume(self, character):
        state = self._state
        if state["problem"]:
            return
        if state["escaped"]:
            state["escaped"] = False
            return
        if character == "\\" and state["quote"]:
            state["escaped"] = True
            return
        if state["quote"]:
            self._consume_quoted(character)
            return
        if character in ("'", '"'):
            state["quote"] = character
            return
        if character == "(":
            state["depth"] += 1
            return
        if character == ")":
            self._close_parenthesis()

    def _consume_quoted(self, character):
        state = self._state
        if character == state["quote"]:
            state["quote"] = ""

    def _close_parenthesis(self):
        state = self._state
        state["depth"] -= 1
        if state["depth"] < 0:
            state["problem"] = "閉じ括弧が多すぎます"

    def problem(self):
        state = self._state
        if state["problem"]:
            return state["problem"]
        if state["quote"]:
            return "文字列の引用符が閉じられていません"
        if state["depth"]:
            return "括弧が閉じられていません"
        return ""


class KodeSyntax:
    @staticmethod
    def problem(source):
        parts = str(source).split("$")
        if len(parts) % 2 == 0:
            return "$ の開始と終了が対応していません"
        formulas = parts[1::2]
        if any(not formula.strip() for formula in formulas):
            return "空の $...$ 数式があります"
        problems = map(KodeSyntax._formula_problem, formulas)
        return next(filter(None, problems), "")

    @staticmethod
    def _formula_problem(formula):
        scanner = KodeFormulaScanner()
        for character in formula:
            scanner.consume(character)
        return scanner.problem()

    @staticmethod
    def unsupported_functions(source):
        formulas = str(source).split("$")[1::2]
        found = set()
        for formula in formulas:
            found.update(re.findall(
                r"\b([A-Za-z][A-Za-z0-9_]*)\s*\(", formula))
        normalized = map(str.lower, found)
        unsupported = set(normalized) - set(SUPPORTED_KODE_FUNCTIONS)
        return tuple(sorted(unsupported))


class KodeInspector:
    def __init__(self, source, global_values=None):
        self._values = {"source": source, "globals": global_values or {}}

    def inspect(self):
        source = self._values["source"]
        problem = KodeSyntax.problem(source)
        if problem:
            return self._result(False, "構文エラー: " + problem, "")
        try:
            value = eval_formula(source, self._values["globals"])
        except Exception as error:
            return self._result(False, "評価エラー: " + str(error), "")
        unsupported = KodeSyntax.unsupported_functions(source)
        if unsupported:
            names = ", ".join(unsupported)
            return self._result(
                True, "構文OK / PCプレビュー未対応: " + names, value)
        return self._result(True, "構文OK", value)

    @staticmethod
    def _result(valid, status, value):
        return {
            "valid": valid, "status": status,
            "preview": KodeInspector._display(value),
        }

    @staticmethod
    def _display(value):
        if isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=False)


class KodeTargetCollection:
    PREFIX = "internal_formulas."

    def __init__(self, item):
        self._item = item

    def names(self):
        names = []
        item = self._item
        if item.get("internal_type") == "TextModule":
            names.append("text_expression")
        formulas = item.get("internal_formulas", {})
        names.extend(self.PREFIX + name for name in sorted(formulas))
        if not names:
            names.append(self.PREFIX)
        return tuple(names)

    def source(self, target):
        item = self._item
        if target == "text_expression":
            return str(item.get(target, ""))
        property_name = self._property_name(target)
        formulas = item.get("internal_formulas", {})
        return str(formulas.get(property_name, ""))

    def valid(self, target):
        item = self._item
        if target == "text_expression":
            return item.get("internal_type") == "TextModule"
        property_name = self._property_name(target)
        pattern = r"[A-Za-z_][A-Za-z0-9_]*"
        return re.fullmatch(pattern, property_name) is not None

    def apply(self, target, source):
        item = self._item
        if target == "text_expression":
            item[target] = source
            return
        property_name = self._property_name(target)
        formulas = item.setdefault("internal_formulas", {})
        if source.strip():
            formulas[property_name] = source
            return
        formulas.pop(property_name, None)
        if not formulas:
            item.pop("internal_formulas", None)

    def _property_name(self, target):
        if not str(target).startswith(self.PREFIX):
            return ""
        return str(target)[len(self.PREFIX):].strip()


class KodeEditorDialog:
    def __init__(self, owner, item):
        self._context = {
            "owner": owner, "item": item,
            "targets": KodeTargetCollection(item),
        }

    def show(self):
        self._create_window()
        self._target_controls()
        self._editor_controls()
        self._candidate_controls()
        self._result_controls()
        self._buttons()
        self._load_target()

    def _create_window(self):
        context = self._context
        owner = context["owner"]
        window = tk.Toplevel(owner)
        window.title("Kode 数式ライブエディタ")
        window.geometry("860x620")
        window.transient(owner)
        window.grab_set()
        frame = ttk.Frame(window, padding=12)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=3)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(1, weight=1)
        context.update(window=window, frame=frame)

    def _target_controls(self):
        context = self._context
        frame = context["frame"]
        row = ttk.Frame(frame)
        row.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        ttk.Label(row, text="編集対象").pack(side="left")
        targets = context["targets"]
        variable = tk.StringVar(value=targets.names()[0])
        selector = ttk.Combobox(
            row, textvariable=variable, values=targets.names(), width=42)
        selector.pack(side="left", fill="x", expand=True, padx=8)
        selector.bind("<<ComboboxSelected>>", self._load_target)
        ttk.Button(row, text="読込", command=self._load_target).pack(side="left")
        context.update(target_variable=variable, target_selector=selector)

    def _editor_controls(self):
        context = self._context
        frame = context["frame"]
        editor_frame = ttk.LabelFrame(frame, text="Kode", padding=6)
        editor_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        text = tk.Text(
            editor_frame, wrap="word", undo=True, font=("Consolas", 11))
        text.pack(fill="both", expand=True)
        text.bind("<KeyRelease>", self._schedule_inspection)
        context["text"] = text

    def _candidate_controls(self):
        context = self._context
        frame = context["frame"]
        candidate_frame = ttk.LabelFrame(frame, text="関数候補", padding=6)
        candidate_frame.grid(row=1, column=1, sticky="nsew")
        listbox = tk.Listbox(candidate_frame, exportselection=False)
        listbox.pack(fill="both", expand=True)
        for label, _snippet in KODE_CANDIDATES:
            listbox.insert("end", label)
        listbox.bind("<Double-Button-1>", self._insert_candidate)
        ttk.Button(
            candidate_frame, text="カーソル位置へ挿入",
            command=self._insert_candidate).pack(fill="x", pady=(6, 0))
        context["candidate_list"] = listbox

    def _result_controls(self):
        context = self._context
        frame = context["frame"]
        result_frame = ttk.LabelFrame(frame, text="ライブ評価", padding=6)
        result_frame.grid(
            row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        status = tk.StringVar()
        preview = tk.StringVar()
        status_label = ttk.Label(result_frame, textvariable=status)
        status_label.pack(anchor="w")
        ttk.Label(
            result_frame, textvariable=preview,
            font=("Consolas", 10), wraplength=800).pack(
                anchor="w", pady=(4, 0))
        context.update(
            status_variable=status, preview_variable=preview,
            status_label=status_label)

    def _buttons(self):
        context = self._context
        frame = context["frame"]
        row = ttk.Frame(frame)
        row.grid(row=3, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(
            row, text="キャンセル",
            command=context["window"].destroy).pack(side="left", padx=4)
        ttk.Button(row, text="適用", command=self._apply).pack(side="left")

    def _load_target(self, _event=None):
        context = self._context
        target = context["target_variable"].get().strip()
        source = context["targets"].source(target)
        text = context["text"]
        text.delete("1.0", "end")
        text.insert("1.0", source)
        self._inspect()

    def _insert_candidate(self, _event=None):
        context = self._context
        selection = context["candidate_list"].curselection()
        if not selection:
            return
        snippet = KODE_CANDIDATES[selection[0]][1]
        text = context["text"]
        text.insert("insert", snippet)
        text.focus_set()
        self._inspect()

    def _schedule_inspection(self, _event=None):
        context = self._context
        scheduled = context.get("inspection_after")
        window = context["window"]
        if scheduled is not None:
            window.after_cancel(scheduled)
        context["inspection_after"] = window.after(120, self._inspect)

    def _inspection(self):
        context = self._context
        source = context["text"].get("1.0", "end-1c")
        owner = context["owner"]
        return KodeInspector(source, owner._root_globals()).inspect()

    def _inspect(self):
        context = self._context
        result = self._inspection()
        context["status_variable"].set(result["status"])
        context["preview_variable"].set("結果: " + result["preview"])
        color = "#157F3B" if result["valid"] else "#B42318"
        context["status_label"].configure(foreground=color)
        context["inspection_after"] = None

    def _apply(self):
        context = self._context
        target = context["target_variable"].get().strip()
        if not context["targets"].valid(target):
            self._error(
                "編集対象は text_expression または "
                "internal_formulas.プロパティ名 で指定してください。")
            return
        result = self._inspection()
        if not result["valid"]:
            self._error(result["status"])
            return
        source = context["text"].get("1.0", "end-1c")
        context["targets"].apply(target, source)
        owner = context["owner"]
        item = context["item"]
        owner._mark_dirty()
        owner._refresh_all(select=item)
        context["window"].destroy()

    def _error(self, message):
        messagebox.showerror(
            APP_TITLE, message, parent=self._context["window"])
