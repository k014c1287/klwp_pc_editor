"""First-class history timeline for immutable archive snapshots."""


class ArchiveSnapshot:
    def __init__(self, **values):
        self._values = values

    def __getitem__(self, name):
        return self._values[name]

    def __eq__(self, other):
        if not isinstance(other, ArchiveSnapshot):
            return False
        return self._values == other._values


class HistoryTimeline:
    def __init__(self, limit=50):
        self._values = {
            "limit": limit, "undo": [], "redo": [],
            "current": None, "clean": None,
        }

    def reset(self, snapshot):
        self._values["undo"].clear()
        self._values["redo"].clear()
        self._values["current"] = snapshot
        self._values["clean"] = snapshot

    def record(self, snapshot):
        if snapshot == self._values["current"]:
            return
        self._values["undo"].append(self._values["current"])
        self._trim_undo()
        self._values["current"] = snapshot
        self._values["redo"].clear()

    def _trim_undo(self):
        overflow = len(self._values["undo"]) - self._values["limit"]
        if overflow > 0:
            del self._values["undo"][:overflow]

    def undo(self):
        if not self._values["undo"]:
            return None
        self._values["redo"].append(self._values["current"])
        self._values["current"] = self._values["undo"].pop()
        return self._values["current"]

    def redo(self):
        if not self._values["redo"]:
            return None
        self._values["undo"].append(self._values["current"])
        self._values["current"] = self._values["redo"].pop()
        return self._values["current"]

    def saved(self, snapshot):
        self._values["current"] = snapshot
        self._values["clean"] = snapshot

    def dirty(self):
        return self._values["current"] != self._values["clean"]

    def can_undo(self):
        return bool(self._values["undo"])

    def can_redo(self):
        return bool(self._values["redo"])

    def undo_count(self):
        return len(self._values["undo"])

    def redo_count(self):
        return len(self._values["redo"])

    def undo_snapshot(self, index):
        return self._values["undo"][index]
