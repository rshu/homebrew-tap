# TrajViz for Homebrew

Install the full TrajViz dashboard and command-line tools:

```sh
brew install rshu/tap/trajviz
agent-trajviz
```

Open <http://127.0.0.1:7860>. Configure optional model connections in **Settings**.

```sh
brew update
brew upgrade rshu/tap/trajviz
```

The package tracks stable [`agent-trajviz` releases on PyPI](https://pypi.org/project/agent-trajviz/).
For Python projects that import the library, continue using `pip install agent-trajviz`.

This upstream tap uses the release's tested dependency versions and pinned,
SHA-256-verified PyPI wheels in an isolated Homebrew
Python 3.14 environment. Installation does not resolve dependencies or modify
your existing Python environments. The formula includes dashboards, charts,
reports, model features and native compressed-session support. macOS and Linux
on Apple Silicon/ARM64 and Intel/x86-64 are checked in CI.

## Maintaining the package

After publishing a stable PyPI release, run the **Update formula** workflow with
the same version. It regenerates the dependency resources and opens a pull
request. Run the formula tests on that branch before merging.

To prepare an update locally, install [`uv`](https://docs.astral.sh/uv/), then run:

```sh
uv run --with packaging==26.2 python .github/scripts/update_formula.py --version 0.3.1
brew style Formula/trajviz.rb
brew audit --strict --online rshu/tap/trajviz
brew install --build-from-source rshu/tap/trajviz
brew test rshu/tap/trajviz
```

See the [TrajViz repository](https://github.com/rshu/TrajViz) for documentation,
supported native sessions and issue reports. This is an upstream-maintained tap;
the formula is not part of `homebrew/core`.
