"""The serving command for monitors: pure construction, no vLLM needed."""

import tempfile
import unittest
from pathlib import Path

from monitor_experiment import monitor_serving as ms
from monitor_experiment.registry import Registry, RegistryError


class CommandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = Registry.load()

    def flag(self, command, name):
        return command[command.index(name) + 1]

    def test_a_qwen3_monitor_is_served_in_bf16_under_its_registry_name_with_the_reasoning_parser(self):
        command = ms.build_command(self.registry.monitor("qwen3-32b"), "/m/qwen3-32b", python="py", port=9001, tensor_parallel=2)
        self.assertEqual(command[:3], ["py", "-m", "vllm.entrypoints.openai.api_server"])
        self.assertEqual(self.flag(command, "--model"), "/m/qwen3-32b")
        self.assertEqual(self.flag(command, "--served-model-name"), "Qwen/Qwen3-32B")
        self.assertEqual(self.flag(command, "--dtype"), "bfloat16")
        self.assertEqual(self.flag(command, "--reasoning-parser"), "qwen3")
        self.assertEqual((self.flag(command, "--port"), self.flag(command, "--tensor-parallel-size"), self.flag(command, "--max-model-len")),
                         ("9001", "2", "32768"))
        self.assertNotIn("--enable-auto-tool-choice", command, "monitors do not call tools")
        self.assertNotIn("--rope-scaling", command)
        self.assertEqual(self.flag(command, "--generation-config"), "vllm")

    def test_other_families_get_dtype_auto_and_no_assumed_reasoning_parser(self):
        command = ms.build_command(self.registry.monitor("gpt-oss-120b"), "/m/gpt-oss")
        self.assertEqual(self.flag(command, "--dtype"), "auto")
        self.assertNotIn("--reasoning-parser", command)

    def test_a_longer_context_needs_a_yarn_factor_and_a_shorter_one_is_refused(self):
        monitor = self.registry.monitor("qwen3-32b")
        with self.assertRaisesRegex(ms.ServingError, "pass a YaRN factor"):
            ms.build_command(monitor, "/m", max_model_len=131072)
        command = ms.build_command(monitor, "/m", max_model_len=131072, yarn_factor=4)
        self.assertIn('"factor": 4', self.flag(command, "--rope-scaling"))
        self.assertIn('"original_max_position_embeddings": 32768', self.flag(command, "--rope-scaling"))
        with self.assertRaisesRegex(ms.ServingError, "below the 32768"):
            ms.build_command(monitor, "/m", max_model_len=16000)

    def test_bad_resources_and_placeholders_are_refused(self):
        monitor = self.registry.monitor("qwen3-32b")
        for kwargs in ({"tensor_parallel": 0}, {"gpu_memory_utilization": 0}, {"gpu_memory_utilization": 1.5}):
            with self.assertRaises(ms.ServingError):
                ms.build_command(monitor, "/m", **kwargs)
        with self.assertRaisesRegex(RegistryError, "placeholder"):
            ms.build_command(self.registry.monitor("gemma-large"), "/m")

    def test_model_directory_checks(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            with self.assertRaisesRegex(ms.ServingError, "no config.json"):
                ms.check_model_dir(d)
            (d / "config.json").write_text("{}")
            self.assertEqual(ms.check_model_dir(d), d)
            (d / ".download-incomplete").write_text("")
            with self.assertRaisesRegex(ms.ServingError, "interrupted"):
                ms.check_model_dir(d)

    def test_provenance_records_the_command_and_the_monitor_identity(self):
        monitor = self.registry.monitor("qwen3-14b")
        command = ms.build_command(monitor, "/m")
        record = ms.provenance(monitor, command, "0.11.0", "/m")
        self.assertEqual((record["vllm_version"], record["command"], record["monitor"]), ("0.11.0", command, "qwen3-14b"))
        self.assertEqual(record["monitor_identity"], monitor.identity())

    def test_the_registry_name_matches_what_the_cli_check_looks_for(self):
        for name in ("qwen3-14b", "qwen3-32b", "gpt-oss-120b"):
            monitor = self.registry.monitor(name)
            served = ms.build_command(monitor, "/m")[ms.build_command(monitor, "/m").index("--served-model-name") + 1]
            self.assertIn(monitor.model_id.split("/")[-1].lower(), served.lower())


if __name__ == "__main__":
    unittest.main()
