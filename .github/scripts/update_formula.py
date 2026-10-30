"""Resolve a published TrajViz release into checksummed Homebrew wheel resources.

Run with uv's packaging dependency, e.g.:
uv run --with packaging python .github/scripts/update_formula.py --version 0.3.1
"""

from __future__ import annotations

import argparse
import concurrent.futures
import gzip
import http.client
import json
import os
import re
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

import tomllib
from packaging.markers import Marker, default_environment
from packaging.tags import compatible_tags, cpython_tags, mac_platforms
from packaging.utils import parse_wheel_filename

ROOT = Path(__file__).resolve().parents[2]
PLATFORMS = {
    "macos-arm64": ("aarch64-apple-darwin", "on_macos", "on_arm"),
    "macos-x86_64": ("x86_64-apple-darwin", "on_macos", "on_intel"),
    "linux-arm64": ("aarch64-manylinux_2_28", "on_linux", "on_arm"),
    "linux-x86_64": ("x86_64-manylinux_2_28", "on_linux", "on_intel"),
}


def download(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "TrajViz-Homebrew-release", "Accept-Encoding": "gzip"},
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = response.read()
                return gzip.decompress(data) if response.headers.get("Content-Encoding") == "gzip" else data
        except (OSError, http.client.IncompleteRead, urllib.error.URLError):
            if attempt == 2:
                raise
            time.sleep(attempt + 1)
    raise AssertionError("unreachable")


def pypi(name: str, version: str = "") -> dict:
    suffix = f"/{version}" if version else ""
    return json.loads(download(f"https://pypi.org/pypi/{name}{suffix}/json"))


def platform_tags(key: str) -> dict:
    if key.startswith("macos"):
        platforms = list(mac_platforms((13, 0), "arm64" if key.endswith("arm64") else "x86_64"))
    else:
        arch = "aarch64" if key.endswith("arm64") else "x86_64"
        platforms = [f"manylinux_2_{minor}_{arch}" for minor in range(28, 16, -1)]
        platforms += [f"manylinux2014_{arch}"]
    tags = [*cpython_tags((3, 14), abis=["cp314"], platforms=platforms),
            *compatible_tags((3, 14), interpreter="cp314", platforms=platforms)]
    return {tag: index for index, tag in reversed(list(enumerate(tags)))}


def wheel_for(metadata: dict, key: str) -> dict:
    preferred = platform_tags(key)
    candidates = []
    for file in metadata["urls"]:
        if file["packagetype"] != "bdist_wheel" or file.get("yanked"):
            continue
        tags = parse_wheel_filename(file["filename"])[3]
        rank = min((preferred[tag] for tag in tags if tag in preferred), default=None)
        if rank is not None:
            candidates.append((rank, file["filename"], file))
    if not candidates:
        raise RuntimeError(f"No Python 3.14 wheel for {metadata['info']['name']} on {key}")
    return min(candidates, key=lambda row: row[:2])[2]


def constraints_for(lock: dict, key: str) -> str:
    environment = default_environment()
    environment.update(python_version="3.14", python_full_version="3.14.0",
                       implementation_version="3.14.0", implementation_name="cpython",
                       platform_python_implementation="CPython", os_name="posix",
                       sys_platform="darwin" if key.startswith("macos") else "linux",
                       platform_system="Darwin" if key.startswith("macos") else "Linux",
                       platform_machine=("arm64" if key.startswith("macos") else "aarch64")
                       if key.endswith("arm64") else "x86_64")
    pins = []
    for package in lock["package"]:
        if "registry" not in package["source"]:
            continue
        markers = package.get("resolution-markers", [])
        if markers and not any(Marker(marker).evaluate(environment) for marker in markers):
            continue
        pins.append(f"{package['name']}=={package['version']}")
    return "\n".join(pins) + "\n"


def resolve(version: str, key: str, constraints: str) -> dict[str, str]:
    command = [os.environ.get("UV", "uv"), "pip", "compile", "-", "--python-version", "3.14",
               "--python-platform", PLATFORMS[key][0], "--only-binary", ":all:",
               "--default-index", "https://pypi.org/simple", "--no-header", "--no-annotate",
               "--prerelease", "disallow"]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt") as constraint_file:
        constraint_file.write(constraints)
        constraint_file.flush()
        command.extend(["--constraints", constraint_file.name])
        result = subprocess.run(command, input=f"agent-trajviz[app]=={version}\n", text=True,
                                capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(f"Dependency resolution failed on {key}: {result.stderr}")
    packages = {}
    for line in result.stdout.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([^\s;]+)", line)
        if not match:
            raise RuntimeError(f"Unexpected resolver output: {line}")
        packages[match[1].replace("_", "-").lower()] = match[2]
    return packages


def resource(name: str, file: dict, indent: int = 2) -> str:
    space = " " * indent
    result = (f'{space}resource "{name}" do\n'
            f'{space}  url "{file["url"]}", using: :nounzip\n'
            f'{space}  sha256 "{file["digests"]["sha256"]}"\n'
            f'{space}end\n')
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", help="Published PyPI version; defaults to latest")
    args = parser.parse_args()
    if args.version and not re.fullmatch(r"\d+\.\d+\.\d+", args.version):
        raise SystemExit("Only stable semantic releases are supported")
    metadata = pypi("agent-trajviz", args.version or "")
    version = metadata["info"]["version"]
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise SystemExit("Only stable semantic releases are supported")
    lock = tomllib.loads(download(f"https://raw.githubusercontent.com/rshu/TrajViz/v{version}/uv.lock").decode())
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        resolved = dict(zip(PLATFORMS, pool.map(
            lambda key: resolve(version, key, constraints_for(lock, key)), PLATFORMS)))
        releases = sorted({(name, value) for packages in resolved.values() for name, value in packages.items()})
        fetched = list(pool.map(lambda item: pypi(*item), releases))
    all_metadata = dict(zip(releases, fetched))
    wheels = {
        key: {name: wheel_for(all_metadata[(name, value)], key) for name, value in packages.items()}
        for key, packages in resolved.items()
    }
    main_wheel = wheels["macos-arm64"].pop("agent-trajviz")
    for key in list(PLATFORMS)[1:]:
        if wheels[key].pop("agent-trajviz")["url"] != main_wheel["url"]:
            raise RuntimeError("TrajViz itself must remain a platform-independent wheel")
    shared = {
        name: file for name, file in wheels["macos-arm64"].items()
        if all(other.get(name, {}).get("url") == file["url"] for other in wheels.values())
    }
    header = f'''# Generated by .github/scripts/update_formula.py; do not edit resources by hand.
# Dependency versions follow TrajViz v{version}/uv.lock.
class Trajviz < Formula
  include Language::Python::Virtualenv

  desc "Analyze and visualize coding-agent trajectories"
  homepage "https://github.com/rshu/TrajViz"
  url "{main_wheel['url']}", using: :nounzip
  version "{version}"
  sha256 "{main_wheel['digests']['sha256']}"
  license "MIT"

  depends_on "libyaml"
  depends_on "python@3.14"

'''
    chunks = [header]
    for operating_system in ("on_macos", "on_linux"):
        chunks.append(f"  {operating_system} do\n")
        for key, (_, system, architecture) in PLATFORMS.items():
            if system != operating_system:
                continue
            chunks.append(f"    {architecture} do\n")
            for name, file in sorted(wheels[key].items()):
                if name not in shared:
                    chunks.append(resource(name, file, 6) + "\n")
            chunks[-1] = chunks[-1].rstrip() + "\n"
            chunks.append("    end\n\n")
        chunks[-1] = chunks[-1].rstrip() + "\n"
        chunks.append("  end\n\n")
    chunks.append("  # Preserve the relocatable library IDs supplied by upstream Python wheels.\n"
                  "  preserve_rpath\n\n")
    for name, file in sorted(shared.items()):
        chunks.append(resource(name, file) + "\n")
    template = (ROOT / ".github" / "scripts" / "formula_methods.rb").read_text()
    chunks.append(template)
    formula = ROOT / "Formula" / "trajviz.rb"
    content = "".join(chunks)
    # Atomic replacement keeps a failed update from truncating a working formula.
    with tempfile.NamedTemporaryFile(mode="w", dir=formula.parent, delete=False) as output:
        output.write(content)
        temporary = Path(output.name)
    temporary.chmod(0o644)
    temporary.replace(formula)
    print(f"TrajViz {version}: {len(shared)} shared resources; four platform wheel sets")


if __name__ == "__main__":
    main()
