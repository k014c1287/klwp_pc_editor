import copy
import io
import json
import tempfile
import unittest
from unittest.mock import Mock, patch
import zipfile
from datetime import datetime
from pathlib import Path

import klwp_editor as ke
from klwp.ui.property_panel import AnchorChoices, PropertyPanelBuilder
from klwp.ui.color_control import KlwpColor
from klwp.resize import ResizeHandleSet, ResizeSession
from klwp.positioning import PositionMutation
from klwp.background import BackgroundImageBinding, BitmapGlobalCollection
from klwp.ui.global_dialog import GlobalEntryValues
from klwp.ui.setting_values import TouchActionValues
from klwp.ui.document import DocumentMixin
from klwp.ui.window import EditorWindowBuilder
from klwp.adb import AdbDevices, AdbTransfer
from klwp.preview.pages import PresetPageCount, PreviewPageCounter
from klwp.preview.zoom import CachedPreviewImage, PreviewPan, PreviewZoom
from klwp.ui.tree import ModuleTreePresentation
from klwp.ui.tree_drag import TreeDragMixin, TreeReorder
from klwp.ui.zoom import PreviewZoomMixin


ROOT = Path(__file__).resolve().parent
SAMPLES = ROOT / "sample"


class _TreeEditor(DocumentMixin, TreeDragMixin):
    pass


class FormulaTests(unittest.TestCase):
    def test_arithmetic_condition_and_global(self):
        globals_ = {
            "width": {"value": 7},
            "color": {"value": "#FFAABBCC"},
        }
        self.assertEqual(ke.eval_formula("$gv(width)*10+2$", globals_), 72)
        self.assertEqual(ke.eval_formula("$gv(color)$", globals_), "#FFAABBCC")
        self.assertFalse(ke.eval_formula(
            "$if(bi(charging)=1, true, false)$", globals_))
        self.assertEqual(ke.eval_formula("$mi(percent)*140/100$"), 56)

    def test_text_formula_and_markup(self):
        self.assertEqual(
            ke.sample_eval("H: $wf(max, 0)$°$wi(tempu)$"), "H: 29°C")
        self.assertEqual(
            ke.sample_eval("[b]TYPE WHALE[/b]"), "TYPE WHALE")

    def test_extended_math_text_color_and_regex_functions(self):
        self.assertEqual(ke.eval_formula("$mu(sqrt, 81)$"), 9)
        self.assertEqual(ke.eval_formula('$tc(up, "Abc")$'), "ABC")
        self.assertEqual(
            ke.eval_formula('$if("Cloudy" ~= "cloud", yes, no)$'), "yes")
        self.assertEqual(
            ke.eval_formula("$ce(#FF0000, alpha, 50)$"), "#80FF0000")

    def test_formula_functions_use_editable_preview_values(self):
        values = {
            "__preview__": {
                "battery": {"level": 12.0},
                "weather": {"temp": -3.0},
                "media": {"title": "Edited Song"},
                "location": {"loc": "Sapporo"},
            },
        }

        self.assertEqual(ke.eval_formula("$bi(level)$", values), 12.0)
        self.assertEqual(ke.eval_formula("$wi(temp)$", values), -3.0)
        self.assertEqual(ke.eval_formula("$mi(title)$", values), "Edited Song")
        self.assertEqual(ke.eval_formula("$li(loc)$", values), "Sapporo")


class ShapeTemplateTests(unittest.TestCase):
    def test_all_dropdown_shape_types_create_valid_modules(self):
        self.assertEqual(len(ke.SHAPE_TYPE_OPTIONS), 11)
        for name in ke.SHAPE_TYPE_OPTIONS:
            module = ke.make_shape_module(name)
            self.assertEqual(module["internal_type"], "ShapeModule", name)
            self.assertGreater(module["shape_width"], 0, name)
            self.assertGreater(module["shape_height"], 0, name)
            if name == "Path":
                self.assertEqual(module["shape_type"], "PATH")
                self.assertTrue(module["shape_path"].endswith("Z"))

    def test_shape_internal_types_match_shape_sample(self):
        archive = ke.KlwpArchive()
        archive.load(SAMPLES / "図形一覧.klwp")

        actual = [item.get("shape_type") for item in archive.modules()
                  if item.get("internal_type") == "ShapeModule"]
        expected = [ke.make_shape_module(label).get("shape_type")
                    for label in ke.SHAPE_TYPE_OPTIONS]
        self.assertCountEqual(actual, expected)


class PropertyPanelTests(unittest.TestCase):
    def test_anchor_choices_use_japanese_labels_and_klwp_values(self):
        expected_labels = (
            "左上", "上", "右上", "左中央", "中央",
            "右中央", "左下", "下", "右下",
        )
        expected_values = (
            "TOPLEFT", "TOP", "TOPRIGHT", "CENTERLEFT", "CENTER",
            "CENTERRIGHT", "BOTTOMLEFT", "BOTTOM", "BOTTOMRIGHT",
        )

        self.assertEqual(AnchorChoices.display_values(), expected_labels)
        self.assertEqual(
            tuple(map(AnchorChoices.to_internal, expected_labels)),
            expected_values)
        self.assertEqual(
            tuple(map(AnchorChoices.to_display, expected_values)),
            expected_labels)
        self.assertEqual(AnchorChoices.to_display(None), "中央")
        self.assertEqual(AnchorChoices.to_internal(""), "CENTER")

    def test_position_fields_follow_root_and_nested_contexts(self):
        archive = ke.KlwpArchive()
        archive.new()
        root_item = ke.make_module("layer")
        nested_item = ke.make_module("shape")
        root_item["viewgroup_items"].append(nested_item)
        archive.modules().append(root_item)
        owner = type("Owner", (), {"memory": {"archive": archive}})()
        root_builder = PropertyPanelBuilder(owner, root_item)
        nested_builder = PropertyPanelBuilder(owner, nested_item)

        self.assertTrue(root_builder._position_field_is_visible(
            "position_offset_x"))
        self.assertFalse(nested_builder._position_field_is_visible(
            "position_offset_x"))
        self.assertTrue(nested_builder._position_field_is_visible(
            "position_padding_left"))

    def test_visual_color_value_preserves_rgb_and_opacity(self):
        color = KlwpColor("#80aabbcc")

        self.assertEqual(color.encoded(), "#80AABBCC")
        self.assertEqual(color.chooser_color(), "#AABBCC")
        self.assertEqual(color.opacity_percentage(), 50)
        color.replace_chooser_color("#102030")
        self.assertEqual(color.encoded(), "#80102030")
        color.replace_opacity_percentage(100)
        self.assertEqual(color.encoded(), "#FF102030")

    def test_visual_color_value_accepts_rgb_and_invalid_input(self):
        self.assertEqual(KlwpColor("#123456").encoded(), "#FF123456")
        self.assertEqual(KlwpColor("invalid").encoded(), "#FFFFFFFF")

    def test_non_switch_global_values_are_converted_without_losing_fields(self):
        original = {"index": 3, "type": "NUMBER", "min": 0, "max": 720}

        number = GlobalEntryValues.update(
            original, "NUMBER", "size", "62.5", "")
        color = GlobalEntryValues.update(
            {"index": 4}, "COLOR", "accent", "#80aabbcc", "")

        self.assertEqual(number["value"], 62.5)
        self.assertEqual((number["min"], number["max"]), (0, 720))
        self.assertEqual(color["value"], "#80AABBCC")

    def test_global_editor_creates_switch_values(self):
        switch = GlobalEntryValues.create("toggle", "SWITCH", "on", 1)

        self.assertEqual(switch["type"], "SWITCH")
        self.assertEqual(switch["value"], 1)

    def test_external_touch_actions_use_klwp_event_keys(self):
        launched = TouchActionValues.update(
            {"unknown": 7}, "LAUNCH_APP", intent="intent:#Intent;end")
        music = TouchActionValues.update(
            {"intent": "old", "switch": "old"}, "MUSIC",
            music_action="NEXT")

        self.assertEqual(launched["intent"], "intent:#Intent;end")
        self.assertEqual(launched["unknown"], 7)
        self.assertNotIn("switch", launched)
        self.assertEqual(music["music_action"], "NEXT")
        self.assertNotIn("intent", music)
        self.assertNotIn("switch", music)


class ModuleTreeTests(unittest.TestCase):
    def test_drag_reorder_moves_items_before_and_after_targets(self):
        back = {"internal_title": "back"}
        middle = {"internal_title": "middle"}
        front = {"internal_title": "front"}
        siblings = [back, middle, front]

        self.assertTrue(TreeReorder.move(siblings, back, front, True))
        self.assertEqual(siblings, [middle, front, back])
        self.assertTrue(TreeReorder.move(siblings, back, middle, False))
        self.assertEqual(siblings, [back, middle, front])
        self.assertFalse(TreeReorder.move(siblings, middle, middle, True))

    def test_tree_presentation_explains_frontmost_priority(self):
        hidden = {
            "internal_type": "ShapeModule", "internal_title": "panel",
            "config_visible": False,
        }

        self.assertEqual(ModuleTreePresentation.title(hidden), "panel")
        self.assertEqual(ModuleTreePresentation.kind(hidden), "図形")
        self.assertEqual(ModuleTreePresentation.priority(2, 3), "1・最前面")
        self.assertEqual(ModuleTreePresentation.tags(hidden), ("hidden",))

    def test_clearing_layer_selection_restores_root_add_target(self):
        archive = ke.KlwpArchive()
        archive.new()
        layer = ke.make_module("layer")
        archive.modules().append(layer)
        tree = Mock()
        tree.selection.side_effect = [("layer-row",), ()]
        tree.identify_row.return_value = ""
        editor = _TreeEditor()
        editor.memory = ke.ApplicationMemory()
        editor.memory['archive'] = archive
        editor.memory['tree'] = tree
        editor.memory['tree_map'] = {}
        editor.memory['selected'] = layer
        editor.memory['drag_state'] = object()
        editor.memory['resize_state'] = object()
        editor.memory['status'] = Mock()
        editor._render = Mock()
        editor._build_props = Mock()

        result = editor._on_tree_press(
            type("Event", (), {"y": 500})())

        self.assertEqual(result, "break")
        self.assertIsNone(editor.memory['tree_drag'])
        tree.selection_remove.assert_called_once_with("layer-row")
        self.assertIsNone(editor.memory['selected'])
        self.assertIs(editor._target_list(), archive.modules())

    def test_delete_shortcut_removes_item_without_confirmation(self):
        archive = ke.KlwpArchive()
        archive.new()
        item = ke.make_module("text")
        archive.modules().append(item)
        editor = DocumentMixin()
        editor.memory = ke.ApplicationMemory()
        editor.memory['tree'] = Mock()
        editor.memory['tree'].selection.return_value = ("item-row",)
        editor.memory['tree_map'] = {
            "item-row": (item, archive.modules()),
        }
        editor.memory['selected'] = item
        editor.memory['archive'] = archive
        editor._mark_dirty = Mock()
        editor._refresh_all = Mock()

        with patch(
                "klwp.ui.document.messagebox.askyesno") as confirmation:
            result = editor._on_delete_shortcut()

        self.assertEqual(result, "break")
        confirmation.assert_not_called()
        self.assertEqual(archive.modules(), [])
        self.assertIsNone(editor.memory['selected'])
        editor._mark_dirty.assert_called_once_with()
        editor._refresh_all.assert_called_once_with()


class KeyboardShortcutTests(unittest.TestCase):
    def test_control_z_and_control_y_bind_to_history_commands(self):
        owner = Mock()

        EditorWindowBuilder(owner)._keyboard_shortcuts()

        owner.bind_all.assert_any_call(
            "<Control-z>", owner._on_undo_shortcut)
        owner.bind_all.assert_any_call(
            "<Control-y>", owner._on_redo_shortcut)
        owner.bind_all.assert_any_call(
            "<Control-Shift-Z>", owner._on_redo_shortcut)


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


class BackgroundTests(unittest.TestCase):
    def test_binding_updates_background_fields_without_losing_other_formulas(self):
        root_module = {
            "internal_formulas": {"background_color": "$gv(color)$"},
            "internal_globals": {"background_color": "color"},
        }
        binding = BackgroundImageBinding(root_module)

        binding.apply("$gv(day)$", "day")

        self.assertEqual(binding.form_values(), ("$gv(day)$", "day"))
        self.assertEqual(
            root_module["internal_formulas"]["background_color"], "$gv(color)$")
        binding.apply("", "")
        self.assertNotIn("background_bitmap", root_module["internal_formulas"])
        self.assertNotIn("background_bitmap", root_module["internal_globals"])

    def test_bitmap_global_collection_adds_archive_references(self):
        root_module = {"globals_list": {
            "caption": {"index": 1, "type": "TEXT", "value": "hello"},
        }}
        globals_collection = BitmapGlobalCollection(root_module)

        globals_collection.add("day", "kfile://provider/bitmaps/IMGday")
        globals_collection.add("night", "kfile://provider/bitmaps/IMGnight")

        self.assertEqual(globals_collection.names(), ("day", "night"))
        self.assertEqual(
            root_module["globals_list"]["night"]["type"], "BITMAP")


class ArchiveTests(unittest.TestCase):
    def test_adb_transfer_selects_device_and_pushes_saved_preset(self):
        output = "List of devices attached\nABC123\tdevice\n"
        completed = type(
            "Completed", (), {"returncode": 0, "stdout": output, "stderr": ""})()
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "wallpaper.klwp"
            source.write_bytes(b"preset")
            with patch("klwp.adb.subprocess.run", return_value=completed) as run:
                device, destination = AdbTransfer("adb", source).send()

        self.assertEqual(AdbDevices.connected(output), ("ABC123",))
        self.assertEqual(device, "ABC123")
        self.assertEqual(destination, "/sdcard/Kustom/wallpapers/wallpaper.klwp")
        commands = [invocation.args[0] for invocation in run.call_args_list]
        self.assertEqual(commands[0], ["adb", "devices"])
        self.assertEqual(commands[1][-4:], ["shell", "mkdir", "-p", "/sdcard/Kustom/wallpapers"])
        self.assertEqual(commands[2][3], "push")

    def test_imported_bitmap_uses_klwp_identifier_and_zip_flags(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            bitmap_path = directory / "source.png"
            bitmap_data = b"bitmap test payload"
            bitmap_path.write_bytes(bitmap_data)
            output_path = directory / "bitmap.klwp"
            archive = ke.KlwpArchive()
            archive.new()

            reference = archive.add_bitmap(bitmap_path)

            self.assertRegex(
                reference,
                r"^kfile://org\.kustom\.provider/bitmaps/IMG[0-9a-f]{32}$")
            archive_name = "bitmaps/" + reference.rsplit("/", 1)[-1]
            self.assertEqual(archive["bitmaps"][archive_name], bitmap_data)
            archive.save(output_path)
            with zipfile.ZipFile(output_path) as archive_file:
                self.assertEqual(archive_file.read(archive_name), bitmap_data)
                for entry in archive_file.infolist():
                    self.assertEqual(entry.flag_bits & 0x808, 0x808)

    def test_save_migrates_legacy_short_bitmap_identifier(self):
        old_name = "bitmaps/IMG0123456789abcdef0123456789ab"
        old_reference = "kfile://org.kustom.provider/" + old_name
        archive = ke.KlwpArchive()
        archive.new()
        archive["bitmaps"][old_name] = b"legacy bitmap"
        module = ke.make_module("bitmap")
        module["bitmap_bitmap"] = old_reference
        archive.modules().append(module)

        with tempfile.TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory) / "migrated.klwp"
            archive.save(output_path)
            with zipfile.ZipFile(output_path) as archive_file:
                names = archive_file.namelist()
                preset = json.loads(archive_file.read("preset.json"))

        bitmap_names = [name for name in names
                        if name.startswith("bitmaps/")]
        self.assertNotIn(old_name, bitmap_names)
        self.assertEqual(len(bitmap_names), 1)
        self.assertRegex(bitmap_names[0], r"^bitmaps/IMG[0-9a-f]{32}$")
        saved_module = preset["preset_root"]["viewgroup_items"][0]
        self.assertEqual(
            saved_module["bitmap_bitmap"],
            "kfile://org.kustom.provider/" + bitmap_names[0])

    def test_sample_archives_and_module_counts(self):
        expected = {
            "genoblanc.klwp": 46,
            "S041.klwp": 198,
            "sizuka_home.klwp": 112,
        }
        for name, count in expected.items():
            archive = ke.KlwpArchive()
            archive.load(SAMPLES / name)
            modules = []

            def walk(value):
                if isinstance(value, dict):
                    if value.get("internal_type") and \
                            value.get("internal_type") != "RootLayerModule":
                        modules.append(value)
                    for child in value.values():
                        walk(child)
                elif isinstance(value, list):
                    for child in value:
                        walk(child)

            walk(archive.root_module())
            self.assertEqual(len(modules), count, name)

    def test_official_legacy_samples_cover_additional_versions(self):
        expected = {
            "official_v1_Analog.klwp": 1,
            "official_v3_CpuAndMem.klwp": 3,
            "official_v4_BunchOfText.klwp": 4,
            "official_v5_BlurClock.klwp": 5,
        }

        for name, version in expected.items():
            archive = ke.KlwpArchive()
            archive.load(SAMPLES / name)
            information = archive["preset"]["preset_info"]
            self.assertEqual(information["version"], version, name)
            self.assertGreater(len(archive.modules()), 0, name)

    def test_round_trip_preserves_json_and_assets(self):
        for source in sorted(SAMPLES.glob("*.klwp")):
            archive = ke.KlwpArchive()
            archive.load(source)
            before = copy.deepcopy(archive["preset"])
            assets = (archive["extras"].copy(), archive["fonts"].copy(),
                      archive["bitmaps"].copy())
            with tempfile.TemporaryDirectory() as tmp:
                output = Path(tmp) / source.name
                archive.save(output)
                loaded = ke.KlwpArchive()
                loaded.load(output)
                before["preset_info"]["ts"] = \
                    archive["preset"]["preset_info"]["ts"]
                self.assertEqual(before, loaded["preset"], source.name)
                self.assertEqual(assets, (loaded["extras"], loaded["fonts"],
                                          loaded["bitmaps"]), source.name)
                with zipfile.ZipFile(output) as zf:
                    self.assertIsNone(zf.testzip(), source.name)


class _WidgetStub:
    def __init__(self):
        self.options = {}

    def config(self, **kwargs):
        self.options.update(kwargs)

    configure = config


@unittest.skipUnless(ke.HAS_TK, "Tkinter required")
class HistoryTests(unittest.TestCase):
    @staticmethod
    def editor():
        editor = object.__new__(ke.EditorApp)
        editor.memory = ke.ApplicationMemory()
        editor.memory["archive"] = ke.KlwpArchive()
        editor.memory["archive"].new()
        editor.memory["selected"] = None
        editor.memory["drag_state"] = None
        editor.memory["photo_cache"] = {}
        editor.memory["font_cache"] = {}
        editor.memory["dirty"] = False
        editor.memory["history"] = ke.HistoryTimeline(editor.HISTORY_LIMIT)
        editor.memory["undo_button"] = _WidgetStub()
        editor.memory["redo_button"] = _WidgetStub()
        editor.memory["status"] = _WidgetStub()
        editor.title = lambda _title: None
        editor._refresh_all = lambda select=None: None
        editor._reset_history()
        return editor

    def test_undo_redo_and_clean_state(self):
        editor = self.editor()
        item = ke.make_module("text")
        editor.memory['archive'].modules().append(item)
        editor._mark_dirty()

        self.assertTrue(editor.memory['dirty'])
        self.assertEqual(editor.memory['history'].undo_count(), 1)
        self.assertEqual(editor.memory['undo_button'].options["state"], "normal")

        self.assertEqual(editor._on_undo_shortcut(), "break")
        self.assertEqual(editor.memory['archive'].modules(), [])
        self.assertFalse(editor.memory['dirty'])
        self.assertEqual(editor.memory['redo_button'].options["state"], "normal")

        # A no-op dirty mark must preserve the redo history.
        editor._mark_dirty()
        self.assertEqual(editor.memory['history'].redo_count(), 1)
        self.assertEqual(editor._on_redo_shortcut(), "break")
        self.assertEqual(len(editor.memory['archive'].modules()), 1)
        self.assertTrue(editor.memory['dirty'])

        with tempfile.TemporaryDirectory() as tmp:
            editor._do_save(Path(tmp) / "history.klwp")
        self.assertFalse(editor.memory['dirty'])
        editor.cmd_undo()
        self.assertEqual(editor.memory['archive'].modules(), [])
        self.assertTrue(editor.memory['dirty'])
        editor.cmd_redo()
        self.assertEqual(len(editor.memory['archive'].modules()), 1)
        self.assertFalse(editor.memory['dirty'])

    def test_bitmap_history_shares_immutable_bytes(self):
        editor = self.editor()
        old_data = b"old bitmap" * 100
        new_data = b"new bitmap" * 100
        name = "bitmaps/IMGhistory"
        editor.memory['archive']['bitmaps'][name] = old_data
        editor._reset_history()

        editor.memory['archive']['bitmaps'][name] = new_data
        editor._mark_dirty()
        snapshot = editor.memory['history'].undo_snapshot(-1)
        self.assertIs(snapshot["bitmaps"][name], old_data)
        editor.cmd_undo()
        self.assertIs(editor.memory['archive']['bitmaps'][name], old_data)
        editor.cmd_redo()
        self.assertIs(editor.memory['archive']['bitmaps'][name], new_data)

    def test_page_count_is_saved_clamped_and_undoable(self):
        editor = self.editor()
        editor.memory["preview_scroll"] = 0.0
        with patch(
                "klwp.ui.interaction.simpledialog.askinteger",
                return_value=4):
            editor.cmd_page_count()

        information = editor.memory["archive"]["preset"]["preset_info"]
        self.assertEqual(information["xscreens"], 3)
        self.assertEqual(editor._preview_page_count(), 4)
        self.assertTrue(editor.memory["dirty"])

        editor.memory["preview_scroll"] = 3.0
        editor._change_page_count(2)
        self.assertEqual(editor.memory["preview_scroll"], 1.0)
        editor.cmd_undo()
        self.assertEqual(editor._preview_page_count(), 4)

    def test_delete_shortcut_can_be_undone(self):
        editor = self.editor()
        item = ke.make_module("text")
        editor.memory["archive"].modules().append(item)
        editor._mark_dirty()
        editor.memory["selected"] = item
        editor.memory["tree"] = Mock()
        editor.memory["tree"].selection.return_value = ("item-row",)
        editor.memory["tree_map"] = {
            "item-row": (item, editor.memory["archive"].modules()),
        }

        with patch(
                "klwp.ui.document.messagebox.askyesno") as confirmation:
            editor._on_delete_shortcut()

        confirmation.assert_not_called()
        self.assertEqual(editor.memory["archive"].modules(), [])
        editor._on_undo_shortcut()
        restored = editor.memory["archive"].modules()
        self.assertEqual(len(restored), 1)
        self.assertEqual(restored[0]["internal_type"], "TextModule")


@unittest.skipUnless(ke.HAS_TK and ke.HAS_PIL, "Tkinter/Pillow required")
class RenderTests(unittest.TestCase):
    @staticmethod
    def renderer(archive):
        info = archive["preset"]["preset_info"]
        renderer = object.__new__(ke.EditorApp)
        renderer.memory = ke.ApplicationMemory()
        renderer.memory["archive"] = archive
        renderer.memory["photo_cache"] = {}
        renderer.memory["font_cache"] = {}
        renderer.memory["device_res"] = (
            int(info.get("width", 720)), int(info.get("height", 1280)))
        return renderer

    def test_scroll_fade_pages_crossfade(self):
        archive = ke.KlwpArchive()
        archive.load(SAMPLES / "genoblanc.klwp")
        renderer = self.renderer(archive)
        page_groups = archive.modules()[:3]

        expected = ([1.0, 0.0, 0.0],
                    [0.0, 1.0, 0.0],
                    [0.0, 0.0, 1.0])
        for page, alphas in enumerate(expected):
            renderer.memory['preview_scroll'] = float(page)
            actual = [renderer._animation_transform(item)["alpha"]
                      for item in page_groups]
            self.assertEqual(actual, alphas)
        renderer.memory['preview_scroll'] = 0.5
        self.assertEqual(
            [renderer._animation_transform(item)["alpha"]
             for item in page_groups],
            [0.5, 0.5, 0.0])

    def test_formula_backed_bitmap_global_switches_background_by_hour(self):
        archive = ke.KlwpArchive()
        archive.load(SAMPLES / "sizuka_home.klwp")
        renderer = self.renderer(archive)
        root_module = archive.root_module()
        references = []
        images = []
        for hour in (2, 8):
            timestamp = datetime(2026, 7, 22, hour).timestamp() * 1000
            renderer.memory["preview_ts"] = timestamp
            global_values = renderer._root_globals()
            reference = renderer._value(
                root_module, "background_bitmap", "", global_values)
            references.append(reference)
            images.append(renderer.render_to_image(72, 160).tobytes())

        self.assertNotEqual(references[0], references[1])
        self.assertIsNotNone(renderer._bitmap_image(references[0]))
        self.assertIsNotNone(renderer._bitmap_image(references[1]))
        self.assertNotEqual(images[0], images[1])

    def test_missing_anchor_uses_center_and_drag_tracks_pointer(self):
        archive = ke.KlwpArchive()
        archive.new()
        selected = ke.make_module("shape")
        selected.pop("position_anchor", None)
        selected["position_offset_x"] = 100.0
        selected["position_offset_y"] = 100.0
        archive.modules().append(selected)
        renderer = self.renderer(archive)
        renderer.render_to_image(360, 800)
        renderer.memory["selected"] = selected
        self.assertNotIn("position_anchor", selected)

        initial_top = renderer._bounds(selected)[1]
        self.assertAlmostEqual(initial_top, 650.0)
        scale = renderer.memory["_scale"]
        renderer.memory["drag_state"] = (100.0, 600.0)
        renderer._render = lambda: None
        event = type("Event", (), {
            "x": 100.0 * scale, "y": 550.0 * scale,
        })()
        renderer._drag_selected_item(event)

        self.assertEqual(selected["position_offset_y"], 150.0)
        self.assertAlmostEqual(renderer._bounds(selected)[1], initial_top - 50.0)

    def test_anchor_margins_are_measured_from_the_selected_edges(self):
        archive = ke.KlwpArchive()
        archive.new()
        renderer = self.renderer(archive)
        item = ke.make_module("shape")
        item.update({
            "shape_width": 100.0, "shape_height": 50.0,
            "position_padding_left": 20.0,
            "position_padding_right": 80.0,
            "position_padding_top": 30.0,
            "position_padding_bottom": 90.0,
        })
        box = (0.0, 0.0, 500.0, 400.0)

        item["position_anchor"] = "TOPLEFT"
        self.assertEqual(
            renderer._place(item, box, 100.0, 50.0), (20.0, 30.0))
        item["position_anchor"] = "BOTTOMRIGHT"
        self.assertEqual(
            renderer._place(item, box, 100.0, 50.0), (320.0, 260.0))
        item["position_anchor"] = "CENTER"
        self.assertEqual(
            renderer._place(item, box, 100.0, 50.0), (170.0, 145.0))

    def test_nested_drag_updates_margins_without_creating_offsets(self):
        archive = ke.KlwpArchive()
        archive.new()
        parent = ke.make_module("layer")
        parent["position_offset_x"] = 0.0
        parent["position_offset_y"] = 0.0
        background = ke.make_module("shape")
        background["shape_width"] = 400.0
        background["shape_height"] = 300.0
        selected = ke.make_module("shape")
        selected["shape_width"] = 100.0
        selected["shape_height"] = 50.0
        selected["position_anchor"] = "CENTER"
        for child in (background, selected):
            child.pop("position_offset_x", None)
            child.pop("position_offset_y", None)
        parent["viewgroup_items"] = [background, selected]
        archive.modules().append(parent)
        renderer = self.renderer(archive)
        renderer.render_to_image(360, 800)
        initial_left, initial_top, _width, _height = renderer._bounds(selected)
        renderer.memory["selected"] = selected
        renderer.memory["drag_state"] = (0.0, 0.0)
        scale = renderer.memory["_scale"]
        renderer._render = lambda: None
        event = type("Event", (), {
            "x": 30.0 * scale, "y": 40.0 * scale,
        })()

        renderer._drag_selected_item(event)
        renderer.render_to_image(360, 800)
        moved_left, moved_top, _width, _height = renderer._bounds(selected)

        self.assertNotIn("position_offset_x", selected)
        self.assertEqual(selected["position_padding_left"], 30.0)
        self.assertEqual(selected["position_padding_right"], -30.0)
        self.assertEqual(selected["position_padding_top"], 40.0)
        self.assertEqual(selected["position_padding_bottom"], -40.0)
        self.assertAlmostEqual(moved_left, initial_left + 30.0)
        self.assertAlmostEqual(moved_top, initial_top + 40.0)

    def test_scroll_and_switch_move_in_sample_directions(self):
        archive = ke.KlwpArchive()
        archive.load(SAMPLES / "S041.klwp")
        renderer = self.renderer(archive)
        renderer.memory['preview_scroll'] = 2.0
        renderer.memory['preview_switch_progress'] = {}
        renderer.memory['_loop_started_at'] = None
        clock = archive.modules()[3]
        transform = renderer._animation_transform(clock)
        self.assertAlmostEqual(transform["dx"], 0.0, places=6)
        self.assertAlmostEqual(transform["dy"], 1000.0, places=6)

        pool = archive.modules()[1]
        switch_anim = next(a for a in pool["internal_animations"]
                           if a["type"] == "SWITCH")
        renderer.memory['preview_scroll'] = 0.0
        renderer.memory['preview_switch_progress'] = {switch_anim["trigger"]: 1.0}
        transform = renderer._animation_transform(pool)
        self.assertAlmostEqual(transform["dx"], 0.0, places=6)
        self.assertAlmostEqual(transform["dy"], -150.0, places=6)

    def test_tap_switch_changes_preview_only(self):
        archive = ke.KlwpArchive()
        archive.load(SAMPLES / "S041.klwp")
        renderer = self.renderer(archive)
        renderer.memory['_animation_after_id'] = None
        renderer._reset_preview_state()
        renderer.memory['status'] = _WidgetStub()
        renderer.after = lambda _delay, _callback: "test-after"
        pool = archive.modules()[1]
        event = pool["internal_events"][0]
        name = event["switch"]
        saved_value = archive.root_module()["globals_list"][name]["value"]

        self.assertTrue(renderer._perform_preview_event(event))
        self.assertNotEqual(renderer.memory['preview_switches'][name], bool(saved_value))
        self.assertEqual(archive.root_module()["globals_list"][name]["value"],
                         saved_value)
        self.assertIn(name, renderer.memory['_switch_transitions'])

    def test_nested_page_shortcut_is_hit_tested_as_preview_navigation(self):
        archive = ke.KlwpArchive()
        archive.load(SAMPLES / "genoblanc.klwp")
        renderer = self.renderer(archive)
        renderer.memory['_animation_after_id'] = None
        renderer._reset_preview_state()
        renderer.memory['status'] = _WidgetStub()
        renderer.after = lambda _delay, _callback: "test-after"
        renderer.render_to_image(270, 480)

        page_events = []
        for _item, _bounds, events in renderer.memory['_event_regions']:
            page_events.extend(
                event for event in events
                if "PAGE_NUMBER=" in str(event.get("intent", "")))
        self.assertEqual(len(page_events), 3)
        last_page = next(event for event in page_events
                         if "PAGE_NUMBER=2" in event["intent"])
        self.assertTrue(renderer._perform_preview_event(last_page))
        self.assertEqual(renderer.memory['_scroll_transition'][1], 2.0)

    def test_loop_2w_fade_and_motion(self):
        archive = ke.KlwpArchive()
        archive.load(SAMPLES / "sizuka_home.klwp")
        renderer = self.renderer(archive)
        renderer.memory['preview_scroll'] = 0.0
        renderer.memory['preview_switch_progress'] = {}
        renderer.memory['_loop_started_at'] = 100.0

        fade_item = archive.modules()[2]      # duration 35縲∥mount 80
        moving_item = archive.modules()[24]  # duration 50縲《peed 3縲∥ngle 90
        with patch("klwp_editor.time.perf_counter", return_value=101.75):
            self.assertAlmostEqual(
                renderer._animation_transform(fade_item)["alpha"], 0.6,
                places=6)
        with patch("klwp_editor.time.perf_counter", return_value=102.5):
            transform = renderer._animation_transform(moving_item)
        self.assertAlmostEqual(transform["dx"], 0.0, places=6)
        self.assertAlmostEqual(transform["dy"], 1.5, places=6)

    def test_switch_rotate_scale_filter_and_easing(self):
        archive = ke.KlwpArchive()
        archive.new()
        item = ke.make_module("shape")
        item["internal_animations"] = [
            {"type": "SWITCH", "trigger": "active", "action": "ROTATE",
             "amount": 90.0, "ease": "STRAIGHT"},
            {"type": "SWITCH", "trigger": "active", "action": "SCALE",
             "amount": 50.0, "ease": "STRAIGHT"},
            {"type": "SWITCH", "trigger": "active",
             "action": "COLOR_INVERT", "amount": 100.0,
             "ease": "ACCELERATE"},
        ]
        renderer = self.renderer(archive)
        renderer.memory["preview_switch_progress"] = {"active": 0.5}

        transform = renderer._animation_transform(item)

        self.assertEqual(transform["rotation"], 45.0)
        self.assertEqual(transform["scale"], 1.25)
        self.assertEqual(transform["color_filter"], "COLOR_INVERT")
        self.assertEqual(transform["filter_amount"], 0.25)

    def test_all_samples_render_at_thumbnail_aspect(self):
        for source in sorted(SAMPLES.glob("*.klwp")):
            archive = ke.KlwpArchive()
            archive.load(source)
            with zipfile.ZipFile(source) as zf:
                target = ke.Image.open(io.BytesIO(
                    zf.read("preset_thumb_portrait.jpg")))
            image = self.renderer(archive).render_to_image(*target.size)
            self.assertEqual(image.size, target.size, source.name)
            color_count = len(image.getcolors(maxcolors=2_000_000))
            minimum = 16 if source.name in {
                "genoblanc.klwp", "S041.klwp", "sizuka_home.klwp"} else 1
            self.assertGreater(color_count, minimum, source.name)

    def test_bitmap_uses_width_and_source_aspect(self):
        archive = ke.KlwpArchive()
        archive.load(SAMPLES / "S041.klwp")
        renderer = self.renderer(archive)
        renderer.memory['_scale'] = 1.0
        renderer.memory['_doc'] = renderer._doc_size()
        bitmap = archive.modules()[0]
        width, height = renderer._item_size(bitmap, renderer._root_globals())
        self.assertAlmostEqual(width, 525.0)
        self.assertAlmostEqual(height, 525.0 * 1400.0 / 1121.0, places=4)

    def test_west_resize_keeps_opposite_edge_fixed_for_center_anchor(self):
        archive = ke.KlwpArchive()
        archive.new()
        item = ke.make_shape_module("長方形")
        item["position_anchor"] = "CENTER"
        archive.modules().append(item)
        renderer = self.renderer(archive)
        renderer.memory['_doc'] = renderer._doc_size()
        bounds = renderer._bounds(item)
        left, top, width, height = bounds
        session = ResizeSession(
            item, "W", (left, top + height / 2), bounds,
            renderer._base_item_size(item, renderer._root_globals()))

        target = session.apply(left - 50.0, top + height / 2)
        renderer._align_resized_item(session, target)
        resized_left, resized_top, resized_width, resized_height = \
            renderer._bounds(item)

        self.assertAlmostEqual(resized_left, left - 50.0, places=1)
        self.assertAlmostEqual(resized_left + resized_width, left + width, places=1)
        self.assertAlmostEqual(resized_top, top, places=1)
        self.assertAlmostEqual(resized_height, height, places=1)

    def test_nested_shape_has_recorded_bounds_for_direct_resize(self):
        archive = ke.KlwpArchive()
        archive.new()
        layer = ke.make_module("layer")
        child = ke.make_shape_module("長方形")
        layer["viewgroup_items"].append(child)
        archive.modules().append(layer)
        renderer = self.renderer(archive)

        renderer.render_to_image(360, 600)

        bounds = renderer._bounds(child)
        self.assertIsNotNone(bounds)
        self.assertEqual(renderer._hit_item(
            bounds[0] + bounds[2] / 2,
            bounds[1] + bounds[3] / 2), child)

    def test_komponent_scale_applies_to_size_content_and_child_bounds(self):
        archive = ke.KlwpArchive()
        archive.new()
        component = ke.make_module("layer")
        component["internal_type"] = "KomponentModule"
        component["config_scale_value"] = 200.0
        component["position_offset_x"] = 0.0
        component["position_offset_y"] = 0.0
        child = ke.make_shape_module("長方形")
        child["shape_width"] = 100.0
        child["shape_height"] = 50.0
        child["position_offset_x"] = 0.0
        child["position_offset_y"] = 0.0
        component["viewgroup_items"].append(child)
        archive.modules().append(component)
        renderer = self.renderer(archive)

        size = renderer._item_size(component, renderer._root_globals())
        renderer.render_to_image(360, 600)
        child_bounds = renderer._bounds(child)

        self.assertEqual(size, (200.0, 100.0))
        self.assertAlmostEqual(child_bounds[2], 200.0)
        self.assertAlmostEqual(child_bounds[3], 100.0)

    def test_linear_radial_and_sweep_gradients_render_distinct_colors(self):
        for gradient in ("LINEAR", "RADIAL", "SWEEP"):
            archive = ke.KlwpArchive()
            archive.new(100, 100)
            shape = ke.make_shape_module("長方形")
            shape["shape_width"] = 100.0
            shape["shape_height"] = 100.0
            shape["position_anchor"] = "TOPLEFT"
            shape["position_offset_x"] = 0.0
            shape["position_offset_y"] = 0.0
            shape["paint_color"] = "#FFFF0000"
            shape["fx_gradient"] = gradient
            shape["fx_gradient_color"] = "#FF0000FF"
            archive.modules().append(shape)

            image = self.renderer(archive).render_to_image(100, 100)
            colors = image.getcolors(maxcolors=100_000)

            self.assertGreater(len(colors), 8, gradient)

    def test_multiply_paint_mode_blends_with_existing_content(self):
        archive = ke.KlwpArchive()
        archive.new(100, 100)
        base = ke.make_shape_module("長方形")
        base["shape_width"] = 720.0
        base["shape_height"] = 720.0
        base["position_anchor"] = "TOPLEFT"
        base["position_offset_x"] = 0.0
        base["position_offset_y"] = 0.0
        base["paint_color"] = "#FF808080"
        overlay = ke.make_shape_module("長方形")
        overlay["shape_width"] = 720.0
        overlay["shape_height"] = 720.0
        overlay["position_anchor"] = "TOPLEFT"
        overlay["position_offset_x"] = 0.0
        overlay["position_offset_y"] = 0.0
        overlay["paint_color"] = "#FFFF0000"
        overlay["paint_mode"] = "MULTIPLY"
        archive.modules().extend((base, overlay))

        image = self.renderer(archive).render_to_image(100, 100)

        self.assertEqual(image.getpixel((50, 50))[:3], (128, 0, 0))

    def test_all_dropdown_shapes_produce_nonempty_masks(self):
        archive = ke.KlwpArchive()
        archive.new()
        renderer = self.renderer(archive)
        renderer.memory['_scale'] = 1.0
        renderer.memory['_doc'] = renderer._doc_size()
        for name in ke.SHAPE_TYPE_OPTIONS:
            module = ke.make_shape_module(name)
            width = int(module["shape_width"])
            height = int(module["shape_height"])
            stroke = 12 if module.get("paint_style") == "STROKE" else None
            mask = renderer._shape_geometry_mask(
                module, width, height, 1.0, stroke_width=stroke)
            self.assertIsNotNone(mask.getbbox(), name)

    def test_switch_reference_count_includes_animation_and_tap(self):
        archive = ke.KlwpArchive()
        archive.load(SAMPLES / "S041.klwp")
        renderer = self.renderer(archive)
        name = archive.modules()[1]["internal_events"][0]["switch"]
        self.assertEqual(renderer._switch_reference_count(name), 3)


if __name__ == "__main__":
    unittest.main()


