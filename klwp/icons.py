"""Self-contained FontIcon choices compatible with KLWP archives."""

import re

from .svg import decode_kustom_icon, encode_kustom_icon


MATERIAL_ICON_SET = "iconify://ic?name=Google%20Material%20Icons"

MATERIAL_ICON_PATHS = (
    ("add", "追加", "M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"),
    ("baseline-apps", "アプリ一覧",
     "M4 8h4V4H4v4zm6 12h4v-4h-4v4zm-6 0h4v-4H4v4zm0-6h4v-4H4v4z"
     "m6 0h4v-4h-4v4zm6-10v4h4V4h-4zm-6 4h4V4h-4v4zm6 6h4v-4h-4v4z"
     "m0 6h4v-4h-4v4z"),
    ("baseline-airplanemode-active", "飛行機",
     "M10.18 9 2 3.5V2l10 4 10-4v1.5L13.82 9 22 14.5V16l-10-4-10 4"
     "v-1.5L10.18 9z"),
    ("baseline-pause", "一時停止",
     "M6 19h4V5H6v14zm8-14v14h4V5h-4z"),
    ("baseline-play-arrow", "再生", "M8 5v14l11-7z"),
    ("baseline-skip-next", "次へ",
     "M6 18l8.5-6L6 6v12zM16 6v12h2V6h-2z"),
    ("baseline-skip-previous", "前へ",
     "M6 6h2v12H6V6zm3.5 6l8.5 6V6l-8.5 6z"),
    ("camera", "カメラ",
     "M9 2 7.17 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9"
     " 2-2V6c0-1.1-.9-2-2-2h-3.17L15 2H9zm3 15c-2.76 0-5-2.24-5-5s2.24"
     "-5 5-5 5 2.24 5 5-2.24 5-5 5zm3.2-5c0 1.77-1.43 3.2-3.2 3.2S8.8"
     " 13.77 8.8 12 10.23 8.8 12 8.8s3.2 1.43 3.2 3.2z"),
    ("check", "チェック",
     "M9 16.17 4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"),
    ("close", "閉じる",
     "M18.3 5.71 12 12l6.3 6.29-1.41 1.42L10.59 13.41 4.29 19.71"
     " 2.88 18.29 9.17 12 2.88 5.71 4.29 4.29 10.59 10.59 16.89"
     " 4.29z"),
    ("favorite", "お気に入り",
     "M12 21.35 10.55 20.03C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5"
     " 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22"
     " 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"),
    ("home", "ホーム", "M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z"),
    ("menu", "メニュー", "M3 18h18v-2H3v2zm0-5h18v-2H3v2zm0-7v2h18V6H3z"),
    ("search", "検索",
     "M9.5 3a6.5 6.5 0 1 0 3.98 11.64L19.85 21 21 19.85l-6.36-6.37"
     "A6.5 6.5 0 0 0 9.5 3zm0 2a4.5 4.5 0 1 1 0 9 4.5 4.5 0 0 1 0-9z"),
    ("settings", "設定",
     "M19.43 12.98c.04-.32.07-.65.07-.98s-.03-.66-.08-.98l2.11-1.65c.19"
     "-.15.24-.42.12-.64l-2-3.46c-.12-.22-.37-.31-.6-.22l-2.49 1c-.52"
     "-.4-1.08-.73-1.69-.98L14.5 2.42C14.47 2.18 14.25 2 14 2h-4c-.25"
     " 0-.46.18-.5.42l-.38 2.65c-.61.25-1.17.59-1.69.98l-2.49-1c-.23"
     "-.08-.48 0-.6.22l-2 3.46c-.13.22-.07.49.12.64l2.11 1.65c-.04"
     ".32-.08.66-.08.98s.03.66.08.98l-2.11 1.65c-.19.15-.24.42-.12"
     ".64l2 3.46c.12.22.37.31.6.22l2.49-1c.52.4 1.08.73 1.69.98"
     "l.38 2.65c.04.24.25.42.5.42h4c.25 0 .46-.18.5-.42l.38-2.65"
     "c.61-.25 1.17-.58 1.69-.98l2.49 1c.23.08.48 0 .6-.22l2-3.46"
     "c.12-.22.07-.49-.12-.64l-2.11-1.65zM12 15.5A3.5 3.5 0 1 1"
     " 12 8a3.5 3.5 0 0 1 0 7.5z"),
    ("star", "スター",
     "M12 17.27 18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2"
     " 9.19 8.63 2 9.24l5.46 4.73L5.82 21z"),
    ("round-wifi", "Wi-Fi",
     "M1 9l2 2c4.97-4.97 13.03-4.97 18 0l2-2C16.93 2.93 7.07"
     " 2.93 1 9zm8 8 3 3 3-3c-1.65-1.66-4.34-1.66-6 0zm-4-4 2"
     " 2c2.76-2.76 7.24-2.76 10 0l2-2C15.14 9.14 8.87 9.14 5 13z"),
)


class IconCatalogEntry:
    def __init__(self, name, label, icon_set, icon_value):
        self._values = {
            "name": name, "label": label,
            "icon_set": icon_set, "icon_value": icon_value,
        }

    @staticmethod
    def material(name, label, path):
        value = encode_kustom_icon(name, (path,))
        return IconCatalogEntry(name, label, MATERIAL_ICON_SET, value)

    @staticmethod
    def from_module(module):
        if module.get("internal_type") != "FontIconModule":
            return None
        raw_value = str(module.get("icon_icon", ""))
        name, paths, _viewbox = decode_kustom_icon(raw_value)
        if not name or not paths:
            return None
        icon_set = str(module.get("icon_set", MATERIAL_ICON_SET))
        label = str(name).replace("-", " ")
        return IconCatalogEntry(str(name), label, icon_set, raw_value)

    def key(self):
        return self._values["icon_set"], self._values["name"]

    def matches(self, query):
        text = " ".join((
            self._values["name"], self._values["label"],
            self.set_label(),
        ))
        return str(query).lower() in text.lower()

    def name(self):
        return self._values["name"]

    def label(self):
        return self._values["label"]

    def set_reference(self):
        return self._values["icon_set"]

    def set_label(self):
        reference = self._values["icon_set"]
        match = re.search(r"[?&]name=([^&]+)", reference)
        if match is None:
            return reference
        return match.group(1).replace("%20", " ")

    def encoded_value(self):
        return self._values["icon_value"]


class IconCatalog:
    def __init__(self, entries):
        self._entries = tuple(entries)

    @staticmethod
    def from_archive(archive):
        entries = [
            IconCatalogEntry.material(name, label, path)
            for name, label, path in MATERIAL_ICON_PATHS
        ]
        modules = IconCatalog._all_modules(archive.modules())
        entries.extend(filter(None, map(IconCatalogEntry.from_module, modules)))
        return IconCatalog(IconCatalog._unique(entries))

    @staticmethod
    def _all_modules(root_items):
        pending = list(root_items)
        modules = []
        while pending:
            module = pending.pop()
            modules.append(module)
            pending.extend(module.get("viewgroup_items", []))
        return tuple(modules)

    @staticmethod
    def _unique(entries):
        values = {}
        for entry in entries:
            values.setdefault(entry.key(), entry)
        return tuple(values.values())

    def search(self, query=""):
        return tuple(filter(lambda entry: entry.matches(query), self._entries))

    def apply(self, item, entry):
        item["icon_set"] = entry.set_reference()
        item["icon_icon"] = entry.encoded_value()
