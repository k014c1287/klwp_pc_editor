from .support import *  # noqa: F401,F403


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
