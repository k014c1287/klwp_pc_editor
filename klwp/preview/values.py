"""Editable device values used by the deterministic desktop preview."""

import copy


DEFAULT_PREVIEW_VALUES = {
    "battery": {"level": 95.0, "charging": 0.0, "fullempty": "future"},
    "weather": {
        "temp": 32.0, "flik": 32.0, "tempu": "C",
        "icon": "CLEAR", "cond": "Mostly Cloudy",
    },
    "forecast": {"max": 29.0, "min": 26.0, "cond": "MOSTLY_CLOUDY"},
    "media": {
        "title": "Song Title", "artist": "Artist Name",
        "state": "PLAYING", "percent": 40.0,
        "cover": "", "pos": 88000.0, "len": 218000.0,
    },
    "location": {
        "loc": "Yokohama", "country": "Japan", "postal": "231-0836",
    },
    "network": {
        "wifi": "CONNECTED", "ssid": "SSID-328F3B", "wsig": 9.0,
        "csig": 4.0, "dtype": "LTE", "cell": "ON",
    },
    "resource": {"cused": 42.0, "fstot": 256.0, "fsfree": 59.0},
    "calendar": {"title": "学校"},
    "astronomy": {"seasonc": "SPRING"},
    "broadcast": {"gpt_ans": "Preview broadcast value"},
}


PREVIEW_VALUE_FIELDS = (
    ("battery", "level", "バッテリー残量"),
    ("battery", "charging", "充電中 (0/1)"),
    ("weather", "temp", "現在気温"),
    ("weather", "flik", "体感気温"),
    ("weather", "tempu", "温度単位"),
    ("weather", "icon", "天気アイコンコード"),
    ("weather", "cond", "天気説明"),
    ("forecast", "max", "予報最高気温"),
    ("forecast", "min", "予報最低気温"),
    ("media", "title", "曲名"),
    ("media", "artist", "アーティスト"),
    ("media", "state", "再生状態"),
    ("media", "percent", "再生位置 (%)"),
    ("location", "loc", "地域"),
    ("location", "country", "国"),
    ("location", "postal", "郵便番号"),
    ("network", "wifi", "Wi-Fi状態"),
    ("network", "ssid", "SSID"),
    ("calendar", "title", "次の予定"),
    ("astronomy", "seasonc", "季節"),
)


def default_preview_values():
    return copy.deepcopy(DEFAULT_PREVIEW_VALUES)


def converted_preview_value(value, default):
    if not isinstance(default, (int, float)):
        return value
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
