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
from klwp.positioning import KeyboardNudge, PositionMutation
from klwp.snap import SnapEngine, SnapTargets
from klwp.background import BackgroundImageBinding, BitmapGlobalCollection
from klwp.icons import IconCatalog, MATERIAL_ICON_SET
from klwp.svg import decode_kustom_icon
from klwp.ui.global_dialog import GlobalEntryValues
from klwp.ui.setting_values import TouchActionValues
from klwp.ui.kode_dialog import (
    KodeInspector, KodeSyntax, KodeTargetCollection,
)
from klwp.ui.document import DocumentMixin
from klwp.ui.interaction import InteractionMixin
from klwp.ui.multi_selection import MultiSelectionMixin
from klwp.ui.grouping import GroupingMixin
from klwp.ui.menu_toolbar import EditorCommandCatalog, ToolbarPresentation
from klwp.ui.theme import EditorPalette, EditorTheme
from klwp.ui.window import EditorWindowBuilder
from klwp.adb import AdbDevices, AdbTransfer
from klwp.preview.pages import PresetPageCount, PreviewPageCounter
from klwp.preview.values import PREVIEW_VALUE_FIELDS, default_preview_values
from klwp.pixel_diff import (
    ComparableImages, ComparisonRegion, PixelDiff, PixelDiffThresholds,
    PresetPreview)
from klwp.runtime import Resampling
from klwp.preview.zoom import CachedPreviewImage, PreviewPan, PreviewZoom
from klwp.ui.tree import ModuleTreePresentation
from klwp.ui.tree_drag import TreeDragMixin, TreeReorder
from klwp.clipboard import ModuleClipboard
from klwp.selection import ModuleSelection
from klwp.ui.zoom import PreviewZoomMixin


ROOT = Path(__file__).resolve().parent
SAMPLES = ROOT / "sample"


class _TreeEditor(DocumentMixin, TreeDragMixin):
    pass


class _MultiEditor(MultiSelectionMixin, GroupingMixin, DocumentMixin):
    def _set_status(self, text):
        self.memory["last_status"] = text


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

    def test_broadcast_value_is_blank_until_explicitly_entered(self):
        values = {"__preview__": {"broadcast": {"gpt_ans": "回答"}}}

        self.assertEqual(ke.eval_formula("$br(tasker, gpt_ans)$"), "")
        self.assertEqual(
            ke.eval_formula("$br(tasker, gpt_ans)$", values), "回答")
        self.assertEqual(default_preview_values()["broadcast"]["gpt_ans"], "")
        self.assertIn(
            ("broadcast", "gpt_ans", "Broadcast / Tasker値"),
            PREVIEW_VALUE_FIELDS)

    def test_kode_live_editor_reports_structural_errors(self):
        self.assertEqual(KodeSyntax.problem("$if(1, yes, no)$"), "")
        self.assertIn("$", KodeSyntax.problem("$if(1, yes, no)"))
        self.assertIn("括弧", KodeSyntax.problem("$if(1, yes, no$"))
        self.assertIn("引用符", KodeSyntax.problem('$tc(up, "abc)$'))

    def test_kode_live_editor_evaluates_current_preview_values(self):
        values = {"__preview__": {"weather": {"temp": -8.5}}}

        inspection = KodeInspector(
            "気温 $wi(temp)$°C", values).inspect()

        self.assertTrue(inspection["valid"])
        self.assertEqual(inspection["status"], "構文OK")
        self.assertEqual(inspection["preview"], "気温 -8.5°C")

    def test_kode_targets_preserve_unrelated_internal_formulas(self):
        item = {
            "internal_type": "TextModule",
            "text_expression": "$df(HH:mm)$",
            "internal_formulas": {"paint_color": "$gv(color)$"},
        }
        targets = KodeTargetCollection(item)

        targets.apply("internal_formulas.text_size", "$gv(size)$")
        targets.apply("text_expression", "$mi(title)$")

        self.assertIn("text_expression", targets.names())
        self.assertEqual(item["text_expression"], "$mi(title)$")
        self.assertEqual(
            item["internal_formulas"]["paint_color"], "$gv(color)$")
        self.assertEqual(
            item["internal_formulas"]["text_size"], "$gv(size)$")


@unittest.skipUnless(ke.HAS_PIL, "Pillow is required")
class PixelDiffTests(unittest.TestCase):
    def test_identical_images_have_perfect_metrics(self):
        image = ke.Image.new("RGB", (8, 6), "#123456")

        metrics = PixelDiff(ComparableImages(image, image)).measure()

        self.assertEqual(metrics["mse"], 0.0)
        self.assertIsNone(metrics["psnr"])
        self.assertEqual(metrics["ssim"], 1.0)

    def test_changed_images_write_metrics_and_heatmap(self):
        reference = ke.Image.new("RGB", (8, 8), "#000000")
        actual = reference.copy()
        actual.paste("#FFFFFF", (0, 0, 4, 4))
        comparison = PixelDiff(ComparableImages(reference, actual))

        with tempfile.TemporaryDirectory() as directory:
            metrics = comparison.write_report(directory, heat_gain=3.0)
            output = Path(directory)
            stored = json.loads(
                (output / "metrics.json").read_text(encoding="utf-8"))
            names = {
                "reference.png", "actual.png", "heatmap.png", "metrics.json"}
            self.assertEqual(
                {path.name for path in output.iterdir()}, names)

        self.assertEqual(stored, metrics)
        self.assertGreater(metrics["mse"], 0.0)
        self.assertLess(metrics["ssim"], 1.0)
        failures = PixelDiffThresholds(0.0, 1.0).failures(metrics)
        self.assertEqual(len(failures), 2)

    def test_excluded_margin_does_not_affect_metrics(self):
        reference = ke.Image.new("RGB", (6, 6), "#000000")
        actual = reference.copy()
        actual.paste("#FFFFFF", (0, 0, 6, 1))
        images = ComparableImages(reference, actual)
        cropped = images.cropped(ComparisonRegion(top=1))

        metrics = PixelDiff(cropped).measure()

        self.assertEqual(metrics["mse"], 0.0)
        self.assertEqual(metrics["height"], 5)

    def test_sizuka_reference_stays_within_regression_threshold(self):
        preset = SAMPLES / "sizuka_home.klwp"
        screenshot = SAMPLES / "Screenshot_20260720-022511.png"
        if not preset.exists() or not screenshot.exists():
            self.skipTest("local sizuka_home reference pair is unavailable")
        timestamp = datetime(2026, 7, 20, 2, 25).timestamp() * 1000.0
        reference = ke.Image.open(screenshot).convert("RGB")
        normalized = reference.resize((108, 240), Resampling.LANCZOS)
        actual = PresetPreview.load(preset, timestamp).render((108, 240))
        images = ComparableImages(normalized, actual)
        cropped = images.cropped(ComparisonRegion(top=5, bottom=5))

        metrics = PixelDiff(cropped).measure()

        failures = PixelDiffThresholds(6500.0, 0.1).failures(metrics)
        self.assertEqual(failures, ())


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


class IconPickerTests(unittest.TestCase):
    def test_material_icon_catalog_encodes_self_contained_svg(self):
        archive = ke.KlwpArchive()
        archive.new()
        catalog = IconCatalog.from_archive(archive)

        entries = catalog.search()

        self.assertGreaterEqual(len(entries), 17)
        for entry in entries:
            name, paths, viewbox = decode_kustom_icon(
                entry.encoded_value())
            self.assertEqual(name, entry.name())
            self.assertTrue(paths, entry.name())
            self.assertEqual(viewbox, (0.0, 0.0, 24.0, 24.0))

    def test_icon_catalog_reuses_sample_icon_and_applies_selection(self):
        archive = ke.KlwpArchive()
        archive.load(SAMPLES / "sizuka_home.klwp")
        catalog = IconCatalog.from_archive(archive)
        camera = catalog.search("camera")[0]
        item = ke.make_module("icon")
        item["icon_size"] = 84.0

        catalog.apply(item, camera)

        self.assertEqual(item["icon_set"], MATERIAL_ICON_SET)
        self.assertTrue(item["icon_icon"].startswith("camera#"))
        self.assertEqual(item["icon_size"], 84.0)
        self.assertEqual(len(catalog.search("一時停止")), 1)

    def test_selected_icon_survives_klwp_archive_round_trip(self):
        archive = ke.KlwpArchive()
        archive.new()
        catalog = IconCatalog.from_archive(archive)
        item = ke.make_module("icon")
        catalog.apply(item, catalog.search("スター")[0])
        archive.modules().append(item)

        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "icon.klwp"
            archive.save(path)
            loaded = ke.KlwpArchive()
            loaded.load(path)

        saved = loaded.modules()[0]
        name, paths, viewbox = decode_kustom_icon(saved["icon_icon"])
        self.assertEqual(name, "star")
        self.assertTrue(paths)
        self.assertEqual(viewbox, (0.0, 0.0, 24.0, 24.0))


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

    def test_module_selection_tracks_focus_and_common_parent(self):
        first = ke.make_module("shape")
        second = ke.make_module("text")
        parent = [first, second]
        tree = Mock()
        tree.selection.return_value = ("first", "second")
        tree.focus.return_value = "second"
        memory = {
            "tree": tree,
            "tree_map": {
                "first": (first, parent),
                "second": (second, parent),
            },
        }

        selection = ModuleSelection.from_memory(memory)

        self.assertEqual(selection.items(), (first, second))
        self.assertIs(selection.primary_item(), second)
        self.assertTrue(selection.same_parent())

    def test_arrow_key_nudges_selected_root_item_one_unit(self):
        archive = ke.KlwpArchive()
        archive.new()
        item = ke.make_module("shape")
        item["position_anchor"] = "TOPLEFT"
        item["position_offset_x"] = 12.0
        item["position_offset_y"] = 34.0
        archive.modules().append(item)
        editor = _MultiEditor()
        editor.memory = ke.ApplicationMemory()
        editor.memory["archive"] = archive
        editor.memory["tree"] = Mock()
        editor.memory["tree"].selection.return_value = ("item",)
        editor.memory["tree"].focus.return_value = "item"
        editor.memory["tree_map"] = {
            "item": (item, archive.modules()),
        }
        editor._mark_dirty = Mock()
        editor._render = Mock()
        editor._build_props = Mock()
        event = type("Event", (), {"keysym": "Right", "state": 0})()

        result = editor._on_nudge_shortcut(event)

        self.assertEqual(result, "break")
        self.assertEqual(item["position_offset_x"], 13.0)
        self.assertEqual(item["position_offset_y"], 34.0)
        editor._mark_dirty.assert_called_once_with()
        editor._render.assert_called_once_with()
        editor._build_props.assert_called_once_with()

    def test_shift_arrow_nudges_every_selected_nested_item_ten_units(self):
        archive = ke.KlwpArchive()
        archive.new()
        layer = ke.make_module("layer")
        first = ke.make_module("shape")
        second = ke.make_module("text")
        for item in (first, second):
            item["position_anchor"] = "CENTER"
            item["position_padding_top"] = 0.0
            item["position_padding_bottom"] = 0.0
        children = layer["viewgroup_items"]
        children.extend((first, second))
        archive.modules().append(layer)
        editor = _MultiEditor()
        editor.memory = ke.ApplicationMemory()
        editor.memory["archive"] = archive
        editor.memory["tree"] = Mock()
        editor.memory["tree"].selection.return_value = ("first", "second")
        editor.memory["tree"].focus.return_value = "second"
        editor.memory["tree_map"] = {
            "first": (first, children),
            "second": (second, children),
        }
        editor._mark_dirty = Mock()
        editor._render = Mock()
        editor._build_props = Mock()
        event = type("Event", (), {"keysym": "Up", "state": 1})()

        result = editor._on_nudge_shortcut(event)

        self.assertEqual(result, "break")
        for item in (first, second):
            self.assertEqual(item["position_padding_top"], -10.0)
            self.assertEqual(item["position_padding_bottom"], 10.0)
        editor._mark_dirty.assert_called_once_with()

    def test_module_clipboard_renames_conflicting_bitmap_on_cross_file_paste(self):
        bitmap_name = "bitmaps/IMG" + "1" * 32
        reference = "kfile://org.kustom.provider/" + bitmap_name
        source = ke.KlwpArchive()
        source.new()
        source["bitmaps"][bitmap_name] = b"source bitmap"
        item = ke.make_module("bitmap")
        item["bitmap_bitmap"] = reference
        package = ModuleClipboard.capture((item,), source)
        destination = ke.KlwpArchive()
        destination.new()
        destination["bitmaps"][bitmap_name] = b"other bitmap"

        pasted = package.paste_into(destination)[0]

        self.assertNotEqual(pasted["bitmap_bitmap"], reference)
        self.assertEqual(len(destination["bitmaps"]), 2)
        pasted_name = pasted["bitmap_bitmap"].split(
            "kfile://org.kustom.provider/", 1)[1]
        self.assertEqual(destination["bitmaps"][pasted_name], b"source bitmap")

    def test_multi_selection_copy_pastes_into_another_document(self):
        source = ke.KlwpArchive()
        source.new()
        first = ke.make_module("shape")
        second = ke.make_module("text")
        source.modules().extend((first, second))
        editor = _MultiEditor()
        editor.memory = ke.ApplicationMemory()
        editor.memory["archive"] = source
        editor.memory["tree"] = Mock()
        editor.memory["tree"].selection.return_value = ("first", "second")
        editor.memory["tree"].focus.return_value = "second"
        editor.memory["tree_map"] = {
            "first": (first, source.modules()),
            "second": (second, source.modules()),
        }
        editor.cmd_copy()
        destination = ke.KlwpArchive()
        destination.new()
        editor.memory["archive"] = destination
        editor.memory["selected"] = None
        editor.memory["selected_items"] = ()
        editor.memory["tree"].selection.return_value = ()
        editor.memory["tree"].focus.return_value = ""
        editor.memory["tree_map"] = {}
        editor._mark_dirty = Mock()
        editor._refresh_all = Mock()

        editor.cmd_paste()

        self.assertEqual(len(destination.modules()), 2)
        self.assertEqual(
            [item["internal_type"] for item in destination.modules()],
            ["ShapeModule", "TextModule"])
        self.assertEqual(len(editor.memory["selected_items"]), 2)
        editor._mark_dirty.assert_called_once_with()

    def test_delete_shortcut_removes_all_selected_items_without_confirmation(self):
        archive = ke.KlwpArchive()
        archive.new()
        first = ke.make_module("shape")
        second = ke.make_module("text")
        archive.modules().extend((first, second))
        editor = _MultiEditor()
        editor.memory = ke.ApplicationMemory()
        editor.memory["archive"] = archive
        editor.memory["tree"] = Mock()
        editor.memory["tree"].selection.return_value = ("first", "second")
        editor.memory["tree"].focus.return_value = "second"
        editor.memory["tree_map"] = {
            "first": (first, archive.modules()),
            "second": (second, archive.modules()),
        }
        editor._mark_dirty = Mock()
        editor._refresh_all = Mock()

        editor._on_delete_shortcut()

        self.assertEqual(archive.modules(), [])
        editor._mark_dirty.assert_called_once_with()
        editor._refresh_all.assert_called_once_with()


class MenuToolbarTests(unittest.TestCase):
    def test_menu_groups_keep_every_toolbar_command_available(self):
        groups = EditorCommandCatalog(Mock()).menu_groups()
        actual = {
            group: tuple(item[0] for item in entries if item[0])
            for group, entries in groups
        }

        self.assertEqual(actual, {
            "ファイル": ("新規", "開く", "保存", "名前を付けて保存"),
            "編集": ("元に戻す", "やり直す", "コピー", "貼付", "複製", "削除"),
            "追加": ("テキスト", "図形", "アイコン", "画像", "レイヤー"),
            "配置": ("グループ化", "グループ解除", "背面へ", "前面へ"),
            "プロジェクト": (
                "グローバル管理", "プレビュー値",
                "背景設定", "画像管理", "端末解像度"),
            "デバイス": ("Androidへ転送",),
        })

    def test_primary_toolbar_contains_only_frequent_actions(self):
        items = EditorCommandCatalog(Mock()).toolbar_items()
        labels = tuple(
            item[1] for item in items if item[0] != "separator")

        self.assertEqual(labels, (
            "新規", "開く", "保存", "元に戻す", "やり直す", "＋追加",
            "コピー", "貼付", "複製", "削除", "Androidへ転送"))
        self.assertEqual(
            sum(item[0] == "separator" for item in items), 4)

    def test_toolbar_presentation_keeps_labels_and_explains_actions(self):
        labels = ("新規", "保存", "元に戻す", "削除", "Androidへ転送")
        for label in labels:
            self.assertIn(label, ToolbarPresentation.display(label))
            self.assertTrue(ToolbarPresentation.tooltip(label))

    def test_dark_theme_configures_ttk_and_tk_widgets(self):
        owner = Mock()
        style = Mock()
        style.theme_names.return_value = ("vista", "clam")
        palette = EditorPalette.colors()

        with patch("klwp.ui.theme.ttk.Style", return_value=style):
            EditorTheme(owner).apply()

        style.theme_use.assert_called_once_with("clam")
        style.configure.assert_any_call(
            "TFrame", background=palette["background"])
        style.map.assert_any_call(
            "Treeview", background=[("selected", palette["accent"])],
            foreground=[("selected", "#ffffff")])
        owner.configure.assert_called_once_with(
            background=palette["background"])
        self.assertGreaterEqual(owner.option_add.call_count, 8)


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
        for key in ("Left", "Right", "Up", "Down"):
            owner.bind_all.assert_any_call(
                f"<{key}>", owner._on_nudge_shortcut)
            owner.bind_all.assert_any_call(
                f"<Shift-{key}>", owner._on_nudge_shortcut)

    def test_tree_arrow_keys_bind_to_nudge_command(self):
        owner = Mock()
        tree = Mock()

        EditorWindowBuilder(owner)._tree_nudge_shortcuts(tree)

        for key in ("Left", "Right", "Up", "Down"):
            tree.bind.assert_any_call(
                f"<{key}>", owner._on_nudge_shortcut)
            tree.bind.assert_any_call(
                f"<Shift-{key}>", owner._on_nudge_shortcut)

    def test_nudge_ignores_arrow_keys_while_editing_values(self):
        widget = Mock()
        widget.winfo_class.return_value = "TEntry"
        event = type(
            "Event", (), {
                "keysym": "Left", "state": 0, "widget": widget,
            })()

        nudge = KeyboardNudge.from_event(event)

        self.assertIsNone(nudge)

    def test_nudge_accepts_arrow_keys_from_preview_canvas(self):
        widget = Mock()
        widget.winfo_class.return_value = "Canvas"
        event = type(
            "Event", (), {
                "keysym": "Left", "state": 0, "widget": widget,
            })()

        nudge = KeyboardNudge.from_event(event)
        mutation = Mock()
        nudge.apply_to(mutation)

        mutation.move_by.assert_called_once_with(-1.0, 0.0)


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

    def test_keyboard_nudge_can_be_undone(self):
        editor = self.editor()
        item = ke.make_module("shape")
        item["position_anchor"] = "TOPLEFT"
        initial_vertical = item["position_offset_y"]
        editor.memory["archive"].modules().append(item)
        editor._mark_dirty()
        editor.memory["selected"] = item
        editor.memory["tree"] = Mock()
        editor.memory["tree"].selection.return_value = ("item-row",)
        editor.memory["tree"].focus.return_value = "item-row"
        editor.memory["tree_map"] = {
            "item-row": (item, editor.memory["archive"].modules()),
        }
        editor._render = Mock()
        editor._build_props = Mock()
        event = type("Event", (), {"keysym": "Down", "state": 0})()

        editor._on_nudge_shortcut(event)

        self.assertEqual(item["position_offset_y"], initial_vertical + 1.0)
        editor.cmd_undo()
        restored = editor.memory["archive"].modules()[0]
        self.assertEqual(restored["position_offset_y"], initial_vertical)


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

    def test_sizuka_clock_and_weather_text_bounds_do_not_overlap(self):
        archive = ke.KlwpArchive()
        archive.load(SAMPLES / "sizuka_home.klwp")
        renderer = self.renderer(archive)
        timestamp = datetime(2026, 7, 22, 11, 0).timestamp() * 1000.0
        renderer.memory["preview_ts"] = timestamp
        renderer.render_to_image(342, 760)
        clock = archive.modules()[1]
        weather = archive.modules()[4]
        clock_items = clock["viewgroup_items"]
        weather_items = weather["viewgroup_items"]
        hour_bounds = renderer._recorded_bounds(clock_items[3])
        date_bounds = renderer._recorded_bounds(clock_items[7])
        temperature_bounds = renderer._recorded_bounds(weather_items[3])
        clock_bounds = renderer._bounds(clock)
        clock_top = clock_bounds[1]
        clock_bottom = clock_top + clock_bounds[3]
        hour_top = hour_bounds[1]
        hour_bottom = hour_top + hour_bounds[3]
        date_bottom = date_bounds[1] + date_bounds[3]
        temperature_top = temperature_bounds[1]

        self.assertGreaterEqual(hour_top, clock_top)
        self.assertLessEqual(hour_bottom, clock_bottom)
        self.assertLess(date_bottom, temperature_top)

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

    def test_group_and_ungroup_preserve_selected_item_bounds(self):
        archive = ke.KlwpArchive()
        archive.new()
        first = ke.make_shape_module("長方形")
        first.update(
            position_anchor="TOPLEFT", position_offset_x=80.0,
            position_offset_y=120.0, shape_width=100.0, shape_height=60.0)
        second = ke.make_shape_module("円")
        second.update(
            position_anchor="TOPLEFT", position_offset_x=230.0,
            position_offset_y=210.0, shape_width=70.0, shape_height=70.0)
        archive.modules().extend((first, second))
        renderer = self.renderer(archive)
        renderer.render_to_image(360, 600)
        before = (renderer._bounds(first), renderer._bounds(second))
        tree = Mock()
        tree.selection.return_value = ("first", "second")
        tree.focus.return_value = "second"
        renderer.memory["tree"] = tree
        renderer.memory["tree_map"] = {
            "first": (first, archive.modules()),
            "second": (second, archive.modules()),
        }
        renderer.memory["status"] = Mock()
        renderer._mark_dirty = Mock()
        renderer._refresh_all = Mock()

        renderer.cmd_group_selection()
        group = archive.modules()[0]
        renderer.render_to_image(360, 600)
        grouped_bounds = tuple(
            renderer._bounds(item) for item in group["viewgroup_items"])
        tree.selection.return_value = ("group",)
        tree.focus.return_value = "group"
        renderer.memory["tree_map"] = {"group": (group, archive.modules())}
        renderer.cmd_ungroup_selection()
        renderer.render_to_image(360, 600)
        after = tuple(renderer._bounds(item) for item in archive.modules())

        for expected, grouped, restored in zip(
                before, grouped_bounds, after):
            self.assertTupleAlmostEqual(grouped, expected)
            self.assertTupleAlmostEqual(restored, expected)

    def assertTupleAlmostEqual(self, actual, expected):
        for actual_value, expected_value in zip(actual, expected):
            self.assertAlmostEqual(actual_value, expected_value, places=1)

    def test_sizuka_shape_less_overlap_layers_wrap_all_children(self):
        archive = ke.KlwpArchive()
        archive.load(SAMPLES / "sizuka_home.klwp")
        renderer = self.renderer(archive)
        global_values = renderer._root_globals()
        pending = list(archive.modules())
        shape_less_layers = []
        while pending:
            item = pending.pop()
            children = item.get("viewgroup_items", [])
            pending.extend(children)
            child_types = [child.get("internal_type") for child in children]
            if item.get("internal_type") == "OverlapLayerModule" and \
                    "ShapeModule" not in child_types:
                shape_less_layers.append(item)

        sizes = sorted(
            renderer._layer_box_size(item, global_values)
            for item in shape_less_layers)

        self.assertEqual(
            sizes, [(35.0, 35.0), (35.0, 35.0),
                    (40.0, 40.0), (210.0, 40.0)])
        self.assertNotIn((200.0, 120.0), sizes)

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


