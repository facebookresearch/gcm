# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import glob
from typing import Dict

import nox

SRC_DIRS = [
    "gcm",
]
INTERNAL_TESTS_GLOB = "**/tests/*_internal.py"


@nox.session
def tests(session: nox.Session) -> None:
    session.install("-r", "dev-requirements.txt")
    session.install("--no-deps", "-e", ".")
    env_fname = ".env"
    try:
        env = _env_from_file(env_fname)
    except FileNotFoundError:
        session.debug(
            f"File '{env_fname}' does not exist. Not running with modified environment."
        )
        env = None
    session.run(
        "pytest",
        "--ignore-glob",
        INTERNAL_TESTS_GLOB,
        "-n",
        "auto",
        *session.posargs,
        env=env,
    )


@nox.session
def internal_tests(session: nox.Session) -> None:
    session.install("-r", "dev-requirements.txt")
    session.install("--no-deps", "-e", ".")
    env_fname = ".env"
    try:
        env = _env_from_file(env_fname)
    except FileNotFoundError:
        session.debug(
            f"File '{env_fname}' does not exist. Not running with modified environment."
        )
        env = None
    internal_test_files = glob.glob(INTERNAL_TESTS_GLOB)
    session.run("pytest", *internal_test_files, "-n", "auto", *session.posargs, env=env)


def _env_from_file(fname: str) -> Dict[str, str]:
    with open(fname) as f:
        env = {}
        for line in f:
            k, v = line.rstrip().split("=", maxsplit=1)
            env[k] = v
        return env


@nox.session
def lint(session: nox.Session) -> None:
    session.install("-r", "dev-requirements.txt")
    session.install("--no-deps", "-e", ".")
    session.run(
        "flake8",
        "--per-file-ignores=gcm/_version.py:F401",
        *SRC_DIRS,
    )


@nox.session
def format(session: nox.Session) -> None:
    session.install("-r", "dev-requirements.txt")
    session.install("--no-deps", "-e", ".")
    session.run(
        "ufmt",
        "check",
        *SRC_DIRS,
    )


@nox.session
def typecheck(session: nox.Session) -> None:
    session.install("-r", "dev-requirements.txt")
    session.install("--no-deps", "-e", ".")
    session.run("mypy", *SRC_DIRS)
