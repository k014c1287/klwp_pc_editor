"""Copy module trees and their referenced binary assets between presets."""

import copy
import json
from pathlib import PurePosixPath
import uuid


KUSTOM_FILE_PREFIX = "kfile://org.kustom.provider/"
ASSET_GROUP_NAMES = ("bitmaps", "fonts", "extras")


class ModuleClipboard:
    def __init__(self, modules, assets):
        self._values = {
            "modules": tuple(copy.deepcopy(modules)),
            "assets": dict(assets),
        }

    @staticmethod
    def capture(modules, archive):
        copied = tuple(copy.deepcopy(modules))
        serialized = json.dumps(copied, ensure_ascii=False)
        entries = ModuleClipboard._asset_entries(archive)
        referenced = filter(
            lambda entry: entry[0] in serialized, entries)
        return ModuleClipboard(copied, dict(referenced))

    @staticmethod
    def _asset_entries(archive):
        return tuple(
            (name, data)
            for group_name in ASSET_GROUP_NAMES
            for name, data in archive[group_name].items())

    def count(self):
        return len(self._values["modules"])

    def paste_into(self, archive):
        modules = list(copy.deepcopy(self._values["modules"]))
        replacements = self._copy_assets(archive)
        self._replace_references(modules, replacements)
        return modules

    def _copy_assets(self, archive):
        replacements = {}
        for name, data in self._values["assets"].items():
            self._copy_asset(archive, name, data, replacements)
        return replacements

    def _copy_asset(self, archive, name, data, replacements):
        group = self._asset_group(archive, name)
        existing = group.get(name)
        if existing == data:
            return
        destination = name
        if existing is not None:
            destination = self._unique_name(name)
        group[destination] = data
        if destination != name:
            source_reference = KUSTOM_FILE_PREFIX + name
            replacements[source_reference] = KUSTOM_FILE_PREFIX + destination

    @staticmethod
    def _asset_group(archive, name):
        prefix = str(name).split("/", 1)[0]
        if prefix in ASSET_GROUP_NAMES:
            return archive[prefix]
        return archive["extras"]

    @staticmethod
    def _unique_name(name):
        path = PurePosixPath(name)
        token = uuid.uuid4().hex
        if str(name).startswith("bitmaps/IMG"):
            return "bitmaps/IMG" + token
        filename = path.stem + "_" + token[:8] + path.suffix
        return str(path.parent / filename)

    def _replace_references(self, value, replacements):
        if isinstance(value, dict):
            self._replace_mapping(value, replacements)
            return
        if isinstance(value, list):
            self._replace_sequence(value, replacements)

    def _replace_mapping(self, mapping, replacements):
        for name in tuple(mapping):
            value = mapping[name]
            mapping[name] = self._replaced_value(value, replacements)

    def _replace_sequence(self, sequence, replacements):
        for index, value in enumerate(sequence):
            sequence[index] = self._replaced_value(value, replacements)

    def _replaced_value(self, value, replacements):
        if isinstance(value, (dict, list)):
            self._replace_references(value, replacements)
            return value
        if isinstance(value, str):
            return replacements.get(value, value)
        return value
