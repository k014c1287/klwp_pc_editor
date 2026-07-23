"""Background image bindings and bitmap Global entries."""


class BackgroundImageBinding:
    FIELD = "background_bitmap"

    def __init__(self, root_module):
        self._root_module = root_module

    def form_values(self):
        formula = self._mapping_value("internal_formulas")
        global_name = self._mapping_value("internal_globals")
        return formula, global_name

    def apply(self, formula, global_name):
        self._write_mapping_value("internal_formulas", formula)
        self._write_mapping_value("internal_globals", global_name)

    def _mapping_value(self, mapping_name):
        root_module = self._root_module
        mapping = root_module.get(mapping_name)
        if not isinstance(mapping, dict):
            return ""
        return str(mapping.get(self.FIELD, "") or "")

    def _write_mapping_value(self, mapping_name, value):
        root_module = self._root_module
        mapping = root_module.get(mapping_name)
        updated = dict(mapping) if isinstance(mapping, dict) else {}
        if value:
            updated[self.FIELD] = value
            root_module[mapping_name] = updated
            return
        updated.pop(self.FIELD, None)
        if updated:
            root_module[mapping_name] = updated
            return
        root_module.pop(mapping_name, None)


class BitmapGlobalCollection:
    def __init__(self, root_module):
        self._root_module = root_module

    def names(self):
        entries = self._entries()
        candidates = filter(
            lambda name: self._is_bitmap(entries[name]), entries)
        return tuple(sorted(candidates, key=lambda name: self._index(entries[name])))

    def add(self, name, reference):
        entries = self._entries()
        entries[name] = {
            "index": self._next_index(entries), "type": "BITMAP",
            "title": name, "description": "", "value": reference,
        }

    def contains(self, name):
        return name in self._entries()

    def _entries(self):
        root_module = self._root_module
        entries = root_module.get("globals_list")
        if isinstance(entries, dict):
            return entries
        root_module["globals_list"] = {}
        return root_module["globals_list"]

    @staticmethod
    def _is_bitmap(entry):
        return isinstance(entry, dict) and entry.get("type") == "BITMAP"

    @staticmethod
    def _index(entry):
        return int(entry.get("index", 0) or 0)

    @staticmethod
    def _next_index(entries):
        values = filter(lambda entry: isinstance(entry, dict), entries.values())
        indexes = map(BitmapGlobalCollection._index, values)
        return max(tuple(indexes) or (0,)) + 1
