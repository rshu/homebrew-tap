# TrajViz for Homebrew

Install the full TrajViz dashboard and command-line tools. The first two
commands are one-time setup. The trust step applies to Homebrew 6 and later.

```sh
brew tap rshu/tap
brew trust --formula rshu/tap/trajviz
brew install trajviz
agent-trajviz
```

Open <http://127.0.0.1:7860>. Configure optional model connections in
**AI Trajectory Analysis → Settings**.

For the Converge comparison dashboard, run:

```sh
agent-trajviz-converge-app --data-root /path/to/trajectories
```

It opens on port 7861. `agent-trajviz-converge` provides headless comparisons.

Inspect saved AWE analyses and export an offline report without an API key:

```sh
agent-trajviz-awe inspect /path/to/saved-run.zip
agent-trajviz-awe export /path/to/saved-run.zip --output report.html
```

The dashboard's **AWE → Trajectory** view inspects the loaded session directly;
reference-based attribution is optional. **Saved runs & evaluation** provides
recorded evidence, graphs and reports. Evaluation operations and optional model
connections have their own session settings; see the
[AWE guide](https://github.com/rshu/TrajViz/blob/main/docs/awe.md).

```sh
brew update
brew upgrade trajviz
```

The package tracks stable [`agent-trajviz` releases on PyPI](https://pypi.org/project/agent-trajviz/).
For Python projects that import the library, continue using `pip install agent-trajviz`.

Homebrew installs a prebuilt bottle when one matches your platform. Otherwise,
the formula installs the release's pinned, SHA-256-verified PyPI wheels into
its isolated Python 3.14 environment. The formula includes dashboards, charts,
reports, model features and native compressed-session support.

## Maintaining the package

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
cd "$(brew --repository rshu/tap)"
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

See the [TrajViz repository](https://github.com/rshu/TrajViz) for documentation,
supported native sessions and issue reports. This is an upstream-maintained tap;
the formula is not part of `homebrew/core`.
