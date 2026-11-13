# TrajViz for Homebrew

[TrajViz](https://github.com/rshu/TrajViz) analyzes coding-agent trajectories.
The Homebrew package includes the dashboards, command-line tools, and Python runtime.

## Install

Register the tap once so Homebrew can find `trajviz` by name.

```sh
brew tap rshu/trajviz
```

On Homebrew 6 or later, trust the TrajViz formula once. [Homebrew Tap Trust](https://docs.brew.sh/Tap-Trust)

```sh
brew trust --formula rshu/trajviz/trajviz
```

Then install TrajViz.

```sh
brew install trajviz
```

Homebrew installs a prebuilt bottle when one matches your system. Otherwise it
installs pinned Python wheels in an isolated environment. [Bottle releases](https://github.com/rshu/homebrew-trajviz/releases)

## Run

```sh
agent-trajviz
```

Open the local URL printed in your terminal. [TrajViz quickstart](https://rshu.github.io/TrajViz/stable/quickstart.html)

## Upgrade

```sh
brew update
brew upgrade trajviz
```

If `brew update` migrates your tap to `rshu/trajviz`, repeat the trust command
before upgrading.

## Maintaining the formula

1. Run [Update formula](https://github.com/rshu/homebrew-trajviz/actions/workflows/update.yml)
   with the published PyPI version. The workflow prepares a branch and starts the formula tests.
2. Run [Build bottles](https://github.com/rshu/homebrew-trajviz/actions/workflows/bottles.yml)
   on that branch. It tests the prebuilt packages and produces their checksums and Homebrew metadata.
3. Upload the tested bottles to the release URL in the metadata. Add the bottle
   block to the formula and merge the update into `main` after CI passes.

To prepare and test an update locally, install [uv](https://docs.astral.sh/uv/).

```sh
cd "$(brew --repository rshu/trajviz)"
uv run --with packaging==26.2 python .github/scripts/update_formula.py --version X.Y.Z
brew style Formula/trajviz.rb
brew install --build-from-source trajviz
brew test trajviz
brew audit --strict --online trajviz
```

If TrajViz is already installed, use `brew reinstall --build-from-source trajviz`
in the local test sequence. For packaging changes to an existing PyPI version,
pass `--revision N` to the generator. A new PyPI version resets the formula revision.
