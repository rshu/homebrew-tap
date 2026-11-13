# TrajViz for Homebrew

[TrajViz](https://github.com/rshu/TrajViz) analyzes coding-agent trajectories.
This tap installs its dashboards, CLI, and Python runtime. Tap once and trust
the formula on Homebrew 6 or later.

```sh
brew tap rshu/trajviz
brew trust --formula rshu/trajviz/trajviz
brew install trajviz
agent-trajviz
```

Open the local URL printed by `agent-trajviz`. See the [TrajViz documentation](https://rshu.github.io/TrajViz/)
for loading sessions, comparing runs, and configuring AI analysis.

## Upgrade

Run `brew update`. If Homebrew moves your existing tap to `rshu/trajviz`,
repeat the formula trust command above. Then upgrade with:

```sh
brew upgrade trajviz
```

Homebrew uses a prebuilt bottle when available and installs pinned wheels in an
isolated Python environment on other systems. To import the library in your own
Python project, install [`agent-trajviz` from PyPI](https://pypi.org/project/agent-trajviz/).

## Maintaining the formula

After publishing a stable PyPI release, run the **Update formula** workflow with
the same version. It regenerates the dependency resources, prepares an update
branch and starts the formula tests. An existing branch must match the generated
formula exactly. The workflow summary links to the prepared branch.

Run **Build bottles** on the prepared formula commit. The workflow tests the
installed archives and provides their checksums and Homebrew bottle metadata.
Upload the archives to a tap release using the versioned URL in that metadata,
then add the generated bottle block to the formula. Review the passing CI results
and merge the update into `main`.

To prepare an update locally, install [`uv`](https://docs.astral.sh/uv/), then run:

```sh
cd "$(brew --repository rshu/trajviz)"
uv run --with packaging==26.2 python .github/scripts/update_formula.py --version X.Y.Z
brew style Formula/trajviz.rb
brew install --build-from-source trajviz
brew test trajviz
brew audit --strict --online trajviz
```

For an already-installed version, use `brew reinstall --build-from-source trajviz`
to test local formula changes. Packaging-only changes use `--revision N` when
generating the same upstream version. Homebrew displays that revision as a suffix
such as `0.3.1_1`; the Python package remains `0.3.1`. New upstream versions reset
the packaging revision.
