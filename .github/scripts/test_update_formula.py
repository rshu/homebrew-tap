"""Offline checks for the tap's Python target selection and release-lock pins."""

from __future__ import annotations

import importlib.util
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).with_name("update_formula.py")
SPEC = importlib.util.spec_from_file_location("update_formula", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
formula = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(formula)


def wheel(filename: str, **overrides: object) -> dict:
    return {
        "filename": filename,
        "packagetype": "bdist_wheel",
        "yanked": False,
        "url": f"https://example.invalid/{filename}",
        **overrides,
    }


def metadata(*files: dict) -> dict:
    return {"info": {"name": "example"}, "urls": list(files)}


def package(name: str, version: str, *markers: str, source: dict | None = None) -> dict:
    record = {"name": name, "version": version,
              "source": {"registry": "https://pypi.org/simple"} if source is None else source}
    if markers:
        record["resolution-markers"] = list(markers)
    return record


class OfflineTestCase(unittest.TestCase):
    def setUp(self) -> None:
        network = patch.object(formula.urllib.request, "urlopen", side_effect=AssertionError("No network in tests"))
        network.start()
        self.addCleanup(network.stop)


class WheelSelectionTests(OfflineTestCase):
    def test_native_wheel_matches_target_architecture_and_python_abi(self) -> None:
        targets = {
            "macos-arm64": "macosx_11_0_arm64",
            "macos-x86_64": "macosx_10_15_x86_64",
            "linux-arm64": "manylinux_2_28_aarch64",
            "linux-x86_64": "manylinux_2_28_x86_64",
        }
        wheels = [wheel(f"example-1.0-cp314-cp314-{platform}.whl") for platform in targets.values()]
        for key, platform in targets.items():
            with self.subTest(target=key):
                # Both a prior non-stable ABI and the free-threaded ABI must lose
                # to this target's ordinary CPython 3.14 build.
                candidates = metadata(
                    wheel(f"example-1.0-cp313-cp313-{platform}.whl"),
                    wheel(f"example-1.0-cp314-cp314t-{platform}.whl"),
                    *reversed(wheels),
                )
                self.assertEqual(formula.wheel_for(candidates, key)["filename"],
                                 f"example-1.0-cp314-cp314-{platform}.whl")

    def test_stable_abi_wheels_remain_compatible_with_python_314(self) -> None:
        for key, platform in {
            "macos-arm64": "macosx_11_0_arm64",
            "macos-x86_64": "macosx_10_15_x86_64",
            "linux-arm64": "manylinux2014_aarch64.manylinux_2_17_aarch64",
            "linux-x86_64": "manylinux2014_x86_64.manylinux_2_17_x86_64",
        }.items():
            with self.subTest(target=key):
                compatible = wheel(f"example-1.0-cp38-abi3-{platform}.whl")
                self.assertIs(formula.wheel_for(metadata(compatible), key), compatible)

    def test_rejects_unsupported_native_platform_and_abi(self) -> None:
        cases = {
            "macos-arm64": ["cp314-cp314-macosx_11_0_x86_64", "cp314-cp314-macosx_14_0_arm64",
                            "cp315-cp315-macosx_11_0_arm64", "cp314-cp314t-macosx_11_0_arm64"],
            "macos-x86_64": ["cp314-cp314-macosx_11_0_arm64", "cp314-cp314-macosx_14_0_x86_64"],
            "linux-arm64": ["cp314-cp314-manylinux_2_28_x86_64", "cp314-cp314-manylinux_2_29_aarch64",
                            "cp314-cp314-musllinux_1_2_aarch64"],
            "linux-x86_64": ["cp314-cp314-manylinux_2_28_aarch64", "cp314-cp314-manylinux_2_29_x86_64",
                             "cp313-cp313-manylinux_2_28_x86_64"],
        }
        for key, tags in cases.items():
            for tag in tags:
                with self.subTest(target=key, tag=tag), \
                        self.assertRaisesRegex(RuntimeError, f"No Python 3.14 wheel.*{key}"):
                    formula.wheel_for(metadata(wheel(f"example-1.0-{tag}.whl")), key)

    def test_platform_independent_wheel_is_shared_across_every_target(self) -> None:
        universal = wheel("example-1.0-py3-none-any.whl")
        for key in formula.PLATFORMS:
            with self.subTest(target=key):
                self.assertIs(formula.wheel_for(metadata(universal), key), universal)

    def test_yanked_wheel_and_source_archive_do_not_hide_supported_wheel(self) -> None:
        supported = wheel("example-1.0-py3-none-any.whl")
        files = metadata(
            wheel("example-1.0-cp314-cp314-macosx_11_0_arm64.whl", yanked=True),
            {"filename": "example-1.0.tar.gz", "packagetype": "sdist"},
            supported,
        )
        self.assertIs(formula.wheel_for(files, "macos-arm64"), supported)


class ReleaseConstraintTests(OfflineTestCase):
    def test_numpy_marker_uses_target_python_314_instead_of_host_python(self) -> None:
        lock = {"package": [
            package("numpy", "2.4.6", "python_full_version < '3.12'"),
            package("numpy", "2.5.1", "python_full_version >= '3.12'"),
            package("python-target", "1.0", "python_version == '3.14' and implementation_name == 'cpython'"),
        ]}
        host = formula.default_environment()
        host.update(python_version="3.8", python_full_version="3.8.1", implementation_name="pypy")
        with patch.object(formula, "default_environment", side_effect=lambda: host.copy()):
            for key in formula.PLATFORMS:
                with self.subTest(target=key):
                    self.assertEqual(formula.constraints_for(lock, key).splitlines(),
                                     ["numpy==2.5.1", "python-target==1.0"])

    def test_os_and_architecture_markers_use_each_cross_compilation_target(self) -> None:
        lock = {"package": [
            package("common", "1.0"),
            package("mac-arm", "1.0", "sys_platform == 'darwin' and platform_machine == 'arm64'"),
            package("linux-arm", "1.0", "platform_system == 'Linux' and platform_machine == 'aarch64'"),
            package("intel", "1.0", "platform_machine == 'x86_64'"),
            package("darwin", "1.0", "platform_system == 'Darwin' and os_name == 'posix'"),
            package("linux", "1.0", "sys_platform == 'linux' and os_name == 'posix'"),
            package("windows-only", "1.0", "sys_platform == 'win32'"),
        ]}
        expected = {
            "macos-arm64": {"common==1.0", "mac-arm==1.0", "darwin==1.0"},
            "macos-x86_64": {"common==1.0", "intel==1.0", "darwin==1.0"},
            "linux-arm64": {"common==1.0", "linux-arm==1.0", "linux==1.0"},
            "linux-x86_64": {"common==1.0", "intel==1.0", "linux==1.0"},
        }
        host = formula.default_environment()
        host.update(sys_platform="win32", os_name="nt", platform_system="Windows", platform_machine="AMD64")
        with patch.object(formula, "default_environment", side_effect=lambda: host.copy()):
            for key, pins in expected.items():
                with self.subTest(target=key):
                    self.assertEqual(set(formula.constraints_for(lock, key).splitlines()), pins)

    def test_multiple_resolution_markers_are_alternatives_and_local_sources_are_excluded(self) -> None:
        lock = {"package": [
            package("either-arm", "1.0", "platform_machine == 'arm64'", "platform_machine == 'aarch64'"),
            package("agent-trajviz", "0.3.1", source={"editable": "."}),
            package("local-package", "1.0", source={"directory": "../local"}),
        ]}
        for key in formula.PLATFORMS:
            with self.subTest(target=key):
                pins = formula.constraints_for(lock, key)
                self.assertEqual(pins.strip(), "either-arm==1.0" if key.endswith("arm64") else "")

    def test_resolver_receives_release_constraints_and_exact_target_without_network(self) -> None:
        constraints = "numpy==2.5.1\n"
        for key, (target, _, _) in formula.PLATFORMS.items():
            with self.subTest(target=key):
                def compile_offline(command: list[str], expected_target: str = target,
                                    **kwargs: object) -> subprocess.CompletedProcess:
                    self.assertEqual(command[command.index("--python-platform") + 1], expected_target)
                    self.assertEqual(command[command.index("--python-version") + 1], "3.14")
                    self.assertEqual(command[command.index("--only-binary") + 1], ":all:")
                    self.assertEqual(kwargs["input"], "agent-trajviz[app]==0.3.1\n")
                    self.assertEqual(Path(command[command.index("--constraints") + 1]).read_text(), constraints)
                    return subprocess.CompletedProcess(command, 0, "agent_trajviz==0.3.1\nnumpy==2.5.1\n", "")

                with patch.object(formula.subprocess, "run", side_effect=compile_offline) as compile_run:
                    self.assertEqual(formula.resolve("0.3.1", key, constraints),
                                     {"agent-trajviz": "0.3.1", "numpy": "2.5.1"})
                compile_run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
