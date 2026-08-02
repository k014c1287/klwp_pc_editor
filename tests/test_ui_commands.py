from .support import *  # noqa: F401,F403


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
        self.assertEqual(ModuleTreePresentation.visibility(hidden), "○")
        self.assertEqual(ModuleTreePresentation.priority(2, 3), "1・最前面")
        self.assertEqual(ModuleTreePresentation.tags(hidden), ("hidden",))

    def test_visibility_column_click_toggles_one_item_and_records_history(self):
        archive = ke.KlwpArchive()
        archive.new()
        item = ke.make_module("shape")
        archive.modules().append(item)
        tree = Mock()
        tree.identify_column.return_value = "#1"
        tree.identify_row.return_value = "item"
        editor = _LayerEditor()
        editor.memory = ke.ApplicationMemory()
        editor.memory["archive"] = archive
        editor.memory["tree"] = tree
        editor.memory["tree_map"] = {
            "item": (item, archive.modules()),
        }
        editor._mark_dirty = Mock()
        editor._refresh_all = Mock()
        event = type("Event", (), {"x": 10, "y": 20})()

        result = editor._on_tree_visibility_click(event)

        self.assertEqual(result, "break")
        self.assertFalse(item["config_visible"])
        tree.selection_set.assert_called_once_with("item")
        editor._mark_dirty.assert_called_once_with()
        editor._refresh_all.assert_called_once_with(select=(item,))

    def test_visibility_command_hides_mixed_multi_selection(self):
        archive = ke.KlwpArchive()
        archive.new()
        first = ke.make_module("shape")
        second = ke.make_module("text")
        second["config_visible"] = False
        archive.modules().extend((first, second))
        tree = Mock()
        tree.selection.return_value = ("first", "second")
        tree.focus.return_value = "second"
        editor = _LayerEditor()
        editor.memory = ke.ApplicationMemory()
        editor.memory["archive"] = archive
        editor.memory["tree"] = tree
        editor.memory["tree_map"] = {
            "first": (first, archive.modules()),
            "second": (second, archive.modules()),
        }
        editor._mark_dirty = Mock()
        editor._refresh_all = Mock()

        editor.cmd_toggle_visibility()

        self.assertFalse(ModuleVisibility(first).shown())
        self.assertFalse(ModuleVisibility(second).shown())
        editor._mark_dirty.assert_called_once_with()

    def test_context_menu_contains_direct_layer_actions(self):
        archive = ke.KlwpArchive()
        archive.new()
        item = ke.make_module("shape")
        archive.modules().append(item)
        tree = Mock()
        tree.identify_row.return_value = "item"
        tree.selection.return_value = ("item",)
        tree.focus.return_value = "item"
        editor = _LayerEditor()
        editor.memory = ke.ApplicationMemory()
        editor.memory["archive"] = archive
        editor.memory["tree"] = tree
        editor.memory["tree_map"] = {
            "item": (item, archive.modules()),
        }
        event = type(
            "Event", (), {"y": 20, "x_root": 100, "y_root": 200})()
        menu = Mock()

        with patch("klwp.ui.layer_actions.tk.Menu", return_value=menu):
            result = editor._on_tree_context_menu(event)

        labels = tuple(
            call.kwargs["label"] for call in menu.add_command.call_args_list)
        self.assertEqual(result, "break")
        self.assertEqual(labels, (
            "非表示にする", "複製", "削除", "背面へ", "前面へ"))
        menu.tk_popup.assert_called_once_with(100, 200)
        menu.grab_release.assert_called_once_with()

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

class PngExportTests(unittest.TestCase):
    def test_export_uses_device_resolution_without_changing_document_state(self):
        editor = _PngExportEditor()
        editor.memory = ke.ApplicationMemory()
        editor.memory["device_res"] = (1080, 2400)
        editor.memory["dirty"] = True
        editor.memory["archive"] = {"path": "wallpaper.klwp"}
        image = Mock()
        editor.render_to_image = Mock(return_value=image)

        editor._write_png("preview.png")

        editor.render_to_image.assert_called_once_with(1080, 2400)
        image.save.assert_called_once_with("preview.png", format="PNG")
        self.assertTrue(editor.memory["dirty"])
        self.assertEqual(editor.memory["archive"]["path"], "wallpaper.klwp")
        self.assertEqual(
            editor.memory["last_status"], "PNGを書き出しました: preview.png")

    def test_export_command_uses_png_file_dialog(self):
        editor = _PngExportEditor()
        editor._export_png = Mock()

        with patch("klwp.ui.export_png.HAS_PIL", True), patch(
                "klwp.ui.export_png.filedialog.asksaveasfilename",
                return_value="chosen.png") as dialog:
            editor.cmd_export_png()

        dialog.assert_called_once_with(
            defaultextension=".png", filetypes=[("PNG image", "*.png")])
        editor._export_png.assert_called_once_with("chosen.png")

class CommandPaletteTests(unittest.TestCase):
    def test_palette_filters_menu_commands_by_label_and_category(self):
        groups = EditorCommandCatalog(Mock()).menu_groups()
        entries = CommandPaletteEntries(groups)

        save_labels = entries.filtered("保存").labels()
        device_labels = entries.filtered("デバイス").labels()

        self.assertEqual(save_labels, (
            "ファイル › 保存", "ファイル › 名前を付けて保存"))
        self.assertEqual(device_labels, ("デバイス › Androidへ転送",))
        self.assertNotIn("編集 › None", entries.labels())

    def test_palette_executes_selected_command_and_closes(self):
        command = Mock()
        groups = (("テスト", (("実行", command, ""),)),)
        entries = CommandPaletteEntries(groups)
        dialog = CommandPaletteDialog(Mock(), entries)
        listing = Mock()
        listing.curselection.return_value = (0,)
        window = Mock()
        dialog._state["list"] = listing
        dialog._state["window"] = window

        result = dialog._execute()

        self.assertEqual(result, "break")
        window.destroy.assert_called_once_with()
        command.assert_called_once_with()

class AlignmentTests(unittest.TestCase):
    def test_alignment_uses_outer_selection_edges_and_centers(self):
        entries = (
            ("first", (10.0, 10.0, 20.0, 20.0)),
            ("second", (50.0, 20.0, 10.0, 40.0)),
        )
        layout = AlignmentLayout(entries)

        horizontal = layout.movements("center_horizontal")
        vertical = layout.movements("center_vertical")

        self.assertEqual(horizontal, (
            ("first", 15.0, 0.0), ("second", -20.0, 0.0)))
        self.assertEqual(vertical, (
            ("first", 0.0, 15.0), ("second", 0.0, -5.0)))

    def test_distribution_keeps_outer_items_and_equalizes_gaps(self):
        entries = (
            ("first", (0.0, 0.0, 10.0, 10.0)),
            ("second", (20.0, 5.0, 10.0, 10.0)),
            ("third", (60.0, 30.0, 20.0, 10.0)),
        )

        movements = AlignmentLayout(entries).movements(
            "distribute_horizontal")

        self.assertEqual(movements, (
            ("first", 0.0, 0.0),
            ("second", 10.0, 0.0),
            ("third", 0.0, 0.0)))

    def test_align_command_updates_root_offsets_and_records_once(self):
        archive = ke.KlwpArchive()
        archive.new()
        first = ke.make_module("shape")
        second = ke.make_module("shape")
        for item, horizontal in ((first, 10.0), (second, 50.0)):
            item["position_anchor"] = "TOPLEFT"
            item["position_offset_x"] = horizontal
            item["position_offset_y"] = 20.0
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
        editor._bounds = lambda item: (
            (10.0, 20.0, 20.0, 20.0) if item is first
            else (50.0, 20.0, 20.0, 20.0))
        editor._mark_dirty = Mock()
        editor._render = Mock()
        editor._build_props = Mock()

        editor.cmd_align_left()

        self.assertEqual(first["position_offset_x"], 10.0)
        self.assertEqual(second["position_offset_x"], 10.0)
        editor._mark_dirty.assert_called_once_with()
        editor._render.assert_called_once_with()

    def test_distribution_requires_three_items_in_same_layer(self):
        editor = _MultiEditor()
        editor._module_selection = Mock()
        selection = editor._module_selection.return_value
        selection.count.return_value = 2
        selection.same_parent.return_value = True
        editor._set_status = Mock()

        editor.cmd_distribute_horizontal()

        editor._set_status.assert_called_once_with(
            "同じレイヤー内の要素を3件以上選択してください")

class MenuToolbarTests(unittest.TestCase):
    def test_menu_groups_keep_every_toolbar_command_available(self):
        groups = EditorCommandCatalog(Mock()).menu_groups()
        actual = {
            group: tuple(item[0] for item in entries if item[0])
            for group, entries in groups
        }

        self.assertEqual(actual, {
            "ファイル": (
                "新規", "開く", "保存", "名前を付けて保存",
                "PNGを書き出す…"),
            "編集": (
                "元に戻す", "やり直す", "コピー", "貼付", "複製", "削除",
                "コマンドパレット…"),
            "追加": ("テキスト", "図形", "アイコン", "画像", "レイヤー"),
            "配置": (
                "グループ化", "グループ解除",
                "左揃え", "水平方向中央揃え", "右揃え",
                "上揃え", "垂直方向中央揃え", "下揃え",
                "水平方向に均等配置", "垂直方向に均等配置",
                "背面へ", "前面へ"),
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

class WelcomeAndRecentFileTests(unittest.TestCase):
    def test_recent_files_are_deduplicated_and_missing_files_are_removed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            storage = root / "recent.json"
            first = root / "first.klwp"
            second = root / "second.klwp"
            first.write_bytes(b"first")
            second.write_bytes(b"second")
            store = RecentFileStore(storage)
            store.remember(first)
            store.remember(second)
            store.remember(first)
            second.unlink()

            self.assertEqual(store.paths(), (str(first.resolve()),))

    def test_recent_store_recovers_from_invalid_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            storage = Path(temporary) / "recent.json"
            storage.write_text("not-json", encoding="utf-8")

            self.assertEqual(RecentFileStore(storage).paths(), ())

    def test_template_catalog_only_lists_klwp_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "b.klwp").write_bytes(b"b")
            (root / "a.klwp").write_bytes(b"a")
            (root / "note.txt").write_text("ignore", encoding="utf-8")

            names = tuple(path.name for path in TemplateCatalog(root).entries())

            self.assertEqual(names, ("a.klwp", "b.klwp"))

    def test_template_open_forces_save_as_without_recent_history(self):
        editor = _TreeEditor()
        editor.memory = ke.ApplicationMemory()
        archive = ke.KlwpArchive()
        archive.new()
        archive["path"] = "sample/example.klwp"
        editor.memory["archive"] = archive
        editor.memory["status"] = Mock()
        editor._confirm_discard = Mock(return_value=True)
        editor._open_archive_path = Mock(return_value=True)
        editor._update_title = Mock()

        opened = editor.cmd_open_template("sample/example.klwp")

        self.assertTrue(opened)
        self.assertIsNone(archive["path"])
        editor._open_archive_path.assert_called_once_with(
            "sample/example.klwp", False)

    def test_normal_open_records_recent_file_after_success(self):
        editor = _TreeEditor()
        editor.memory = ke.ApplicationMemory()
        editor.memory["archive"] = {
            "preset": {"preset_info": {"ts": 123}}}
        editor.memory["recent_files"] = Mock()
        editor._load_archive = Mock(return_value=True)
        editor._apply_document_dimensions = Mock()
        editor._after_document_loaded = Mock()

        opened = editor._open_archive_path("work.klwp", True)

        self.assertTrue(opened)
        editor.memory["recent_files"].remember.assert_called_once_with(
            "work.klwp")

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
        owner.bind_all.assert_any_call(
            "<Control-k>", owner.services.on_command_palette_shortcut)
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
