"""Connect resize geometry to preview mouse interaction."""

from ..resize import ResizeHandleSet, ResizeSession
from ..shared import *  # noqa: F401,F403


class ResizeInteractionMixin:
    HANDLE_TOLERANCE = 8.0

    def _resize_handle_at(self, horizontal, vertical):
        memory = self.memory
        item = memory.optional("selected")
        if not ResizeHandleSet.supports(item):
            return None
        bounds = self._bounds(item)
        if bounds is None:
            return None
        scale = memory.optional("_scale", 1.0)
        tolerance = self.HANDLE_TOLERANCE / max(scale, 0.001)
        return ResizeHandleSet.hit(bounds, horizontal, vertical, tolerance)

    def _start_resize(self, horizontal, vertical):
        handle = self._resize_handle_at(horizontal, vertical)
        if handle is None:
            return False
        memory = self.memory
        item = memory["selected"]
        bounds = self._bounds(item)
        global_values = self._root_globals()
        base_size = self._base_item_size(item, global_values)
        memory["resize_state"] = ResizeSession(
            item, handle, (horizontal, vertical), bounds, base_size)
        memory["drag_state"] = None
        self._set_status("縁をドラッグしてサイズを変更")
        return True

    def _on_canvas_motion(self, event):
        memory = self.memory
        canvas = memory["canvas"]
        if self._interaction_enabled():
            canvas.configure(cursor="")
            return
        if memory.optional("_view_pan_state") is not None:
            canvas.configure(cursor="fleur")
            return
        horizontal, vertical = self._document_point(event)
        handle = self._resize_handle_at(horizontal, vertical)
        canvas.configure(cursor=ResizeHandleSet.cursor(handle))

    def _drag_resize(self, event):
        memory = self.memory
        state = memory.optional("resize_state")
        if state is None:
            return False
        horizontal, vertical = self._document_point(event)
        target = state.apply(horizontal, vertical)
        self._align_resized_item(state, target)
        self._render()
        return True

    def _align_resized_item(self, state, target):
        item = state.selected_item()
        self._refresh_nested_bounds(item)
        actual = self._bounds(item)
        if actual is None:
            return
        target_left, target_top, _target_width, _target_height = target
        actual_left, actual_top, _actual_width, _actual_height = actual
        difference_horizontal = target_left - actual_left
        difference_vertical = target_top - actual_top
        mutation = self._position_mutation(item)
        mutation.move_by(difference_horizontal, difference_vertical)

    def _refresh_nested_bounds(self, item):
        memory = self.memory
        archive = memory["archive"]
        if item in archive.modules():
            return
        document_width, document_height = memory["_doc"]
        scale = memory["_scale"]
        pixel_width = max(1, int(document_width * scale))
        pixel_height = max(1, int(document_height * scale))
        self.render_to_image(pixel_width, pixel_height)

    def _finish_resize(self):
        memory = self.memory
        state = memory.optional("resize_state")
        if state is None:
            return False
        memory["resize_state"] = None
        memory["canvas"].configure(cursor="")
        if not state.changed():
            return True
        self._mark_dirty()
        self._build_props()
        self._set_status("サイズを変更しました")
        return True
