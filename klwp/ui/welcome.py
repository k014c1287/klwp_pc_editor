"""Welcome window for creating, reopening, or exploring presets."""

from pathlib import Path

from ..shared import *  # noqa: F401,F403


class TemplateCatalog:
    def __init__(self, root=None):
        self._root = Path(root or self._default_root())

    def entries(self):
        root = self._root
        if not root.is_dir():
            return ()
        return tuple(sorted(root.glob("*.klwp"), key=self._sort_key))

    @staticmethod
    def _sort_key(path):
        name = path.name
        return name.lower()

    @staticmethod
    def _default_root():
        location = Path(__file__).resolve()
        ui_root = location.parent
        package_root = ui_root.parent
        project_root = package_root.parent
        return project_root / "sample"


class WelcomeDialog:
    def __init__(self, owner, templates=None):
        self._state = {
            "owner": owner,
            "templates": templates or TemplateCatalog(),
            "window": None,
            "recent_list": None,
            "recent_paths": (),
            "template_list": None,
            "template_paths": (),
        }

    def show(self):
        state = self._state
        owner = state["owner"]
        window = tk.Toplevel(owner)
        state["window"] = window
        window.title("KLWP Desktop Editor へようこそ")
        window.geometry("680x500")
        window.minsize(560, 420)
        window.transient(owner)
        window.protocol("WM_DELETE_WINDOW", self.close)
        self._header(window)
        self._primary_actions(window)
        self._file_lists(window)
        window.focus_set()

    @staticmethod
    def _header(window):
        frame = ttk.Frame(window, padding=(24, 22, 24, 10))
        frame.pack(fill="x")
        ttk.Label(
            frame, text="KLWP Desktop Editor",
            font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(
            frame, text="作業を開始する方法を選んでください。"
        ).pack(anchor="w", pady=(6, 0))

    def _primary_actions(self, window):
        frame = ttk.Frame(window, padding=(24, 8))
        frame.pack(fill="x")
        ttk.Button(
            frame, text="＋ 新しいプリセット",
            command=self._new).pack(side="left", padx=(0, 8))
        ttk.Button(
            frame, text="↗ KLWPファイルを開く",
            command=self._open).pack(side="left")

    def _file_lists(self, window):
        frame = ttk.Frame(window, padding=(24, 12, 24, 20))
        frame.pack(fill="both", expand=True)
        recent_paths = self._recent_paths()
        template_paths = self._state["templates"].entries()
        self._list_panel(
            frame, "最近使ったファイル", recent_paths,
            "recent_list", "recent_paths", self._open_recent)
        self._list_panel(
            frame, "サンプルから始める（別名保存）", template_paths,
            "template_list", "template_paths", self._open_template)

    def _list_panel(self, parent, title, paths, list_key, paths_key, command):
        frame = ttk.LabelFrame(parent, text=title, padding=8)
        frame.pack(side="left", fill="both", expand=True, padx=4)
        listing = tk.Listbox(frame, activestyle="dotbox", exportselection=False)
        listing.pack(fill="both", expand=True)
        for path in paths:
            listing.insert("end", path.name)
        self._state[list_key] = listing
        self._state[paths_key] = paths
        ttk.Button(frame, text="開く", command=command).pack(
            fill="x", pady=(8, 0))

    def _recent_paths(self):
        owner = self._state["owner"]
        store = owner.memory["recent_files"]
        return tuple(map(Path, store.paths()))

    def _new(self):
        owner = self._state["owner"]
        owner.cmd_new()
        self.close()

    def _open(self):
        owner = self._state["owner"]
        if owner.cmd_open():
            self.close()

    def _open_recent(self):
        path = self._selected_path("recent_list", "recent_paths")
        if path is None:
            return
        owner = self._state["owner"]
        if owner.cmd_open_path(str(path)):
            self.close()

    def _open_template(self):
        path = self._selected_path("template_list", "template_paths")
        if path is None:
            return
        owner = self._state["owner"]
        if owner.cmd_open_template(str(path)):
            self.close()

    def _selected_path(self, list_key, paths_key):
        listing = self._state[list_key]
        selection = listing.curselection()
        if not selection:
            return None
        return self._state[paths_key][selection[0]]

    def close(self):
        state = self._state
        window = state["window"]
        if window is None:
            return
        window.destroy()
        state["window"] = None
