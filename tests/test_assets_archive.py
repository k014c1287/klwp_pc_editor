from .support import *  # noqa: F401,F403


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
