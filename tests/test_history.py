from .support import *  # noqa: F401,F403


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
