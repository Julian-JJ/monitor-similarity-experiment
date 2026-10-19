"""Offline tests for the registries and the experiment spec."""

import tempfile
import unittest
from pathlib import Path

from monitor_experiment import registry as reg
from monitor_experiment import spec as sp

ROOT = Path(__file__).resolve().parents[1]
FP = {"prompts": "p", "tokenizer": "t"}


def base(**over):
    raw = {"name": "t", "monitor": "qwen3-14b", "rollout_sets": ["original_clean"], "grid": {"scope": ["cot"]}}
    raw.update(over)
    return raw


class RegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = reg.Registry.load()

    def test_the_committed_registries_load(self):
        self.assertEqual(self.registry.actor.model_id, "Qwen/Qwen3-14B")
        self.assertIn("qwen3-32b", self.registry.monitors)
        self.assertEqual(set(self.registry.sets), {"original_clean", "main_only_v1"})

    def test_relations_to_the_fixed_actor(self):
        want = {"qwen3-14b": "same_model", "qwen3-4b": "same_family_smaller", "qwen3-1.7b": "same_family_smaller",
                "qwen3-32b": "same_family_larger", "qwen3-30b-a3b": "same_family_other_architecture",
                "gpt-oss-120b": "different_family", "gemma-large": "different_family"}
        got = {n: m.relation_to(self.registry.actor) for n, m in self.registry.monitors.items()}
        self.assertEqual(got, want)
        self.assertTrue(set(got.values()) <= set(reg.RELATIONS))

    def test_placeholders_cannot_run_but_real_entries_can(self):
        self.assertIs(self.registry.monitor("qwen3-14b").runnable(), self.registry.monitor("qwen3-14b"))
        with self.assertRaisesRegex(reg.RegistryError, "placeholder"):
            self.registry.monitor("gemma-large").runnable()

    def test_identity_ignores_where_a_monitor_is_served(self):
        a = self.registry.monitor("qwen3-14b")
        moved = reg.Monitor(**{**{f: getattr(a, f) for f in a.__dataclass_fields__}, "base_url": "http://elsewhere:1/v1"})
        self.assertEqual(a.identity(), moved.identity())
        self.assertNotEqual(a.identity(), self.registry.monitor("qwen3-4b").identity())

    def test_unknown_names_and_planned_sets_give_clear_errors(self):
        with self.assertRaisesRegex(reg.RegistryError, "Unknown monitor"):
            self.registry.monitor("nope")
        with self.assertRaisesRegex(reg.RegistryError, "Unknown rollout set"):
            self.registry.load_set("nope")
        with tempfile.TemporaryDirectory() as empty:
            fresh = reg.Registry.load(root=Path(empty), config_dir=ROOT / "configs")
            with self.assertRaisesRegex(reg.RegistryError, "planned, not generated yet"):
                fresh.load_set("main_only_v1")

    def test_strict_validation_catches_typos(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "rollout_sets.toml").write_text((ROOT / "configs/rollout_sets.toml").read_text())
            text = (ROOT / "configs/monitors.toml").read_text()
            for broken, message in ((text.replace("thinking = true", "thinkin = true", 1), "unknown keys|missing"),
                                    (text.replace('architecture = "dense"', 'architecture = "dence"', 1), "architecture must be"),
                                    (text.replace("output_reserve = 16768", "output_reserve = 99999", 1), "smaller than context_tokens"),
                                    (text.replace("max_tokens = 16768", "max_tokens = 20000", 1), "exceeds output_reserve")):
                (d / "monitors.toml").write_text(broken)
                with self.assertRaisesRegex(reg.RegistryError, message):
                    reg.Registry.load(config_dir=d)
            with self.assertRaisesRegex(reg.RegistryError, "not found"):
                reg.Registry.load(config_dir=d / "missing")


class SpecParsingTests(unittest.TestCase):
    def test_minimal_spec_gets_defaults(self):
        spec = sp.parse_spec(base())
        self.assertEqual(spec.told, ("malicious", "benign"))
        self.assertEqual(spec.axes["task_context"], ["none"])
        self.assertEqual(spec.options["samples"], 4)
        self.assertEqual(spec.options["bin_size"], 6)

    def test_every_error_names_the_problem(self):
        cases = [({"extra": 1}, "Unknown top-level keys"), ({"grid": {}}, "grid.scope is required"),
                 ({"grid": {"scope": ["cot"], "colour": ["red"]}}, "Unknown grid axes"),
                 ({"grid": {"scope": ["thoughts"]}}, "not one of"),
                 ({"grid": {"scope": ["cot", "cot"]}}, "twice"),
                 ({"grid": {"scope": ["cot"], "task_context": ["execute"]}}, "not implemented"),
                 ({"grid": {"scope": ["cot"], "followup_visibility": ["all"]}}, "not implemented"),
                 ({"options": {"sample": 4}}, "Unknown options"),
                 ({"options": {"samples": 0}}, "at least 1"),
                 ({"told": ["both"]}, "told must be"),
                 ({"grid": {"scope": ["cot"], "partial_cot": ["half"]}}, "partial_cot"),
                 ({"grid": {"scope": ["cot"], "partial_cot": ["turns:1.5"]}}, "0 < p <= 1")]
        for override, message in cases:
            with self.assertRaisesRegex(sp.SpecError, message, msg=str(override)):
                sp.parse_spec(base(**override))
        with self.assertRaisesRegex(sp.SpecError, "exactly one"):
            sp.parse_spec(base(monitors=["qwen3-4b"]))
        raw = base()
        del raw["name"]
        with self.assertRaisesRegex(sp.SpecError, "Missing required key"):
            sp.parse_spec(raw)

    def test_partial_cot_parsing(self):
        self.assertEqual(sp.parse_partial_cot("off"), {})
        self.assertEqual(sp.parse_partial_cot("turns:0.25"), {"mode": "turns", "value": 0.25})
        self.assertEqual(sp.parse_partial_cot("tokens:1"), {"mode": "tokens", "value": 1.0})

    def test_overrides(self):
        raw = base()
        out = sp.apply_overrides(raw, ["grid.scope=action", "options.samples=2", "grid.task_context=plan",
                                       'grid.hierarchy="long-context"', "name=renamed"])
        self.assertEqual(out["grid"]["scope"], ["action"])
        self.assertEqual(out["options"]["samples"], 2)
        self.assertEqual(out["grid"]["task_context"], ["plan"])
        self.assertEqual(out["grid"]["hierarchy"], ["long-context"])
        self.assertEqual(out["name"], "renamed")
        self.assertEqual(raw["grid"]["scope"], ["cot"], "the original is not modified")
        with self.assertRaisesRegex(sp.SpecError, "path=value"):
            sp.apply_overrides(raw, ["nonsense"])


class ExpansionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = reg.Registry.load()

    def cells(self, **over):
        return sp.expand(sp.parse_spec(base(**over)), self.registry, FP)

    def test_grid_is_the_cross_product(self):
        raw = base(grid={"scope": ["action", "cot", "all"], "task_context": ["none", "plan"]})
        del raw["monitor"]
        raw["monitors"] = ["qwen3-4b", "qwen3-32b"]
        cells = sp.expand(sp.parse_spec(raw), self.registry, FP)
        self.assertEqual(len(cells), 2 * 3 * 2)
        self.assertEqual(len({c.cell_id for c in cells}), 12)
        self.assertEqual({c.monitor for c in cells}, {"qwen3-4b", "qwen3-32b"})

    def test_cell_ids_are_stable_and_depend_on_everything_that_matters(self):
        a = self.cells()[0]
        self.assertEqual(a.cell_id, self.cells()[0].cell_id)
        self.assertEqual(a.cell_id, self.cells(options={"samples": 9, "concurrency": 2, "item_limit": 3})[0].cell_id,
                         "samples, concurrency and item_limit do not change a unit's result")
        for change in ({"options": {"seed": 1}}, {"options": {"bin_size": 4}}, {"options": {"chunk_tokens": 8000}},
                       {"grid": {"scope": ["action"]}}, {"grid": {"scope": ["cot"], "task_context": ["plan"]}},
                       {"grid": {"scope": ["cot"], "partial_cot": ["turns:0.5"]}}, {"monitor": "qwen3-4b"}):
            self.assertNotEqual(a.cell_id, self.cells(**change)[0].cell_id, change)
        other = sp.expand(sp.parse_spec(base()), self.registry, {"prompts": "changed", "tokenizer": "t"})[0]
        self.assertNotEqual(a.cell_id, other.cell_id, "editing a prompt file changes every cell")

    def test_parameters_come_from_the_preset_and_options(self):
        cell = self.cells(options={"bin_size": 4})[0]
        self.assertEqual((cell.params["context_tokens"], cell.params["chunk_tokens"], cell.params["bin_size"]), (32768, 12000, 4))
        self.assertEqual(cell.params["scope"], "cot")
        self.assertEqual(self.cells(options={"chunk_tokens": 6000})[0].params["chunk_tokens"], 6000)
        self.assertEqual(cell.partial_cot, {})
        self.assertEqual(self.cells(grid={"scope": ["cot"], "partial_cot": ["tokens:0.5"]})[0].partial_cot,
                         {"mode": "tokens", "value": 0.5})

    def test_cells_the_monitor_cannot_support_are_rejected(self):
        with self.assertRaisesRegex(sp.SpecError, "needs 131072 tokens of context"):
            self.cells(grid={"scope": ["cot"], "hierarchy": ["long-context"]})
        with self.assertRaisesRegex(sp.SpecError, "reasoning_effort"):
            self.cells(grid={"scope": ["cot"], "reasoning": ["high"]})
        self.assertEqual(self.cells(monitor="gpt-oss-120b", grid={"scope": ["cot"], "reasoning": ["high"]})[0].label["reasoning"], "high")
        with self.assertRaisesRegex(reg.RegistryError, "Unknown monitor"):
            self.cells(monitor="nope")

    def test_committed_experiment_files_expand(self):
        files = sorted((ROOT / "configs/experiments").glob("*.toml"))
        self.assertTrue(files, "no experiment files committed")
        for path in files:
            cells = sp.expand(sp.load_spec(path), self.registry, FP)
            self.assertTrue(cells, path.name)


if __name__ == "__main__":
    unittest.main()
