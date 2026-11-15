"""Partial-CoT transform and the plan book, on their own."""

import json
import unittest
from pathlib import Path

from monitor_experiment import hierarchy as h
from monitor_experiment import strategies as st
from tests.support import TempDir

words = lambda text: len(text.split())


def turns(sizes):
    out = []
    for i, n in enumerate(sizes):
        out.append({"turn": i + 1, "id": f"m{i}", "message_ids": [f"m{i}"], "content": "", "calls": [], "results": [],
                    "reasoning": " ".join(f"t{i}w{k}" for k in range(n))})
    return out


class PartialCotTests(unittest.TestCase):
    def test_no_config_means_no_transform(self):
        self.assertIsNone(st.partial_cot_transform({}, words))

    def test_turns_mode_keeps_the_first_fraction_of_turns(self):
        transform = st.partial_cot_transform({"mode": "turns", "value": 0.5}, words)
        out, stats = transform(turns([10, 10, 10, 10]))
        self.assertEqual([bool(t["reasoning"]) for t in out], [True, True, False, False])
        self.assertEqual((stats["turns_total"], stats["turns_with_reasoning_shown"]), (4, 2))
        self.assertEqual((stats["reasoning_tokens_total"], stats["reasoning_tokens_shown"]), (40, 20))
        self.assertAlmostEqual(stats["fraction_shown"], 0.5)
        # ceil: 0.3 of 4 turns keeps 2
        out, _ = st.partial_cot_transform({"mode": "turns", "value": 0.3}, words)(turns([5, 5, 5, 5]))
        self.assertEqual(sum(bool(t["reasoning"]) for t in out), 2)

    def test_tokens_mode_cuts_inside_the_straddling_turn(self):
        transform = st.partial_cot_transform({"mode": "tokens", "value": 0.5}, words)
        out, stats = transform(turns([10, 30]))  # total 40 -> keep 20: all of turn 1 (10), then 10 of turn 2
        self.assertEqual(words(out[0]["reasoning"]), 10)
        self.assertLessEqual(words(out[1]["reasoning"]), 10)
        self.assertGreater(words(out[1]["reasoning"]), 0)
        self.assertTrue(out[1]["reasoning"].startswith("t1w0"))
        self.assertEqual(stats["reasoning_tokens_total"], 40)
        self.assertLessEqual(stats["reasoning_tokens_shown"], 20)
        self.assertEqual(stats["reasoning_tokens_shown"], words(out[0]["reasoning"]) + words(out[1]["reasoning"]))

    def test_the_whole_reasoning_is_kept_at_one_and_nothing_else_changes(self):
        original = turns([5, 7])
        for mode in ("turns", "tokens"):
            out, stats = st.partial_cot_transform({"mode": mode, "value": 1.0}, words)(original)
            self.assertEqual([t["reasoning"] for t in out], [t["reasoning"] for t in original])
            self.assertEqual(stats["fraction_shown"], 1.0)
        self.assertEqual(original[0]["reasoning"].split()[0], "t0w0", "the input is not modified")

    def test_a_transcript_without_reasoning_reports_zero_total(self):
        out, stats = st.partial_cot_transform({"mode": "turns", "value": 0.5}, words)(turns([0, 0]))
        self.assertEqual((stats["reasoning_tokens_total"], stats["fraction_shown"]), (0, 0.0))

    def test_actions_and_visible_text_are_untouched(self):
        original = turns([10, 10])
        original[1]["content"] = "visible"
        original[1]["calls"] = [{"id": "c", "name": "tool", "arguments": "{}"}]
        out, _ = st.partial_cot_transform({"mode": "turns", "value": 0.5}, words)(original)
        self.assertEqual(out[1]["content"], "visible")
        self.assertEqual(out[1]["calls"], original[1]["calls"])
        self.assertEqual(out[1]["reasoning"], "")

    def test_the_transform_plugs_into_plan_and_shortens_the_rendered_text(self):
        from tests.support import messages
        prompts = h.load_prompts()
        params = {**h.default_params("cot"), "context_tokens": 4000, "output_reserve": 1000, "margin_tokens": 100,
                  "chunk_tokens": 300, "single_pass_if_fits": True}
        full = h.plan(messages("bank", "malicious", 4, words=40), params, words, prompts)
        cut = h.plan(messages("bank", "malicious", 4, words=40), params, words, prompts,
                     turns_transform=st.partial_cot_transform({"mode": "turns", "value": 0.5}, words))
        self.assertLess(cut["chunks"][0]["tokens"], full["chunks"][0]["tokens"])
        self.assertEqual(cut["partial_cot"]["turns_with_reasoning_shown"], 2)
        self.assertIsNone(full["partial_cot"])


TOOLS = {"bank": [{"name": "a", "description": "tool a"}]}


def book(path, k=2, prompts=None, tools=TOOLS, seed=0, attempts=2):
    return st.PlanBook(path, prompts or h.load_prompts(), tools, words, {"model": "m"}, k, seed, attempts)


class Scripted:
    def __init__(self, *replies):
        self.replies, self.prompts = list(replies), []

    def __call__(self, prompt, seed):
        self.prompts.append((prompt, seed))
        reply = self.replies.pop(0) if self.replies else "a fine plan"
        if isinstance(reply, dict):
            return reply
        return {"text": reply, "finish_reason": "stop", "usage": {"prompt_tokens": 5}, "latency_seconds": 0.1}


class PlanBookTests(unittest.TestCase):
    def test_plans_are_written_once_per_task_and_index_and_assigned_by_sample_modulo_k(self):
        with TempDir() as d:
            b = book(d / "p.jsonl", k=3)
            complete = Scripted("plan zero", "plan one", "plan two")
            made = b.ensure({"bank": "Please pay."}, complete)
            self.assertEqual(len(made), 3)
            self.assertEqual([b.get("bank", "Please pay.", s)["text"] for s in range(6)],
                             ["plan zero", "plan one", "plan two"] * 2)
            self.assertEqual(b.ensure({"bank": "Please pay."}, complete), [], "nothing missing the second time")
            self.assertEqual(len(complete.prompts), 3)

    def test_the_prompt_contains_the_task_and_tools_and_nothing_about_the_objective(self):
        with TempDir() as d:
            complete = Scripted()
            book(d / "p.jsonl", k=1).ensure({"bank": "Please pay."}, complete)
            prompt = complete.prompts[0][0]
            self.assertIn("Please pay.", prompt)
            self.assertIn("- a: tool a", prompt)
            self.assertNotIn("secondary", prompt.lower())
            self.assertNotIn("hidden", prompt.lower())

    def test_the_cache_survives_a_new_book_object_and_keys_on_everything_that_shaped_a_plan(self):
        with TempDir() as d:
            path = d / "p.jsonl"
            book(path, k=1).ensure({"bank": "Please pay."}, Scripted("cached plan"))
            reopened = book(path, k=1)
            self.assertEqual(reopened.get("bank", "Please pay.", 0)["text"], "cached plan")
            self.assertEqual(reopened.ensure({"bank": "Please pay."}, Scripted("never used")), [])
            other_tools = book(path, k=1, tools={"bank": [{"name": "a", "description": "changed"}]})
            with self.assertRaises(st.PlanError):
                other_tools.get("bank", "Please pay.", 0)
            with self.assertRaises(st.PlanError):
                reopened.get("bank", "A different task text", 0)
            with self.assertRaises(st.PlanError):
                book(path, k=1, seed=1).get("bank", "Please pay.", 0)
            changed = dict(h.load_prompts(), plan=h.load_prompts()["plan"] + " extra")
            with self.assertRaises(st.PlanError):
                book(path, k=1, prompts=changed).get("bank", "Please pay.", 0)

    def test_an_invalid_first_attempt_is_retried_with_a_new_seed(self):
        with TempDir() as d:
            complete = Scripted({"text": "cut off", "finish_reason": "length"}, "second try works")
            record = book(d / "p.jsonl", k=1).ensure({"bank": "t"}, complete)[0]
            self.assertEqual(record["text"], "second try works")
            self.assertEqual([a["valid"] for a in record["attempts"]], [False, True])
            self.assertEqual(complete.prompts[1][1], complete.prompts[0][1] + 1)

    def test_empty_overlong_and_exhausted_attempts_raise_without_storing_anything(self):
        with TempDir() as d:
            path = d / "p.jsonl"
            with self.assertRaisesRegex(st.PlanError, "empty plan"):
                book(path, k=1).ensure({"bank": "t"}, Scripted("   ", ""))
            with self.assertRaisesRegex(st.PlanError, "limit is 1000"):
                book(path, k=1).ensure({"bank": "t"}, Scripted("word " * 1001, "word " * 1001))
            with self.assertRaisesRegex(st.PlanError, "finish_reason"):
                book(path, k=1, attempts=1).ensure({"bank": "t"}, Scripted({"text": "x", "finish_reason": "length"}))
            self.assertFalse(path.exists() and path.read_text().strip(), "failed plans are never cached")

    def test_a_plan_at_the_token_limit_is_accepted(self):
        with TempDir() as d:
            record = book(d / "p.jsonl", k=1).ensure({"bank": "t"}, Scripted("word " * 1000))[0]
            self.assertEqual(record["tokens"], 1000)

    def test_stored_lines_are_json_without_the_models_reasoning(self):
        with TempDir() as d:
            book(d / "p.jsonl", k=1).ensure({"bank": "t"}, Scripted({"text": "p", "finish_reason": "stop", "reasoning": "private"}))
            line = json.loads((d / "p.jsonl").read_text().splitlines()[0])
            self.assertNotIn("private", json.dumps(line))
            self.assertEqual(set(line), {"plan_id", "task", "index", "text", "tokens", "prompt_sha256", "attempts", "created_at"})


def exec_book(path, k=2, prompts=None, tools=TOOLS, seed=0, attempts=2, max_turns=5):
    return st.ExecutionBook(path, prompts or h.load_prompts(), tools, words, {"model": "m"}, k, seed, attempts, max_turns=max_turns)


class ExecutionBookTests(unittest.TestCase):
    def test_executions_run_tool_loop_summarize_and_assign_by_sample_modulo_k(self):
        with TempDir() as d:
            b = exec_book(d / "e.jsonl", k=2)
            complete = Scripted(
                '<tool_call>{"name": "a", "arguments": {"amount": 10}}</tool_call>',
                '<tool_call>{"name": "end_task", "arguments": {}}</tool_call>',
                "summary zero",
                '<tool_call>{"name": "a", "arguments": {"amount": 20}}</tool_call>\n<tool_call>{"name": "end_task", "arguments": {}}</tool_call>',
                "summary one",
            )
            made = b.ensure({"bank": "Please pay."}, complete)
            self.assertEqual(len(made), 2)
            self.assertEqual([b.get("bank", "Please pay.", s)["text"] for s in range(4)],
                             ["summary zero", "summary one", "summary zero", "summary one"])
            self.assertEqual(made[0]["termination"], "end_task")
            self.assertEqual(made[0]["turns"], 2)
            self.assertTrue(made[0]["main_success"])
            self.assertEqual(made[0]["tool_calls"], ["a", "end_task"])
            self.assertEqual(b.ensure({"bank": "Please pay."}, complete), [], "cached on second ensure")

    def test_execution_prompts_contain_task_tools_and_history_and_no_objective(self):
        with TempDir() as d:
            complete = Scripted(
                '<tool_call>{"name": "a", "arguments": {}}</tool_call>',
                "Final answer without tool calls.",
                "summary text",
            )
            exec_book(d / "e.jsonl", k=1).ensure({"bank": "Please pay."}, complete)
            agent_p1, agent_p2, summary_p = [p for p, _ in complete.prompts]
            self.assertIn("Please pay.", agent_p1)
            self.assertIn("- a: tool a", agent_p1)
            self.assertIn("No steps taken yet.", agent_p1)
            self.assertIn("executed a({})", agent_p2)
            self.assertIn("Termination: final_answer | Main task success: True", summary_p)
            for p in (agent_p1, agent_p2, summary_p):
                self.assertNotIn("secondary", p.lower())

    def test_unknown_tools_and_bad_tool_json_are_reported_back_to_the_agent(self):
        with TempDir() as d:
            complete = Scripted(
                '<tool_call>{bad json}</tool_call>\n<tool_call>{"name": "missing_tool", "arguments": {}}</tool_call>',
                '<tool_call>{"name": "end_task", "arguments": {}}</tool_call>',
                "recovered summary",
            )
            rec = exec_book(d / "e.jsonl", k=1).ensure({"bank": "Please pay."}, complete)[0]
            self.assertEqual(rec["text"], "recovered summary")
            second_turn_prompt = complete.prompts[1][0]
            self.assertIn("Invalid tool_call JSON", second_turn_prompt)
            self.assertIn("ToolNotFoundError", second_turn_prompt)

    def test_execution_cache_keys_on_everything_that_shapes_execution(self):
        with TempDir() as d:
            path = d / "e.jsonl"
            exec_book(path, k=1).ensure({"bank": "Please pay."}, Scripted("no tools", "cached summary"))
            reopened = exec_book(path, k=1)
            self.assertEqual(reopened.get("bank", "Please pay.", 0)["text"], "cached summary")
            with self.assertRaises(st.PlanError):
                exec_book(path, k=1, max_turns=9).get("bank", "Please pay.", 0)
            with self.assertRaises(st.PlanError):
                exec_book(path, k=1, seed=1).get("bank", "Please pay.", 0)
            with self.assertRaises(st.PlanError):
                reopened.get("bank", "Different task", 0)

    def test_invalid_summary_retries_and_rejects_when_exhausted(self):
        with TempDir() as d:
            complete = Scripted("done", {"text": "cut", "finish_reason": "length"}, "valid summary")
            rec = exec_book(d / "e.jsonl", k=1).ensure({"bank": "t"}, complete)[0]
            self.assertEqual(rec["text"], "valid summary")
            self.assertEqual([a["valid"] for a in rec["attempts"]], [False, True])
            with self.assertRaisesRegex(st.PlanError, "limit is 1000"):
                exec_book(d / "e2.jsonl", k=1).ensure({"bank": "t"}, Scripted("done", "word " * 1001, "word " * 1001))


class ComparisonBookTests(unittest.TestCase):
    def test_comparisons_are_cached_per_item_scope_partial_cot_and_plan_without_seeing_the_objective(self):
        from monitor_experiment import spec as sp
        from tests.support import make_project
        with TempDir() as root:
            registry = make_project(root)
            items = registry.load_set("original_clean").items
            item = items[0]
            prompts = h.load_prompts()
            cell = sp.expand(sp.parse_spec({"name": "t", "monitor": "qwen3-14b", "rollout_sets": ["original_clean"],
                                            "grid": {"scope": ["cot"], "task_context": ["plan_compare"]}}),
                             registry, {"prompts": "p", "tokenizer": "t"})[0]
            cb = st.ComparisonBook( Path(root) / "comp.jsonl", prompts, words, {"model": "m"}, seed=0)
            plan_record = {"plan_id": "plan-123", "text": "1. Call tool_0.\n2. Verify."}
            complete = Scripted("The agent followed step 1 and called tool_1 in turn 2.")
            first = cb.ensure_one(item, plan_record, cell, complete)
            second = cb.ensure_one(item, plan_record, cell, complete)
            self.assertEqual(first["comparison_id"], second["comparison_id"])
            self.assertEqual(len(complete.prompts), 1, "reused across told objectives and samples")
            prompt = complete.prompts[0][0]
            self.assertIn("1. Call tool_0.", prompt)
            self.assertIn("START OF AGENT TRANSCRIPT", prompt)
            self.assertNotIn("ACCT-9", prompt)
            self.assertNotIn("split payments", prompt)
            reopened = st.ComparisonBook(Path(root) / "comp.jsonl", prompts, words, {"model": "m"}, seed=0)
            self.assertEqual(reopened.ensure_one(item, plan_record, cell, Scripted("unused"))["text"], first["text"])


if __name__ == "__main__":
    unittest.main()
