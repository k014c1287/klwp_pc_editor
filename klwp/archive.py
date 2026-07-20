"""Read and write the ZIP-based KLWP artifact format."""

import io
import json
import re
import time
import uuid
import zipfile

from .collections import ArchiveContents
from .runtime import KFILE_PREFIX
from .values import ArchiveLocation, DocumentSize, TextValue


class ForwardOnlyArchiveBuffer:
    """Make ZipFile emit data descriptors like Android ZipOutputStream."""

    def __init__(self):
        self._stream = io.BytesIO()

    def write(self, data):
        stream = self._stream
        return stream.write(data)

    def flush(self):
        return None

    def bytes(self):
        stream = self._stream
        return stream.getvalue()


class KlwpZipEntry(zipfile.ZipInfo):
    """ZIP entry carrying the flags emitted by KLWP on Android."""

    @staticmethod
    def create(name):
        timestamp = time.localtime()
        entry = KlwpZipEntry(name, timestamp[:6])
        entry.compress_type = zipfile.ZIP_DEFLATED
        entry.create_system = 0
        return entry

    def _encodeFilenameFlags(self):
        filename = self.filename
        encoded_name = filename.encode("utf-8")
        return encoded_name, self.flag_bits | 0x800


class PresetFactory:
    """Build the smallest valid editable KLWP preset."""

    @staticmethod
    def create(width, height, title):
        size = DocumentSize(width, height)
        preset_information = PresetFactory._information(size, title)
        return {
            "preset_info": preset_information,
            "preset_root": PresetFactory._root_module(),
        }

    @staticmethod
    def _information(size, title):
        information = {
            "archive": "", "author": "", "description": "", "email": "",
            "features": "", "pflags": 0, "hash": None,
            "id": str(uuid.uuid4()), "locked": False,
            "release": 381531008, "ts": ArchiveClock.timestamp(),
            "title": str(TextValue(title)), "version": 15,
            "xscreens": 0, "yscreens": 0,
        }
        information.update(size.json_fields())
        return information

    @staticmethod
    def _root_module():
        return {
            "internal_type": "RootLayerModule",
            "background_type": "SOLID",
            "background_color": "#FF202030",
            "viewgroup_items": [],
        }


class ArchiveClock:
    @staticmethod
    def timestamp():
        return int(time.time() * 1000)


class ArchiveReader:
    """Populate archive contents from a location."""

    def __init__(self, contents, location):
        self._contents = contents
        self._location = location

    def read(self):
        with zipfile.ZipFile(self._location, "r") as archive_file:
            self._read_entries(archive_file)
        self._require_preset()
        self._contents["path"] = self._location

    def _read_entries(self, archive_file):
        for name in archive_file.namelist():
            self._read_entry(archive_file, name)

    def _read_entry(self, archive_file, name):
        data = archive_file.read(name)
        if name == "preset.json":
            self._contents["preset"] = json.loads(data.decode("utf-8"))
            return
        if name.startswith("bitmaps/"):
            self._contents["bitmaps"][name] = data
            return
        if name.startswith("fonts/"):
            self._contents["fonts"][name] = data
            return
        self._contents["extras"][name] = data

    def _require_preset(self):
        if self._contents["preset"] is not None:
            return
        raise ValueError(
            "preset.json が見つかりません。KLWP ファイルではない可能性があります。"
        )


class ArchiveWriter:
    """Serialize archive contents without leaking ZIP details."""

    def __init__(self, contents, location):
        self._contents = contents
        self._location = location

    def write(self):
        buffer = ForwardOnlyArchiveBuffer()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive_file:
            self._write_archive(archive_file)
        self._write_file(buffer)
        self._contents["path"] = self._location

    def _write_archive(self, archive_file):
        preset = self._contents["preset"]
        encoded = json.dumps(preset, ensure_ascii=False, indent=1)
        self._write_entry(archive_file, "preset.json", encoded)
        self._write_asset_groups(archive_file)

    def _write_asset_groups(self, archive_file):
        contents = self._contents
        for group in contents.asset_groups():
            self._write_asset_group(archive_file, group)

    @staticmethod
    def _write_asset_group(archive_file, group):
        for name, data in group.items():
            ArchiveWriter._write_entry(archive_file, name, data)

    @staticmethod
    def _write_entry(archive_file, name, data):
        entry = KlwpZipEntry.create(name)
        archive_file.writestr(entry, data)

    def _write_file(self, buffer):
        with open(self._location, "wb") as output_file:
            output_file.write(buffer.bytes())


class BitmapImporter:
    """Move a bitmap through the filesystem boundary into an archive."""

    def __init__(self, contents, location):
        self._contents = contents
        self._location = location

    def add(self):
        identifier = uuid.uuid4()
        name = "bitmaps/IMG" + identifier.hex
        self.replace(name)
        suffix = name.split("/", 1)[1]
        return KFILE_PREFIX + suffix

    def replace(self, archive_name):
        with open(self._location, "rb") as source_file:
            self._contents["bitmaps"][archive_name] = source_file.read()


class BitmapReferenceNormalizer:
    """Migrate bitmap identifiers truncated by older editor versions."""

    INVALID_NAME_PATTERN = re.compile(r"^bitmaps/IMG[0-9a-fA-F]{28}$")

    def __init__(self, contents):
        self._contents = contents

    def normalize(self):
        renames = self._renames()
        if not renames:
            return
        self._rename_entries(renames)
        references = self._reference_renames(renames)
        contents = self._contents
        self._replace_references(contents["preset"], references)

    def _renames(self):
        contents = self._contents
        bitmaps = contents["bitmaps"]
        names = filter(self._invalid_name, tuple(bitmaps))
        return tuple(map(self._rename_pair, names))

    def _invalid_name(self, name):
        pattern = self.INVALID_NAME_PATTERN
        return pattern.fullmatch(name) is not None

    def _rename_pair(self, name):
        return name, self._new_name()

    @staticmethod
    def _new_name():
        identifier = uuid.uuid4()
        return "bitmaps/IMG" + identifier.hex

    def _rename_entries(self, renames):
        contents = self._contents
        bitmaps = contents["bitmaps"]
        for old_name, new_name in renames:
            bitmaps[new_name] = bitmaps.pop(old_name)

    @staticmethod
    def _reference_renames(renames):
        pairs = map(BitmapReferenceNormalizer._reference_pair, renames)
        return dict(pairs)

    @staticmethod
    def _reference_pair(rename):
        old_name, new_name = rename
        old_reference = BitmapReferenceNormalizer._reference(old_name)
        new_reference = BitmapReferenceNormalizer._reference(new_name)
        return old_reference, new_reference

    @staticmethod
    def _reference(name):
        parts = name.split("/", 1)
        return KFILE_PREFIX + parts[1]

    def _replace_references(self, value, references):
        if isinstance(value, dict):
            self._replace_mapping(value, references)
            return
        if isinstance(value, list):
            self._replace_sequence(value, references)

    def _replace_mapping(self, mapping, references):
        for name in tuple(mapping):
            mapping[name] = self._replaced_value(mapping[name], references)

    def _replace_sequence(self, sequence, references):
        for index in range(len(sequence)):
            sequence[index] = self._replaced_value(sequence[index], references)

    def _replaced_value(self, value, references):
        if isinstance(value, (dict, list)):
            self._replace_references(value, references)
            return value
        if isinstance(value, str):
            return references.get(value, value)
        return value


class KlwpArchive:
    """Behavioral facade for a KLWP artifact."""

    def __init__(self):
        self.contents = ArchiveContents()

    def __getitem__(self, name):
        return self.contents[name]

    def __setitem__(self, name, value):
        self.contents[name] = value

    def load(self, path):
        contents = ArchiveContents()
        reader = ArchiveReader(contents, ArchiveLocation(path))
        reader.read()
        normalizer = BitmapReferenceNormalizer(contents)
        normalizer.normalize()
        self.contents = contents

    def new(self, width=1080, height=2400, title="untitled"):
        self.contents = ArchiveContents()
        self.contents["preset"] = PresetFactory.create(width, height, title)

    def save(self, path):
        normalizer = BitmapReferenceNormalizer(self.contents)
        normalizer.normalize()
        information = self.contents["preset"]["preset_info"]
        information["ts"] = ArchiveClock.timestamp()
        writer = ArchiveWriter(self.contents, ArchiveLocation(path))
        writer.write()

    def add_bitmap(self, file_path):
        importer = BitmapImporter(self.contents, ArchiveLocation(file_path))
        return importer.add()

    def replace_bitmap(self, archive_name, file_path):
        importer = BitmapImporter(self.contents, ArchiveLocation(file_path))
        importer.replace(archive_name)

    def bitmap_refs(self):
        preset = self.contents["preset"]
        serialized = json.dumps(preset)
        matches = re.finditer(r"kfile://[^\s\"']+", serialized)
        return {match.group(0).rstrip("\\") for match in matches}

    def root_module(self):
        preset = self.contents["preset"]
        return preset["preset_root"]

    def modules(self):
        root_module = self.root_module()
        return root_module.setdefault("viewgroup_items", [])

