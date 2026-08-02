"""Search and execute commands exposed by the editor menu catalog."""

from itertools import chain

from ..shared import *  # noqa: F401,F403
from .menu_toolbar import EditorCommandCatalog


class CommandPaletteEntries:
    def __init__(self, groups):
        grouped = map(self._group_entries, groups)
        entries = chain.from_iterable(grouped)
        self._entries = tuple(filter(None, entries))

    def filtered(self, query):
        text = str(query)
        normalized = text.strip().lower()
        if not normalized:
            return CommandPaletteEntries.from_entries(self._entries)
        matches = filter(
            lambda entry: normalized in entry[0].lower(), self._entries)
        return CommandPaletteEntries.from_entries(matches)

    def labels(self):
        return tuple(entry[0] for entry in self._entries)

    def count(self):
        return len(self._entries)

    def command(self, index):
        return self._entries[index][1]

    @staticmethod
    def from_entries(entries):
        collection = object.__new__(CommandPaletteEntries)
        collection._entries = tuple(entries)
        return collection

    @staticmethod
    def _group_entries(group):
        group_name, items = group
        converted = map(
            lambda item: CommandPaletteEntries._entry(group_name, item),
            items)
        return tuple(filter(None, converted))

    @staticmethod
    def _entry(group_name, item):
        label, command, _accelerator = item
        if label is None:
            return None
        return f"{group_name} › {label}", command


class CommandPaletteDialog:
    def __init__(self, owner, entries):
        self._state = {
            "owner": owner, "source": entries, "entries": entries,
            "window": None, "query": None, "list": None,
        }

    def show(self):
        state = self._state
        owner = state["owner"]
        window = tk.Toplevel(owner)
        state["window"] = window
        window.title("コマンドパレット")
        window.geometry("560x420")
        window.transient(owner)
        window.grab_set()
        window.bind("<Escape>", self.close)
        window.bind("<Return>", self._execute)
        self._build(window)

    def _build(self, window):
        frame = ttk.Frame(window, padding=12)
        frame.pack(fill="both", expand=True)
        query = tk.StringVar(value="")
        self._state["query"] = query
        entry = ttk.Entry(frame, textvariable=query)
        entry.pack(fill="x", pady=(0, 8))
        entry.bind("<KeyRelease>", self._filter)
        listing = tk.Listbox(frame, activestyle="dotbox")
        listing.pack(fill="both", expand=True)
        listing.bind("<Double-Button-1>", self._execute)
        self._state["list"] = listing
        self._replace_rows(self._state["entries"])
        entry.focus_set()

    def _filter(self, _event=None):
        state = self._state
        query = state["query"].get()
        entries = state["source"].filtered(query)
        state["entries"] = entries
        self._replace_rows(entries)

    def _replace_rows(self, entries):
        listing = self._state["list"]
        listing.delete(0, "end")
        for label in entries.labels():
            listing.insert("end", label)
        if entries.count() > 0:
            listing.selection_set(0)

    def _execute(self, _event=None):
        state = self._state
        entries = state["entries"]
        index = self._selected_index(state["list"], entries)
        if index is None:
            return "break"
        command = entries.command(index)
        self.close()
        command()
        return "break"

    @staticmethod
    def _selected_index(listing, entries):
        selection = listing.curselection()
        if selection:
            return int(selection[0])
        if entries.count() > 0:
            return 0
        return None

    def close(self, _event=None):
        window = self._state["window"]
        if window is None:
            return
        window.destroy()
        self._state["window"] = None


class CommandPaletteMixin:
    def cmd_command_palette(self):
        groups = EditorCommandCatalog(self).menu_groups()
        entries = CommandPaletteEntries(groups)
        CommandPaletteDialog(self, entries).show()

    def _on_command_palette_shortcut(self, _event=None):
        self.cmd_command_palette()
        return "break"
