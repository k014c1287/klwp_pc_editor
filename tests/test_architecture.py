from .support import *  # noqa: F401,F403

from klwp.commands import MoveModulesCommand, RemoveModulesCommand
from klwp.editor import EditorApp
from klwp.memory import ApplicationMemory


class ArchitectureRefactorTests(unittest.TestCase):
    def test_application_memory_keeps_responsibility_states_independent(self):
        memory = ApplicationMemory()
        archive = object()
        selected = object()

        memory.initialize_document({"archive": archive})
        memory.initialize_selection({"selected": selected})
        memory.initialize_preview({"preview_scroll": 0.5})
        memory["plugin_extension"] = "available"

        self.assertIs(memory["archive"], archive)
        self.assertIs(memory["selected"], selected)
        self.assertEqual(memory["preview_scroll"], 0.5)
        self.assertEqual(memory["plugin_extension"], "available")

    def test_edit_commands_return_selection_without_ui_dependencies(self):
        first = {"internal_title": "first"}
        second = {"internal_title": "second"}
        parent = [first, second]

        moved = MoveModulesCommand(parent, (second,), -1).execute()
        removed = RemoveModulesCommand(((first, parent),)).execute()

        self.assertEqual(parent, [second])
        self.assertEqual(moved["selection"], (second,))
        self.assertEqual(removed["selection"], ())

    def test_editor_app_composes_independent_features_instead_of_inheriting(self):
        base_names = {base.__name__ for base in EditorApp.__mro__}

        self.assertNotIn("AlignmentMixin", base_names)
        self.assertNotIn("LayerActionsMixin", base_names)
        self.assertNotIn("CommandPaletteMixin", base_names)
        self.assertNotIn("PngExportMixin", base_names)
        self.assertNotIn("AdbTransferMixin", base_names)
        self.assertNotIn("TimePreviewMixin", base_names)
