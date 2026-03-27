#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Deterministic rubric checks used by PR routing."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

import yaml


def _changed_files() -> list[str]:
    env_file = Path(".rubric_changed_files.json")
    if not env_file.exists():
        return []

    payload = json.loads(env_file.read_text())
    files = payload.get("changed_files", [])
    return [str(file) for file in files]


def _docs_check(from_changed: bool) -> int:
    files = _changed_files() if from_changed else []
    doc_files = [
        Path(file)
        for file in files
        if file.endswith(".md")
        or file.startswith("website/docs/")
        or file.startswith("gcm/docs/")
    ]

    failures: list[str] = []
    for file in doc_files:
        if not file.exists():
            continue

        text = file.read_text(encoding="utf-8")
        if not re.search(r"^#", text, flags=re.MULTILINE):
            failures.append(f"{file}: missing markdown heading")

        if "\t" in text:
            failures.append(f"{file}: contains tab characters")

    if failures:
        for failure in failures:
            print(f"ERROR: {failure}")
        return 1

    print("docs-validation: ok")
    return 0


def _repro_check(from_changed: bool) -> int:
    files = _changed_files() if from_changed else []
    cfg_files = [
        Path(file)
        for file in files
        if file.startswith(("training/", "experiments/", "configs/"))
        and file.endswith((".yaml", ".yml", ".json", ".toml"))
    ]

    if not cfg_files:
        print("reproducibility-config: skipped (no changed config files)")
        return 0

    failures: list[str] = []
    seed_pattern = re.compile(r"\b(seed|random_seed)\b", re.IGNORECASE)
    for file in cfg_files:
        if not file.exists():
            continue

        text = file.read_text(encoding="utf-8")
        if not seed_pattern.search(text):
            failures.append(f"{file}: missing seed/random_seed")

    if failures:
        for failure in failures:
            print(f"ERROR: {failure}")
        return 1

    print("reproducibility-config: ok")
    return 0


def _ci_check(from_changed: bool) -> int:
    files = _changed_files() if from_changed else []
    yaml_files = [
        Path(file)
        for file in files
        if file.endswith((".yml", ".yaml"))
        and (file.startswith(".github/") or file == ".rubric.yml")
    ]

    failures: list[str] = []
    for file in yaml_files:
        if not file.exists():
            continue

        try:
            text = file.read_text(encoding="utf-8")
            list(yaml.safe_load_all(text))
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{file}: invalid YAML ({exc})")

    if failures:
        for failure in failures:
            print(f"ERROR: {failure}")
        return 1

    print("ci-yaml-validation: ok")
    return 0


def _run_shell(command: str, cwd: str | None) -> int:
    print(f"running: {command}")
    result = subprocess.run(command, shell=True, cwd=cwd)
    return int(result.returncode)


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    docs_parser = subparsers.add_parser("docs")
    docs_parser.add_argument("--from-changed", action="store_true")

    repro_parser = subparsers.add_parser("reproducibility")
    repro_parser.add_argument("--from-changed", action="store_true")

    ci_parser = subparsers.add_parser("ci")
    ci_parser.add_argument("--from-changed", action="store_true")

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--command", required=True)
    run_parser.add_argument("--cwd", default=None)

    args = parser.parse_args()
    if args.cmd == "docs":
        return _docs_check(from_changed=args.from_changed)
    if args.cmd == "reproducibility":
        return _repro_check(from_changed=args.from_changed)
    if args.cmd == "ci":
        return _ci_check(from_changed=args.from_changed)
    if args.cmd == "run":
        return _run_shell(args.command, args.cwd)

    raise RuntimeError("unknown command")


if __name__ == "__main__":
    raise SystemExit(main())
