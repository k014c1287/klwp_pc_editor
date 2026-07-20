"""Resolve KLWP global variables and formula-backed module values."""

from datetime import datetime

from ..formula import DEFAULT_DATE_FORMAT_VALUES, _as_number, eval_formula


class PreviewDateValues:
    def __init__(self, timestamp):
        self._timestamp = timestamp

    def values(self):
        try:
            date_time = datetime.fromtimestamp(float(self._timestamp) / 1000.0)
        except (TypeError, ValueError, OSError):
            return DEFAULT_DATE_FORMAT_VALUES
        return self._formatted(date_time)

    @staticmethod
    def _formatted(date_time):
        hour = date_time.hour % 12 or 12
        weekday = date_time.isoweekday()
        return {
            "hh": f"{hour:02d}", "h": str(hour),
            "H": str(date_time.hour), "k": str(date_time.hour or 24),
            "mm": f"{date_time.minute:02d}", "m": str(date_time.minute),
            "ss": f"{date_time.second:02d}", "dd": f"{date_time.day:02d}",
            "d": str(date_time.day), "e": str(weekday), "f": str(weekday),
            "M": str(date_time.month), "MM": f"{date_time.month:02d}",
            "MMM": date_time.strftime("%b"), "MMMM": date_time.strftime("%B"),
            "yyyy": str(date_time.year), "yy": f"{date_time.year % 100:02d}",
            "y": str(date_time.year), "a": date_time.strftime("%p"),
            "EEE": date_time.strftime("%a"), "EEEE": date_time.strftime("%A"),
        }


class RootGlobalValues:
    def __init__(self, owner):
        self._owner = owner

    def values(self):
        owner = self._owner
        memory = owner.memory
        archive = memory['archive']
        root_module = archive.root_module()
        stored = root_module.get("globals_list", {})
        result = dict(stored) if isinstance(stored, dict) else {}
        self._apply_switches(result)
        result["__df__"] = self._date_values()
        return result

    def _apply_switches(self, result):
        owner = self._owner
        memory = owner.memory
        switches = memory.optional("preview_switches", {})
        for name, enabled in switches.items():
            self._apply_switch(result, name, enabled)

    @staticmethod
    def _apply_switch(result, name, enabled):
        if not isinstance(result.get(name), dict):
            return
        entry = dict(result[name])
        entry["value"] = int(bool(enabled))
        result[name] = entry

    def _date_values(self):
        owner = self._owner
        memory = owner.memory
        timestamp = memory.optional("preview_ts")
        if timestamp is None:
            archive = memory['archive']
            information = archive["preset"].get("preset_info", {})
            timestamp = information.get("ts")
        return PreviewDateValues(timestamp).values()


class ModuleValueResolver:
    MISSING = object()

    def __init__(self, owner, global_values):
        self._owner = owner
        self._global_values = global_values

    def resolve(self, item, key, default=None):
        formula_value = self._formula_value(item, key)
        if formula_value is not self.MISSING:
            return formula_value
        global_value = self._linked_global_value(item, key, default)
        if global_value is not self.MISSING:
            return global_value
        return self._direct_value(item, key, default)

    def _formula_value(self, item, key):
        formulas = item.get("internal_formulas")
        if not isinstance(formulas, dict):
            return self.MISSING
        formula = formulas.get(key)
        if not isinstance(formula, str) or not formula.strip():
            return self.MISSING
        value = eval_formula(formula, self._global_values)
        if value in (None, ""):
            return self.MISSING
        return value

    def _linked_global_value(self, item, key, default):
        links = item.get("internal_globals")
        if not isinstance(links, dict) or key not in links:
            return self.MISSING
        global_values = self._global_values
        entry = global_values.get(str(links[key]))
        if isinstance(entry, dict):
            return self._global_entry_value(entry, default)
        if entry is not None:
            return entry
        return self.MISSING

    def _global_entry_value(self, entry, default):
        formula = entry.get("global_formula")
        if isinstance(formula, str) and formula.strip():
            return eval_formula(formula, self._global_values)
        return entry.get("value", default)

    def _direct_value(self, item, key, default):
        value = item.get(key, default)
        if self._is_formula(value):
            return eval_formula(value, self._global_values)
        return value

    @staticmethod
    def _is_formula(value):
        if not isinstance(value, str):
            return False
        stripped = value.strip()
        return stripped.startswith("$") and stripped.endswith("$")


def merge_local_globals(item, global_values):
    local_values = item.get("globals_list")
    if not isinstance(local_values, dict) or not local_values:
        return global_values or {}
    merged = dict(global_values or {})
    merged.update(local_values)
    return merged


def numeric_module_value(owner, item, key, default, global_values):
    resolver = ModuleValueResolver(owner, global_values)
    value = resolver.resolve(item, key, default)
    return _as_number(value, default)
