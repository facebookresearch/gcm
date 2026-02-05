<!--
Copyright (c) Meta Platforms, Inc. and affiliates.
All rights reserved.
-->
# Contributing to `gpu-cluster-monitoring`

## Environment setup

A dev environment with Nvidia GPUs and slurm CLI commands provides a good foundation for GCM development.

The pinned dependencies were generated using Python 3.12, therefore it is recommended that you use 3.12 in your development environment.

You can create the environment via conda:
```shell
conda create -y --name py312 python==3.12
conda activate py312
# Common Conda Troubleshooting:
# if you're having issues activating the conda env
source activate base
# binaries like pip, nox should be pointing inside your conda env (`which pip`), if it's not:
conda install pip
conda deactivate
conda activate py312
```

Once you have a local copy of this repo, first install pinned development dependencies:
```shell
pip install -r dev-requirements.txt
```
Then install the package in editable mode `-e` without dependencies `--no-deps` (since they were installed in the previous step)
```shell
pip install --no-deps -e .
```
This will prevent you from needing to reinstall the package every time you make changes *except* if
* you make changes to `pyproject.toml` (e.g. adding a new entry to `[project.scripts]`)

After this step you should be able to run CLI commands locally:

```shell
$ gcm --help
...
$ health_checks --help
...
```

To run gcm collection exporting data to stdout:
```shell
$ gcm slurm_monitor --sink=stdout --once
...
```

Then run `pre-commit install` to install Git pre-commit hooks.
You only need to do this once.

## `nox`
`nox` is a test automation tool.
There are several workflows called "sessions" in this repository which are automated by `nox`.
To use `nox`, the general form is
```shell
nox -s $session_name
```
### Useful `nox` options
For more information, refer to `nox --help`
* `-R`: Reuses the virtual environment for the requested sessions from the previous invocations.
Speeds up runtime considerably.

### Tests
Tests live in [tests/](tests/).
To run the entire test suite in an isolated virtual environment, run `nox -s tests`. To get e2e tests signals you'll need to create a `.env` file with the tokens, similarly to [`.env.example`](../.env.example)
Alternatively, `pytest` is installed in your development environment, so you can invoke `pytest` directly.
Additional positional arguments to `nox` are forwarded to `pytest`, e.g. if you want to view `pytest`'s help message, run
```shell
nox -s tests -- --help
```
Analogously, if you want to run specific tests with a substring match,
```shell
nox -s tests -- -k 'test_something'  # runs tests including the string 'test_something'
```

### Formatting
To check formatting,
```shell
nox -s format
```
To format in-place, invoke `black` and `isort` directly.

### Static Analysis
```shell
nox -s lint
nox -s typecheck
```

For faster typechecking, feel free to use `dmypy`
```shell
dmypy start -- --show-error-codes  # only once to start the daemon
dmypy check gcm
```

## Pull Requests
Follow the same guidelines as described in https://www.internalfb.com/intern/wiki/Diff_Review/.

### Useful tools
* [`gh`](https://cli.github.com/): The GitHub CLI
* [`git-branchless`](https://github.com/arxanas/git-branchless): Easily move commit trees (better than `git rebase`)

### Tips
* If you're stuck, create a draft PR so that others can look at what you've changed.
* Feel free to amend commits and force push while you're iterating towards a reviewable state.
    * Corollary: If you need to make changes after your PR has been reviewed, **make a new commit** so that it's easy for reviewers to see what changed.
    Commits are squashed anyways when merging to `main`.
* Rebase your feature branch onto `main` often (`git-branchless move` is very useful for this). If you rebase, feel free to force push.

### Merging (stacked) PRs
These instructions depend on `git-branchless`.
Starting with the bottom of your stack,
1. Merge your PR in the GitHub UI.
1. On your local checkout, `pull` main.
1. If your PR has more than one commit, squash your local commits into a single one (`git rb -i $base_rev`).
1. `move` your local feature branch onto main. `git-branchless` should see that your feature branch is merged and remove it from your tree.
1. If you have no more PRs, then you're done. Otherwise, checkout the next PR in your stack (which should now be a direct child of main), force `push`, and go to (1).

## Updating dependencies
All direct dependencies are declared in [`pyproject.toml`](../pyproject.toml).
The transitive closure of these dependencies is locked and hash-checked to [`requirements.txt`](../requirements.txt) and [`dev-requirements.txt`](../dev-requirements.txt) using `pip-tools` for install and development dependencies, respectively.
To update these lockfiles, run `make $lockfile` where `lockfile` is either `requirements.txt` or `dev-requirements.txt`.


## Synchronizing your development environment to the lockfile
To keep your development environment in sync with the lockfile (i.e. add/update/remove dependencies), use `pip-sync`.
```shell
pip-sync dev-requirements.txt
pip install --no-deps -e .  # because this project is not specified in dev-requirements.txt
```

## Single-file binaries
Using `pyinstaller`, `gcm` and `health_checks` are also available as standalone executables in order to facilitate distribution to various platforms.
Currently only Linux is supported.

To build:
```shell
make gcm # or use `make health_checks` for Health Checks
```
The resulting binary should be `./dist/gcm/gcm`.

Similarly, to build health_checks:
```shell
make health_checks
```
The resulting binary should be `./dist/health_checks/health_checks`.

## Building the Debian package
To facilitate deployment to Ubuntu clusters (e.g. FAIR Cluster), a Debian package is built containing `gcm` and various `systemd` service files.
To build the package locally,
1. Ensure your working tree is clean. Commit or stash any dirty changes.
1. Run
    ```shell
    builddir=$(mktemp -d)
    gcm/bin/build_deb.sh $builddir
    ```
    which should yield a tree like
    ```
    > tree -L 2 $builddir
    /tmp/tmp.TrBFjHZe7q
    ├── gcm
    │   ├── CONTRIBUTING.md
    │   ├── LICENSE
    │   ├── Makefile
    │   ├── README.md
    │   ├── bin
    │   ├── build
    │   ├── debian
    │   ├── dev-requirements.txt
    │   ├── dist
    │   ├── docs
    │   ├── gcm
    │   ├── gcm.egg-info
    │   ├── gcm.spec
    │   ├── health_checks
    │   ├── health_checks.spec
    │   ├── mypy.ini
    │   ├── noxfile.py
    │   ├── pyproject.toml
    │   ├── requirements.txt
    │   ├── stubs
    │   ├── systemd
    │   └── tests
    ├── gcm-dbgsym_2023.2.9-1_amd64.ddeb
    ├── gcm_2023.2.9-1_amd64.build
    ├── gcm_2023.2.9-1_amd64.buildinfo
    ├── gcm_2023.2.9-1_amd64.changes
    ├── gcm_2023.2.9-1_amd64.deb
    ├── gcm_2023.2.9.orig.tar.gz
    ├── healthchecks-dbgsym_2023.2.9-1_amd64.ddeb
    └── healthchecks_2023.2.9-1_amd64.deb
    ```
1. Now you can copy any of the `.deb` files to the target machine and install it, e.g. `sudo dpkg -i /path/to/deb/file`.

## Further Reading
Refer to the files in [`docs/`](docs/).
