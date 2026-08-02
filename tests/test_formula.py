from .support import *  # noqa: F401,F403


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
