import copy
import io
import json
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from pathlib import Path

import klwp_editor as ke
from klwp.ui.property_panel import AnchorChoices
from klwp.ui.color_control import KlwpColor
from klwp.resize import ResizeHandleSet, ResizeSession
from klwp.ui.global_dialog import GlobalEntryValues
from klwp.ui.setting_values import TouchActionValues
from klwp.adb import AdbDevices, AdbTransfer


ROOT = Path(__file__).resolve().parent
SAMPLES = ROOT / "sample"


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

        editor.cmd_undo()
        self.assertEqual(editor.memory['archive'].modules(), [])
        self.assertFalse(editor.memory['dirty'])
        self.assertEqual(editor.memory['redo_button'].options["state"], "normal")

        # A no-op dirty mark must preserve the redo history.
        editor._mark_dirty()
        self.assertEqual(editor.memory['history'].redo_count(), 1)
        editor.cmd_redo()
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


