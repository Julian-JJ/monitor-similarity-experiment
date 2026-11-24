"""Exercise toolkit discovery in fresh batch shells without CUDA, Torch or Lmod."""

import os
import json
from pathlib import Path
import shutil
import shlex
import subprocess
import sys
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
        ninja = directory / "ninja"
        ninja.write_text("#!/bin/sh\necho 1.13.0\n")
        ninja.chmod(0o755)
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

    def run_helper_with_sampling(self, env):
        command = COMMAND + 'printf "%s\\n" "${VLLM_USE_FLASHINFER_SAMPLER:-unset}" "$MONITOR_CUDA_JIT" "$MONITOR_CUDA_MODULE"\n'
        return subprocess.run(["bash", "-c", command, "bash", str(HELPER)], env=env, text=True, capture_output=True)

    def test_unavailable_module_falls_back_to_native_sampling(self):
        with TempDir() as directory:
            env = {**self.environment(directory), "TEST_LOAD_FAIL": "1"}
            tools = directory / "tools"
            tools.mkdir()
            for command in ("bash", "dirname", "readlink"):
                (tools / command).symlink_to(shutil.which(command))
            env["PATH"] = str(tools)   # Nothing else can provide nvcc.
            result = self.run_helper_with_sampling(env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("disabled FlashInfer JIT", result.stderr)
            self.assertEqual(result.stdout.splitlines()[-3:], ["0", "no", "none (FlashInfer JIT disabled)"])

    def test_wrong_compiler_without_a_requested_module_falls_back(self):
        with TempDir() as directory:
            env = self.environment(directory)
            env["TEST_CUDA_ROOT"] = str(directory / "old cuda")
            result = self.run_helper_with_sampling(env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.splitlines()[-3:], ["0", "no", "none (FlashInfer JIT disabled)"])

    def test_unavailable_requested_module_fails_with_cluster_instructions(self):
        with TempDir() as directory:
            env = {**self.environment(directory), "TEST_LOAD_FAIL": "1",
                   "CUDA_MODULE": "CUDA/13.0", "TEST_EXPECT_MODULE": "CUDA/13.0"}
            result = self.run_helper(env)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Cannot load CUDA/13.0", result.stderr)
            self.assertIn("module spider CUDA", result.stderr)
            self.assertEqual(result.stdout, "")

    def test_requested_module_with_wrong_compiler_still_fails(self):
        with TempDir() as directory:
            env = self.environment(directory)
            env["TEST_CUDA_ROOT"] = str(directory / "old cuda")
            env["CUDA_MODULE"] = env["TEST_EXPECT_MODULE"] = "CUDA/12.9"
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

    def test_ninja_in_serving_environment_is_added_to_path(self):
        with TempDir() as directory:
            env = self.environment(directory)
            self.assertNotIn(str(directory), env["PATH"].split(os.pathsep))
            command = COMMAND + 'printf "%s\\n" "$MONITOR_NINJA_PATH" "$MONITOR_NINJA_VERSION"\n'
            result = subprocess.run(["bash", "-c", command, "bash", str(HELPER)], env=env, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.splitlines()[-2:], [str(directory / "ninja"), "1.13.0"])

    def test_missing_ninja_stops_before_launching_server(self):
        with TempDir() as directory:
            env = self.environment(directory)
            (directory / "ninja").unlink()
            tools = directory / "tools"
            tools.mkdir()
            for command in ("bash", "dirname", "readlink"):
                (tools / command).symlink_to(shutil.which(command))
            env["PATH"] = str(tools)
            env["CUDA_HOME"] = env["TEST_CUDA_ROOT"]
            result = self.run_helper(env)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("FlashInfer needs ninja on PATH", result.stderr)

    def test_server_wrapper_sets_actual_child_environment_and_records_provenance(self):
        from monitor_experiment.monitor_serving import cuda_launch_command
        with TempDir() as directory:
            env = self.environment(directory)
            env["CUDA_HOME"] = env["TEST_CUDA_ROOT"]
            python = Path(env["SERVING_PY"])
            python.write_text('#!/bin/sh\nif [ "$1" = "-c" ] && [ "$2" = "import torch; print(torch.version.cuda)" ]; then\n'
                              'printf "%s\\n" "$TEST_TORCH_CUDA"\nelse\nexec ' + shlex.quote(sys.executable) + ' "$@"\nfi\n')
            manifest = directory / "serving.json"
            manifest.write_text(json.dumps({"monitor": "gemma4-e2b", "command": ["original"]}))
            code = "import json,os,shutil; print(json.dumps({'cuda_home':os.environ['CUDA_HOME'],'ninja':shutil.which('ninja'),'nvcc':shutil.which('nvcc')}))"
            command = cuda_launch_command([str(python), "-c", code], ROOT, manifest)
            result = subprocess.run(command, env=env, text=True, capture_output=True, cwd=directory)
            self.assertEqual(result.returncode, 0, result.stderr)
            child = json.loads(result.stdout.splitlines()[-1])
            record = json.loads(manifest.read_text())
            self.assertEqual(record["command"], ["original"])
            self.assertEqual(record["cuda_environment"]["cuda_home"], child["cuda_home"])
            self.assertEqual(record["cuda_environment"]["nvcc"], child["nvcc"])
            self.assertEqual(child["ninja"], str(directory / "ninja"))
            self.assertEqual(record["cuda_environment"]["ninja_version"], "1.13.0")


if __name__ == "__main__":
    unittest.main()
