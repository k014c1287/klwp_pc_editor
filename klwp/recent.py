"""Persist a compact, validated list of recently opened KLWP files."""

import json
import os
from os.path import expanduser
from pathlib import Path


class RecentFileCollection:
    LIMIT = 8

    def __init__(self, paths=()):
        self._paths = tuple(paths)

    def valid_paths(self):
        return tuple(filter(self._is_valid, self._paths))

    def with_first(self, path):
        normalized = str(Path(path).resolve())
        remaining = filter(lambda item: item != normalized, self._paths)
        paths = (normalized, *remaining)
        return RecentFileCollection(paths[:self.LIMIT])

    @staticmethod
    def _is_valid(path):
        location = Path(path)
        suffix = location.suffix
        return location.is_file() and suffix.lower() == ".klwp"


class RecentFileStore:
    def __init__(self, storage_path=None):
        self._storage_path = Path(storage_path or self._default_path())

    def paths(self):
        collection = RecentFileCollection(self._read())
        paths = collection.valid_paths()
        self._write(paths)
        return paths

    def remember(self, path):
        collection = RecentFileCollection(self._read())
        updated = collection.with_first(path)
        paths = updated.valid_paths()
        self._write(paths)
        return paths

    def _read(self):
        location = self._storage_path
        if not location.is_file():
            return ()
        try:
            value = json.loads(location.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return ()
        if not isinstance(value, list):
            return ()
        return tuple(filter(lambda item: isinstance(item, str), value))

    def _write(self, paths):
        location = self._storage_path
        try:
            parent = location.parent
            parent.mkdir(parents=True, exist_ok=True)
            encoded = json.dumps(paths, ensure_ascii=False, indent=2)
            location.write_text(encoded, encoding="utf-8")
        except OSError:
            return

    @staticmethod
    def _default_path():
        base = os.getenv("APPDATA")
        if not base:
            base = expanduser("~")
        return Path(base) / "KLWPEditor" / "recent.json"
