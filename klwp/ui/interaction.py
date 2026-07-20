"""Handle preview animation, taps, swipes and canvas dragging."""

from ..shared import *  # noqa: F401,F403


class PreviewInteractionMixin:
    def _interaction_enabled(self):
        memory = self.memory
        mode = memory.optional("interaction_mode")
        return bool(mode is not None and mode.get())

    def _set_status(self, text):
        memory = self.memory
        status = memory.optional("status")
        if status is not None:
            status.config(text=text)

    def _on_interaction_mode_changed(self):
        self.memory['drag_state'] = None
        self.memory['interaction_drag'] = None
        if self._interaction_enabled():
            self._set_status(
                "操作プレビュー: タップでイベント、横スワイプでページ移動")
            return
        self._set_status("編集モード: 要素をドラッグして移動")

    def _set_preview_scroll(self, page, redraw=True):
        page_count = self._preview_page_count()
        page = max(0.0, min(float(page_count - 1), float(page)))
        self.memory['preview_scroll'] = page
        self._update_page_variable()
        self._update_preview_page_label()
        memory = self.memory
        if redraw and memory.optional("canvas") is not None:
            self._render()

    def _update_page_variable(self):
        memory = self.memory
        variable = memory.optional("preview_page_var")
        if variable is None:
            return
        self.memory['_updating_page_control'] = True
        try:
            variable.set(self.memory['preview_scroll'] + 1.0)
        finally:
            self.memory['_updating_page_control'] = False

    def _on_preview_page_changed(self, value):
        memory = self.memory
        if memory.optional("_updating_page_control", False):
            return
        try:
            page = float(value) - 1.0
        except (TypeError, ValueError):
            return
        self.memory['_scroll_transition'] = None
        self._set_preview_scroll(page)

    def cmd_toggle_loop(self):
        if self.memory['_loop_started_at'] is not None:
            self._stop_loop()
            return
        self.memory['_loop_started_at'] = time.perf_counter()
        self.memory['loop_button'].configure(text="ループ停止")
        self._ensure_animation_timer()

    def _stop_loop(self):
        self.memory['_loop_started_at'] = None
        self.memory['loop_button'].configure(text="ループ再生")
        self._render()

    def _ensure_animation_timer(self):
        if self.memory['_animation_after_id'] is None:
            self.memory['_animation_after_id'] = self.after(
                16, self._animation_tick)

    def _animation_tick(self):
        self.memory['_animation_after_id'] = None
        current_time = time.perf_counter()
        active = self.memory['_loop_started_at'] is not None
        transitions = list(self.memory['_switch_transitions'].items())
        for name, transition in transitions:
            active = self._advance_switch(name, transition, current_time) or active
        active = self._advance_scroll(current_time) or active
        self._render()
        if active:
            self.memory['_animation_after_id'] = self.after(
                16, self._animation_tick)

    def _advance_switch(self, name, transition, current_time):
        start, target, started_at, duration = transition
        progress = min(1.0, (current_time - started_at) / duration)
        eased = self._smooth_progress(progress)
        value = start + (target - start) * eased
        self.memory['preview_switch_progress'][name] = value
        if progress < 1.0:
            return True
        self.memory['preview_switch_progress'][name] = target
        del self.memory['_switch_transitions'][name]
        return False

    def _advance_scroll(self, current_time):
        transition = self.memory['_scroll_transition']
        if transition is None:
            return False
        start, target, started_at, duration = transition
        progress = min(1.0, (current_time - started_at) / duration)
        eased = self._smooth_progress(progress)
        self._set_preview_scroll(
            start + (target - start) * eased, redraw=False)
        if progress < 1.0:
            return True
        self.memory['_scroll_transition'] = None
        return False

    @staticmethod
    def _smooth_progress(progress):
        return progress * progress * (3.0 - 2.0 * progress)

    def _start_scroll_transition(self, target):
        maximum = float(self._preview_page_count() - 1)
        target = max(0.0, min(maximum, float(target)))
        self.memory['_scroll_transition'] = (
            self.memory['preview_scroll'], target,
            time.perf_counter(), 0.25)
        self._ensure_animation_timer()

    def _toggle_preview_switch(self, name):
        name = str(name)
        current_target = self.memory['preview_switches'].get(name, False)
        target = not current_target
        current_progress = self.memory['preview_switch_progress']
        start = float(current_progress.get(name, float(current_target)))
        self.memory['preview_switches'][name] = target
        self.memory['_switch_transitions'][name] = (
            start, float(target), time.perf_counter(), 0.30)
        self._ensure_animation_timer()
        return target

    def _perform_preview_event(self, event):
        if not isinstance(event, dict) or event.get("type") != "SINGLE_TAP":
            return False
        action = str(event.get("action", "NONE"))
        handlers = {
            "SWITCH_GLOBAL": self._perform_switch_event,
            "LAUNCH_SHORTCUT": self._perform_shortcut_event,
            "LAUNCH_APP": self._perform_external_event,
            "MUSIC": self._perform_external_event,
        }
        handler = handlers.get(action)
        if handler is None:
            return False
        return handler(event, action)

    def _perform_switch_event(self, event, _action):
        if not event.get("switch"):
            return False
        name = str(event["switch"])
        enabled = self._toggle_preview_switch(name)
        state = "ON" if enabled else "OFF"
        self._set_status(f"タップ: グローバル「{name}」を{state}")
        return True

    def _perform_shortcut_event(self, event, action):
        pattern = r"(?:^|;)i\.PAGE_NUMBER=(\d+)(?:;|$)"
        match = re.search(pattern, str(event.get("intent", "")))
        if match is None:
            return self._perform_external_event(event, action)
        page = int(match.group(1))
        self._start_scroll_transition(page)
        self._set_status(f"タップ: ページ {page + 1} へ移動")
        return True

    def _perform_external_event(self, _event, action):
        self._set_status(f"タップ: {action}（PCプレビューでは外部実行を省略）")
        return True

    def _trigger_tap_at(self, horizontal, vertical):
        memory = self.memory
        regions = reversed(memory.optional("_event_regions", []))
        matching = filter(
            lambda region: self._inside_region(region, horizontal, vertical),
            regions)
        region = next(matching, None)
        if region is None:
            self._set_status("この位置に再現可能なタップイベントはありません")
            return False
        handled = False
        for event in region[2]:
            handled = self._perform_preview_event(event) or handled
        if not handled:
            self._set_status("この位置に再現可能なタップイベントはありません")
        return handled

    @staticmethod
    def _inside_region(region, horizontal, vertical):
        _item, bounds, _events = region
        left, top, width, height = bounds
        return left <= horizontal <= left + width and top <= vertical <= top + height

class InteractionMixin(PreviewInteractionMixin):
    def _on_canvas_press(self, event):
        if self._interaction_enabled():
            self._start_interaction_drag(event)
            return
        scale = self.memory['_scale']
        horizontal, vertical = event.x / scale, event.y / scale
        hit = self._hit_item(horizontal, vertical)
        if hit is None:
            return
        self.memory['selected'] = hit
        self.memory['drag_state'] = (
            horizontal, vertical,
            float(hit.get("position_offset_x", 0) or 0),
            float(hit.get("position_offset_y", 0) or 0),
        )
        self._rebuild_tree(select=hit)
        self._render()
        self._build_props()

    def _start_interaction_drag(self, event):
        self.memory['_scroll_transition'] = None
        self.memory['interaction_drag'] = {
            "x": event.x, "y": event.y,
            "page": self.memory['preview_scroll'], "moved": False,
        }

    def _hit_item(self, horizontal, vertical):
        modules = reversed(self.memory['archive'].modules())
        candidates = filter(
            lambda item: self._inside_item(item, horizontal, vertical),
            modules)
        return next(candidates, None)

    def _inside_item(self, item, horizontal, vertical):
        bounds = self._bounds(item)
        if bounds is None:
            return False
        left, top, width, height = bounds
        return left <= horizontal <= left + width and top <= vertical <= top + height

    def cmd_device_res(self):
        current = "%dx%d" % self.memory['device_res']
        value = simpledialog.askstring(
            APP_TITLE, "プレビュー基準の端末解像度 (例 1080x2400):",
            initialvalue=current, parent=self)
        if not value:
            return
        match = re.match(r"\s*(\d+)\s*[xX×]\s*(\d+)\s*$", value)
        if match is None:
            messagebox.showerror(APP_TITLE, "形式が不正です (例: 1080x2400)")
            return
        self.memory['device_res'] = (
            int(match.group(1)), int(match.group(2)))
        self.memory['photo_cache'].clear()
        self._render()

    def _on_canvas_drag(self, event):
        if self._interaction_enabled() and self.memory['interaction_drag']:
            self._drag_preview(event)
            return
        if not self.memory['drag_state'] or self.memory['selected'] is None:
            return
        self._drag_selected_item(event)

    def _drag_preview(self, event):
        state = self.memory['interaction_drag']
        difference = event.x - state["x"]
        if abs(difference) >= 5:
            state["moved"] = True
        canvas_width = max(1, self.memory['canvas'].winfo_width())
        self._set_preview_scroll(state["page"] - difference / canvas_width)

    def _drag_selected_item(self, event):
        scale = self.memory['_scale']
        initial_horizontal, initial_vertical, offset_horizontal, offset_vertical = \
            self.memory['drag_state']
        difference_horizontal = event.x / scale - initial_horizontal
        difference_vertical = event.y / scale - initial_vertical
        anchor = self.memory['selected'].get("position_anchor", "TOPLEFT")
        horizontal_sign = self._horizontal_drag_sign(anchor)
        vertical_sign = self._vertical_drag_sign(anchor)
        selected = self.memory['selected']
        selected["position_offset_x"] = round(
            offset_horizontal + horizontal_sign * difference_horizontal, 1)
        selected["position_offset_y"] = round(
            offset_vertical + vertical_sign * difference_vertical, 1)
        self._render()

    @staticmethod
    def _horizontal_drag_sign(anchor):
        if anchor in ("TOPRIGHT", "CENTERRIGHT", "BOTTOMRIGHT"):
            return -1
        return 1

    @staticmethod
    def _vertical_drag_sign(anchor):
        if anchor in (
                "BOTTOMLEFT", "BOTTOM", "BOTTOMRIGHT",
                "CENTER", "CENTERLEFT", "CENTERRIGHT"):
            return -1
        return 1

    def _on_canvas_release(self, event):
        if self._interaction_enabled() and self.memory['interaction_drag']:
            self._release_interaction(event)
            return
        if self.memory['drag_state']:
            self.memory['drag_state'] = None
            self._mark_dirty()
            self._build_props()

    def _release_interaction(self, event):
        state = self.memory['interaction_drag']
        self.memory['interaction_drag'] = None
        if state["moved"]:
            self._start_scroll_transition(round(self.memory['preview_scroll']))
            return
        scale = self.memory['_scale']
        self._trigger_tap_at(event.x / scale, event.y / scale)
