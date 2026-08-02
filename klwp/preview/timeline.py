"""Convert between preview timestamps and a 24-hour scrubber value."""

from datetime import datetime


class PreviewTimeline:
    LAST_SECOND = 23.0 + 59.0 / 60.0 + 59.0 / 3600.0

    def __init__(self, timestamp):
        self._timestamp = timestamp

    def hour(self):
        date_time = self._date_time()
        return (
            float(date_time.hour)
            + float(date_time.minute) / 60.0
            + float(date_time.second) / 3600.0)

    def at_hour(self, value):
        clamped = max(0.0, min(self.LAST_SECOND, float(value)))
        hour = int(clamped)
        minute_value = (clamped - hour) * 60.0
        minute = int(minute_value)
        second = int((minute_value - minute) * 60.0)
        date_time = self._date_time()
        changed = date_time.replace(
            hour=hour, minute=minute, second=second, microsecond=0)
        return int(changed.timestamp() * 1000.0)

    def label(self):
        date_time = self._date_time()
        return date_time.strftime("%H:%M:%S")

    def _date_time(self):
        try:
            return datetime.fromtimestamp(float(self._timestamp) / 1000.0)
        except (TypeError, ValueError, OSError):
            return datetime.now()
