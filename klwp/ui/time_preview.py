"""Drive live time and manual 24-hour scrubbing in the preview."""

from ..shared import (
    time,
)
from ..preview.timeline import PreviewTimeline


class TimePreviewMixin:
    def _start_preview_clock(self):
        if self._live_time_enabled():
            self._set_live_preview_timestamp()
            self._schedule_time_tick()

    def _live_time_enabled(self):
        memory = self.memory
        variable = memory.optional("preview_time_live_var")
        return bool(variable is not None and variable.get())

    def _schedule_time_tick(self):
        memory = self.memory
        if memory["_time_after_id"] is not None:
            return
        memory["_time_after_id"] = self.after(1000, self._time_tick)

    def _cancel_time_tick(self):
        memory = self.memory
        timer = memory["_time_after_id"]
        if timer is None:
            return
        self.after_cancel(timer)
        memory["_time_after_id"] = None

    def _time_tick(self):
        self.memory["_time_after_id"] = None
        if not self._live_time_enabled():
            return
        self._set_live_preview_timestamp()
        self._render()
        self._schedule_time_tick()

    def _on_live_time_changed(self):
        if not self._live_time_enabled():
            self._cancel_time_tick()
            self._set_status("時刻プレビュー: 手動")
            return
        self._set_live_preview_timestamp()
        self._render()
        self._schedule_time_tick()
        self._set_status("時刻プレビュー: 現在時刻へ追従")

    def _on_preview_time_changed(self, value):
        memory = self.memory
        if memory.optional("_updating_time_control", False):
            return
        try:
            hour = float(value)
        except (TypeError, ValueError):
            return
        self._disable_live_time()
        timeline = PreviewTimeline(memory["preview_ts"])
        memory["preview_ts"] = timeline.at_hour(hour)
        self._update_preview_time_controls()
        self._render()
        self._set_status("時刻プレビュー: 手動")

    def _set_manual_preview_timestamp(self, timestamp):
        self._disable_live_time()
        self.memory["preview_ts"] = timestamp
        self._update_preview_time_controls()

    def _disable_live_time(self):
        memory = self.memory
        variable = memory.optional("preview_time_live_var")
        if variable is not None:
            variable.set(False)
        self._cancel_time_tick()

    def _set_live_preview_timestamp(self):
        self.memory["preview_ts"] = int(time.time() * 1000.0)
        self._update_preview_time_controls()

    def _update_preview_time_controls(self):
        memory = self.memory
        timeline = PreviewTimeline(memory["preview_ts"])
        variable = memory.optional("preview_time_var")
        label = memory.optional("preview_time_label")
        if variable is not None:
            self._set_time_variable(variable, timeline.hour())
        if label is not None:
            label.configure(text=timeline.label())

    def _set_time_variable(self, variable, value):
        memory = self.memory
        memory["_updating_time_control"] = True
        try:
            variable.set(value)
        finally:
            memory["_updating_time_control"] = False
