from .support import *  # noqa: F401,F403


class PreviewTimeTests(unittest.TestCase):
    def test_timeline_changes_time_without_changing_date(self):
        source = datetime(2026, 7, 22, 8, 15, 30)
        timestamp = source.timestamp() * 1000.0

        changed = PreviewTimeline(timestamp).at_hour(18.5)
        actual = datetime.fromtimestamp(changed / 1000.0)

        self.assertEqual(actual.date(), source.date())
        self.assertEqual((actual.hour, actual.minute), (18, 30))

    def test_manual_scrubbing_stops_live_mode_and_renders(self):
        editor = _TimeEditor()
        editor.memory = ke.ApplicationMemory()
        live = Mock()
        variable = Mock()
        label = Mock()
        source = datetime(2026, 7, 22, 8, 0).timestamp() * 1000.0
        editor.memory["preview_ts"] = source
        editor.memory["preview_time_live_var"] = live
        editor.memory["preview_time_var"] = variable
        editor.memory["preview_time_label"] = label
        editor.memory["_time_after_id"] = "timer"
        editor.memory["_updating_time_control"] = False
        editor.after_cancel = Mock()
        editor._render = Mock()

        editor._on_preview_time_changed("18.5")

        actual = datetime.fromtimestamp(editor.memory["preview_ts"] / 1000.0)
        self.assertEqual((actual.hour, actual.minute), (18, 30))
        live.set.assert_called_once_with(False)
        editor.after_cancel.assert_called_once_with("timer")
        editor._render.assert_called_once_with()
        label.configure.assert_called_with(text="18:30:00")

    def test_live_tick_uses_current_time_and_schedules_one_second(self):
        editor = _TimeEditor()
        editor.memory = ke.ApplicationMemory()
        live = Mock()
        live.get.return_value = True
        editor.memory["preview_time_live_var"] = live
        editor.memory["preview_ts"] = 0
        editor.memory["_time_after_id"] = "previous"
        editor.memory["_updating_time_control"] = False
        editor.after = Mock(return_value="next")
        editor._render = Mock()

        with patch("klwp.ui.time_preview.time.time", return_value=100.5):
            editor._time_tick()

        self.assertEqual(editor.memory["preview_ts"], 100500)
        editor.after.assert_called_once_with(1000, editor._time_tick)
        self.assertEqual(editor.memory["_time_after_id"], "next")
        editor._render.assert_called_once_with()

class PreviewPageTests(unittest.TestCase):
    def test_page_count_uses_and_updates_klwp_xscreens(self):
        information = {"xscreens": 2}
        root_module = {"viewgroup_items": [{
            "internal_animations": [{"type": "SCROLL"}],
        }]}
        setting = PresetPageCount(information)

        self.assertEqual(
            PreviewPageCounter(root_module, information).count(), 3)
        self.assertTrue(setting.apply(5))
        self.assertEqual(information["xscreens"], 4)
        self.assertEqual(setting.specified(), 5)
        self.assertFalse(setting.apply(5))

    def test_sample_page_counts_follow_saved_values(self):
        expected = {"genoblanc.klwp": 3, "S041.klwp": 2}
        for name, count in expected.items():
            archive = ke.KlwpArchive()
            archive.load(SAMPLES / name)
            information = archive["preset"]["preset_info"]
            counter = PreviewPageCounter(
                archive.root_module(), information)
            self.assertEqual(counter.count(), count, name)

class PreviewZoomTests(unittest.TestCase):
    def test_selection_zoom_is_clamped_and_larger_than_fit(self):
        zoom = PreviewZoom.for_selection(
            (300.0, 500.0, 120.0, 80.0),
            (720.0, 1600.0), (420.0, 760.0))
        tiny = PreviewZoom.for_selection(
            (300.0, 500.0, 1.0, 1.0),
            (720.0, 1600.0), (420.0, 760.0))

        self.assertGreater(zoom.number(), 1.0)
        self.assertLessEqual(zoom.number(), PreviewZoom.MAXIMUM)
        self.assertEqual(tiny.number(), PreviewZoom.MAXIMUM)
        self.assertEqual(PreviewZoom(1.0).decreased().number(), 1.0)

    def test_zoomed_canvas_coordinates_include_crop_origin(self):
        view = PreviewZoomMixin()
        view.memory = ke.ApplicationMemory()
        view.memory["_scale"] = 2.0
        view.memory["_view_origin"] = (100.0, 50.0)
        event = type("Event", (), {"x": 20.0, "y": 30.0})()

        self.assertEqual(view._document_point(event), (60.0, 40.0))

    def test_canvas_zoom_clamps_crop_to_rendered_document(self):
        archive = ke.KlwpArchive()
        archive.new()
        renderer = object.__new__(ke.EditorApp)
        renderer.memory = ke.ApplicationMemory()
        renderer.memory["archive"] = archive
        renderer.memory["device_res"] = (1080, 2400)
        renderer.memory["preview_zoom"] = 2.0
        renderer.memory["_view_origin"] = (9999.0, 9999.0)
        canvas = Mock()

        rendered_size = renderer._configure_canvas(canvas)

        self.assertEqual(rendered_size, (684, 1520))
        self.assertEqual(renderer.memory["_viewport_size"], (420, 760))
        self.assertEqual(renderer.memory["_view_origin"], (264, 760))
        canvas.config.assert_called_once_with(width=420, height=760)

    def test_control_wheel_zoom_keeps_pointer_position(self):
        view = PreviewZoomMixin()
        view.CANVAS_W, view.CANVAS_H = 420, 760
        view.memory = ke.ApplicationMemory()
        view.memory["preview_zoom"] = 1.0
        view.memory["_scale"] = 0.475
        view.memory["_view_origin"] = (10.0, 20.0)
        view._doc_size = lambda: (720.0, 1600.0)
        view._render_zoom_preview = Mock()
        view.after = Mock(return_value="quality-render")
        view.after_cancel = Mock()
        event = type("Event", (), {
            "x": 20.0, "y": 30.0, "delta": 120, "num": 0,
        })()
        original_point = view._document_point(event)

        result = view._on_preview_zoom_wheel(event)

        self.assertEqual(result, "break")
        self.assertEqual(view.memory["preview_zoom"], 1.5)
        self.assertEqual(view.memory["_view_origin"], (25.0, 45.0))
        new_scale = PreviewZoom(1.5).scale(
            (720.0, 1600.0), (420.0, 760.0))
        new_horizontal = (event.x + 25.0) / new_scale
        new_vertical = (event.y + 45.0) / new_scale
        self.assertAlmostEqual(new_horizontal, original_point[0])
        self.assertAlmostEqual(new_vertical, original_point[1])
        view._render_zoom_preview.assert_called_once_with()
        view.after.assert_called_once_with(
            PreviewZoom.SETTLE_MILLISECONDS, view._finish_preview_zoom)

    def test_quality_render_is_replaced_until_wheel_stops(self):
        view = PreviewZoomMixin()
        view.memory = ke.ApplicationMemory()
        view.after = Mock(side_effect=("quality-1", "quality-2"))
        view.after_cancel = Mock()
        view._render = Mock()

        view._schedule_zoom_quality_render()
        view._schedule_zoom_quality_render()
        view._finish_preview_zoom()

        view.after_cancel.assert_called_once_with("quality-1")
        self.assertIsNone(view.memory["_zoom_render_after_id"])
        view._render.assert_called_once_with()

    @unittest.skipUnless(ke.HAS_PIL, "Pillow is required")
    def test_cached_preview_scales_only_requested_viewport(self):
        source = ke.Image.new("RGB", (342, 760), "#123456")

        preview = CachedPreviewImage(source).viewport(
            (1368, 3040), (420, 760), (200, 400))

        self.assertEqual(preview.size, (420, 760))
        self.assertEqual(preview.getpixel((200, 300)), (18, 52, 86))

    @unittest.skipUnless(ke.HAS_TK and ke.HAS_PIL, "Tkinter/Pillow required")
    def test_quality_render_is_reused_by_wheel_preview(self):
        archive = ke.KlwpArchive()
        archive.new()
        renderer = object.__new__(ke.EditorApp)
        renderer.memory = ke.ApplicationMemory()
        renderer.memory["archive"] = archive
        renderer.memory["photo_cache"] = {}
        renderer.memory["font_cache"] = {}
        renderer.memory["device_res"] = (1080, 2400)
        renderer.memory["preview_zoom"] = 1.0
        renderer.memory["_view_origin"] = (0.0, 0.0)
        renderer.memory["selected"] = None
        renderer.memory["canvas"] = Mock()
        with patch("klwp.render.canvas.ImageTk.PhotoImage"):
            renderer._render()
        quality = renderer.memory["_quality_preview"]
        renderer.memory["preview_zoom"] = 1.5
        with patch("klwp.render.zoom.ImageTk.PhotoImage"):
            renderer._render_zoom_preview()

        self.assertEqual(quality.size, (342, 760))
        self.assertIs(renderer.memory["_quality_preview"], quality)
        self.assertEqual(renderer.memory["_viewport_size"], (420, 760))

class PreviewPanTests(unittest.TestCase):
    def test_grabbed_background_moves_opposite_to_pointer(self):
        pan = PreviewPan((100.0, 200.0), (300.0, 400.0))

        origin = pan.moved_origin((140.0, 170.0))

        self.assertEqual(origin, (260.0, 430.0))

    @unittest.skipUnless(ke.HAS_TK and ke.HAS_PIL, "Tkinter/Pillow required")
    def test_background_drag_pans_clamps_and_avoids_quality_redraw(self):
        renderer = object.__new__(ke.EditorApp)
        renderer.memory = ke.ApplicationMemory()
        renderer.memory["canvas"] = Mock()
        renderer.memory["device_res"] = (1080, 2400)
        renderer.memory["preview_zoom"] = 2.0
        renderer.memory["_scale"] = 0.95
        renderer.memory["_doc"] = (720.0, 1600.0)
        renderer.memory["_view_origin"] = (0.0, 0.0)
        renderer.memory["_view_pan_state"] = None
        renderer.memory["_zoom_render_after_id"] = None
        renderer.memory["_quality_preview"] = ke.Image.new(
            "RGBA", (684, 1520), "#123456")
        renderer.memory["_item_bounds"] = []
        renderer.memory["resize_state"] = None
        renderer.memory["drag_state"] = None
        renderer.memory["selected"] = None
        renderer.after = Mock()
        press = type("Event", (), {"x": 100.0, "y": 100.0})()
        beyond_edge = type("Event", (), {"x": 150.0, "y": 150.0})()
        return_from_edge = type("Event", (), {"x": 140.0, "y": 140.0})()

        with patch("klwp.render.zoom.ImageTk.PhotoImage"):
            renderer._on_canvas_press(press)
            renderer._on_canvas_drag(beyond_edge)
            renderer._on_canvas_drag(return_from_edge)
            renderer._on_canvas_release(return_from_edge)

        self.assertEqual(renderer.memory["_view_origin"], (10, 10))
        self.assertIsNone(renderer.memory["_view_pan_state"])
        renderer.after.assert_not_called()

class CanvasSelectionTests(unittest.TestCase):
    def test_canvas_item_click_does_not_select_when_tree_is_unselected(self):
        renderer = object.__new__(ke.EditorApp)
        renderer.memory = ke.ApplicationMemory()
        renderer.memory["selected"] = None
        renderer.memory["resize_state"] = None
        renderer.memory["drag_state"] = None
        renderer.memory["_scale"] = 1.0
        renderer.memory["_view_origin"] = (0.0, 0.0)
        item = ke.make_module("shape")
        renderer.memory["_item_bounds"] = [(item, (10.0, 10.0, 80.0, 80.0))]
        renderer._start_preview_pan = Mock()
        event = type("Event", (), {"x": 40.0, "y": 40.0})()

        renderer._on_canvas_press(event)

        self.assertIsNone(renderer.memory["selected"])
        self.assertIsNone(renderer.memory["drag_state"])
        renderer._start_preview_pan.assert_not_called()

    def test_tree_selected_item_can_be_moved_on_canvas(self):
        archive = ke.KlwpArchive()
        archive.new()
        selected = ke.make_module("shape")
        archive.modules().append(selected)
        renderer = object.__new__(ke.EditorApp)
        renderer.memory = ke.ApplicationMemory()
        renderer.memory["archive"] = archive
        renderer.memory["photo_cache"] = {}
        renderer.memory["font_cache"] = {}
        renderer.memory["device_res"] = (1080, 2400)
        renderer.render_to_image(360, 800)
        renderer.memory["selected"] = selected
        renderer.memory["resize_state"] = None
        renderer.memory["drag_state"] = None
        renderer.memory["_view_pan_state"] = None
        renderer.memory["_view_origin"] = (0.0, 0.0)
        initial_horizontal = selected["position_offset_x"]
        initial_vertical = selected["position_offset_y"]
        left, top, width, height = renderer._bounds(selected)
        scale = renderer.memory["_scale"]
        press = type("Event", (), {
            "x": (left + width / 2.0) * scale,
            "y": (top + height / 2.0) * scale,
        })()
        renderer._on_canvas_press(press)
        renderer._render = Mock()
        drag = type("Event", (), {
            "x": press.x + 10.0 * scale,
            "y": press.y + 20.0 * scale,
        })()

        renderer._on_canvas_drag(drag)

        self.assertEqual(
            selected["position_offset_x"], initial_horizontal + 10.0)
        self.assertEqual(
            selected["position_offset_y"], initial_vertical + 20.0)

    def test_tree_selected_item_can_be_resized_on_canvas(self):
        archive = ke.KlwpArchive()
        archive.new()
        selected = ke.make_module("shape")
        archive.modules().append(selected)
        renderer = object.__new__(ke.EditorApp)
        renderer.memory = ke.ApplicationMemory()
        renderer.memory["archive"] = archive
        renderer.memory["photo_cache"] = {}
        renderer.memory["font_cache"] = {}
        renderer.memory["device_res"] = (1080, 2400)
        renderer.render_to_image(360, 800)
        renderer.memory["selected"] = selected
        renderer.memory["resize_state"] = None
        renderer.memory["drag_state"] = None
        renderer.memory["_view_pan_state"] = None
        renderer.memory["_view_origin"] = (0.0, 0.0)
        initial_width = selected["shape_width"]
        initial_height = selected["shape_height"]
        left, top, width, height = renderer._bounds(selected)
        scale = renderer.memory["_scale"]
        press = type("Event", (), {
            "x": (left + width) * scale,
            "y": (top + height) * scale,
        })()

        renderer._on_canvas_press(press)
        renderer._render = Mock()
        drag = type("Event", (), {
            "x": press.x + 10.0 * scale,
            "y": press.y + 20.0 * scale,
        })()
        renderer._on_canvas_drag(drag)

        self.assertEqual(selected["shape_width"], initial_width + 10.0)
        self.assertEqual(selected["shape_height"], initial_height + 20.0)

    def test_canvas_click_on_other_item_keeps_tree_selection(self):
        renderer = object.__new__(ke.EditorApp)
        renderer.memory = ke.ApplicationMemory()
        selected = ke.make_module("shape")
        other = ke.make_module("text")
        renderer.memory["selected"] = selected
        renderer.memory["drag_state"] = None
        renderer.memory["_scale"] = 1.0
        renderer.memory["_view_origin"] = (0.0, 0.0)
        renderer.memory["_item_bounds"] = [(other, (10.0, 10.0, 80.0, 80.0))]
        renderer._start_resize = Mock(return_value=False)
        renderer._inside_item = Mock(return_value=False)
        renderer._start_preview_pan = Mock()
        event = type("Event", (), {"x": 40.0, "y": 40.0})()

        renderer._on_canvas_press(event)

        self.assertIs(renderer.memory["selected"], selected)
        self.assertIsNone(renderer.memory["drag_state"])
        renderer._start_preview_pan.assert_not_called()

class ResizeTests(unittest.TestCase):
    def test_handle_hit_detection_includes_edges_and_corners(self):
        bounds = (100.0, 200.0, 300.0, 150.0)

        self.assertEqual(ResizeHandleSet.hit(bounds, 100, 200, 8), "NW")
        self.assertEqual(ResizeHandleSet.hit(bounds, 250, 200, 8), "N")
        self.assertEqual(ResizeHandleSet.hit(bounds, 400, 275, 8), "E")
        self.assertIsNone(ResizeHandleSet.hit(bounds, 250, 275, 8))

    def test_shape_resize_changes_width_and_height_independently(self):
        item = ke.make_shape_module("長方形")
        session = ResizeSession(
            item, "SE", (200.0, 100.0),
            (0.0, 0.0, 200.0, 100.0), (200.0, 100.0))

        target = session.apply(260.0, 140.0)

        self.assertEqual(target, (0.0, 0.0, 260.0, 140.0))
        self.assertEqual(item["shape_width"], 260.0)
        self.assertEqual(item["shape_height"], 140.0)

    def test_bitmap_resize_preserves_source_aspect_ratio(self):
        item = ke.make_module("bitmap")
        item["bitmap_width"] = 200.0
        session = ResizeSession(
            item, "S", (100.0, 100.0),
            (0.0, 0.0, 200.0, 100.0), (200.0, 100.0))

        left, top, width, height = session.apply(100.0, 150.0)

        self.assertEqual((left, top), (-50.0, 0.0))
        self.assertEqual(width / height, 2.0)
        self.assertEqual(item["bitmap_width"], 300.0)
        self.assertNotIn("bitmap_height", item)

class PositioningTests(unittest.TestCase):
    def test_root_movement_changes_anchor_relative_offsets(self):
        item = {
            "position_anchor": "BOTTOMRIGHT",
            "position_offset_x": 20.0, "position_offset_y": 30.0,
        }

        PositionMutation(item, True).move_by(15.0, 25.0)

        self.assertEqual(item["position_offset_x"], 5.0)
        self.assertEqual(item["position_offset_y"], 5.0)
        self.assertNotIn("position_padding_left", item)

    def test_nested_movement_changes_margins_instead_of_offsets(self):
        item = {"position_anchor": "CENTER"}

        PositionMutation(item, False).move_by(15.0, -25.0)

        self.assertEqual(item["position_padding_left"], 15.0)
        self.assertEqual(item["position_padding_right"], -15.0)
        self.assertEqual(item["position_padding_top"], -25.0)
        self.assertEqual(item["position_padding_bottom"], 25.0)
        self.assertNotIn("position_offset_x", item)

class SnapTests(unittest.TestCase):
    def test_document_ruler_snaps_nearest_item_edge(self):
        targets = SnapTargets.from_layout((720.0, 1200.0), (), None)
        engine = SnapEngine(targets, 3.0)

        result = engine.apply((45.0, 40.0, 50.0, 20.0), 4.0, 0.0)

        self.assertEqual(result.movement(), (5.0, 0.0))
        self.assertEqual(result.guides(), (("vertical", 100.0),))

    def test_other_item_edges_and_centers_are_snap_targets(self):
        selected = {}
        other = {}
        targets = SnapTargets.from_layout(
            (720.0, 1200.0),
            ((selected, (100.0, 100.0, 100.0, 50.0)),
             (other, (330.0, 200.0, 80.0, 80.0))),
            selected)

        result = SnapEngine(targets, 7.0).apply(
            (150.0, 100.0, 100.0, 50.0), 74.0, 108.0)

        self.assertEqual(result.movement(), (80.0, 115.0))
        self.assertEqual(
            result.guides(),
            (("vertical", 330.0), ("horizontal", 240.0)))

    def test_movement_outside_tolerance_is_not_changed(self):
        targets = SnapTargets((300.0,), (400.0,))

        result = SnapEngine(targets, 5.0).apply(
            (10.0, 20.0, 50.0, 50.0), 17.0, 19.0)

        self.assertEqual(result.movement(), (17.0, 19.0))
        self.assertEqual(result.guides(), ())

    def test_drag_keeps_raw_movement_and_defers_snap_correction(self):
        selected = {}
        editor = Mock()
        editor.memory = ke.ApplicationMemory()
        editor.memory["_doc"] = (720.0, 1200.0)
        editor.memory["_item_bounds"] = ((selected, (45.0, 40.0, 50.0, 20.0)),)
        editor._guides_enabled.return_value = True
        editor._bounds.return_value = (45.0, 40.0, 50.0, 20.0)

        movement = InteractionMixin._guided_movement(
            editor, selected, 4.0, 0.0, 1.0)

        self.assertEqual(movement, (4.0, 0.0))
        self.assertEqual(editor.memory["snap_correction"], (1.0, 0.0))
        self.assertEqual(
            editor.memory["snap_guides"], (("vertical", 100.0),))

    def test_release_applies_deferred_snap_correction_once(self):
        selected = {}
        mutation = Mock()
        editor = Mock()
        editor.memory = ke.ApplicationMemory()
        editor.memory["selected"] = selected
        editor.memory["snap_correction"] = (1.0, -2.0)
        editor._position_mutation.return_value = mutation

        InteractionMixin._commit_drag_snap(editor)

        editor._position_mutation.assert_called_once_with(selected)
        mutation.move_by.assert_called_once_with(1.0, -2.0)
