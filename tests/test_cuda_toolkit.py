"""Exercise toolkit discovery in fresh batch shells without CUDA, Torch or Lmod."""

import os
from pathlib import Path
import shutil
import subprocess
import unittest

from tests.support import TempDir

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "mihai/cluster/cuda_toolkit.sh"
MODULE = r'''module() {
    printf '%s\n' "$*" >> "$TEST_MODULE_LOG"
    [[ "$1" == load && "$2" == "$TEST_EXPECT_MODULE" && "${TEST_LOAD_FAIL:-0}" == 0 ]] || return 1
    export PATH="$TEST_CUDA_ROOT/bin:$PATH"
}
'''
COMMAND = 'set -euo pipefail\n' + MODULE + r'''
source "$1"
configure_monitor_cuda
printf '%s\n' "$CUDA_HOME" "$CUDA_PATH" "$CUDACXX" "$MONITOR_NVCC_VERSION" "$(command -v nvcc)"
'''


class CudaToolkitTests(unittest.TestCase):
    def toolkit(self, directory, name, version):
        root = directory / name
        nvcc = root / "bin/nvcc"
        nvcc.parent.mkdir(parents=True)
        nvcc.write_text(f"#!/bin/sh\necho 'Cuda compilation tools, release {version}, V{version}.100'\n")
        nvcc.chmod(0o755)
        return root

    def environment(self, directory):
        old = self.toolkit(directory, "old cuda", "12.1")
        matching = self.toolkit(directory, "matching cuda", "12.9")
        python = directory / "serving python"
        python.write_text('#!/bin/sh\nprintf "%s\\n" "$TEST_TORCH_CUDA"\n')
        python.chmod(0o755)
        return {**os.environ, "PATH": str(old / "bin") + os.pathsep + os.environ["PATH"],
                "SERVING_PY": str(python), "CUDA_HOME": "", "CUDA_PATH": "", "CUDA_MODULE": "",
                "TEST_TORCH_CUDA": "12.9", "TEST_CUDA_ROOT": str(matching),
                "TEST_MODULE_LOG": str(directory / "modules.log"), "TEST_EXPECT_MODULE": "CUDA/12.9"}

    def run_helper(self, env):
        return subprocess.run(["bash", "-c", COMMAND, "bash", str(HELPER)], env=env,
                              text=True, capture_output=True)

    def test_fresh_batch_shell_loads_matching_module_and_exports_toolkit(self):
        with TempDir() as directory:
            env = self.environment(directory)
            tools = directory / "tools"
            tools.mkdir()
            for command in ("bash", "dirname", "readlink"):
                (tools / command).symlink_to(shutil.which(command))
            env["PATH"] = str(tools)  # No nvcc anywhere on PATH before module load.
            # An inherited default must not hide the correctly loaded toolkit.
            env["CUDA_HOME"] = "/nonexistent/cuda"
            result = self.run_helper(env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(Path(env["TEST_MODULE_LOG"]).read_text(), "load CUDA/12.9\n")
            root = env["TEST_CUDA_ROOT"]
            self.assertEqual(result.stdout.splitlines(), [root, root, root + "/bin/nvcc", "12.9", root + "/bin/nvcc"])

    def test_batch_shell_can_initialize_lmod_without_an_inherited_module_function(self):
        with TempDir() as directory:
            env = self.environment(directory)
            lmod = directory / "lmod"
            init = lmod / "init/bash"
            init.parent.mkdir(parents=True)
            init.write_text(MODULE)
            env["LMOD_CMD"] = str(lmod / "libexec/lmod")
            command = COMMAND.replace(MODULE, "unset -f module 2>/dev/null || true\n")
            result = subprocess.run(["bash", "-c", command, "bash", str(HELPER)], env=env,
                                    text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(Path(env["TEST_MODULE_LOG"]).read_text(), "load CUDA/12.9\n")

    def test_valid_explicit_toolkit_works_without_loading_a_module(self):
        with TempDir() as directory:
            env = self.environment(directory)
            env["CUDA_HOME"] = env["TEST_CUDA_ROOT"]
            result = self.run_helper(env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.splitlines()[0], env["TEST_CUDA_ROOT"])
            self.assertFalse(Path(env["TEST_MODULE_LOG"]).exists())

    def test_cuda_path_and_path_discovery_work_without_cuda_home(self):
        for setting in ("CUDA_PATH", "PATH"):
            with self.subTest(setting=setting), TempDir() as directory:
                env = self.environment(directory)
                env.pop("CUDA_HOME")
                env[setting] = (env["TEST_CUDA_ROOT"] if setting == "CUDA_PATH" else
                                env["TEST_CUDA_ROOT"] + "/bin:" + env["PATH"])
                result = self.run_helper(env)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertFalse(Path(env["TEST_MODULE_LOG"]).exists())

    def test_explicit_module_override_is_loaded_even_with_existing_toolkit(self):
        with TempDir() as directory:
            env = self.environment(directory)
            env["CUDA_HOME"] = env["TEST_CUDA_ROOT"]
            env["CUDA_MODULE"] = env["TEST_EXPECT_MODULE"] = "CUDA/12.9.1"
            result = self.run_helper(env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(Path(env["TEST_MODULE_LOG"]).read_text(), "load CUDA/12.9.1\n")

    def test_unavailable_module_fails_with_cluster_instructions(self):
        with TempDir() as directory:
            env = {**self.environment(directory), "TEST_LOAD_FAIL": "1"}
            result = self.run_helper(env)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Cannot load CUDA/12.9", result.stderr)
            self.assertIn("module spider CUDA", result.stderr)
            self.assertEqual(result.stdout, "")

    def test_wrong_compiler_after_module_load_is_rejected(self):
        with TempDir() as directory:
            env = self.environment(directory)
            env["TEST_CUDA_ROOT"] = str(directory / "old cuda")
            result = self.run_helper(env)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Need nvcc 12.9", result.stderr)
            self.assertIn("found 12.1", result.stderr)

    def test_cpu_only_serving_python_is_rejected_before_module_load(self):
        with TempDir() as directory:
            env = {**self.environment(directory), "TEST_TORCH_CUDA": "None"}
            result = self.run_helper(env)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("no recognizable CUDA runtime", result.stderr)
            self.assertFalse(Path(env["TEST_MODULE_LOG"]).exists())


if __name__ == "__main__":
    unittest.main()
