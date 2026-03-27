#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Route PR checks deterministically based on a rubric config."""

from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class Check:
    id: str
    command: str
    working_directory: str | None = None


def _git_diff_name_only(base: str, head: str) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", base, head],
        check=True,
        capture_output=True,
        text=True,
    )
    files = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return files


def _git_diff_numstat(base: str, head: str) -> tuple[int, int]:
    result = subprocess.run(
        ["git", "diff", "--numstat", base, head],
        check=True,
        capture_output=True,
        text=True,
    )

    inserted = 0
    deleted = 0
    for line in result.stdout.splitlines():
        cols = line.split("\t")
        if len(cols) < 3:
            continue

        plus = cols[0]
        minus = cols[1]
        if plus.isdigit():
            inserted += int(plus)
        if minus.isdigit():
            deleted += int(minus)

    return inserted, deleted


def _matches_any(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def _dedupe_checks(checks: list[Check]) -> list[Check]:
    seen: set[tuple[str, str, str | None]] = set()
    out: list[Check] = []
    for check in checks:
        key = (check.id, check.command, check.working_directory)
        if key in seen:
            continue
        seen.add(key)
        out.append(check)
    return out


def _markdown_report(report: dict[str, Any]) -> str:
    changed_files = report["changed_files"]
    triggered_rules = report["triggered_rules"]
    selected_checks = report["selected_checks"]

    lines = [
        "## PR Rubric Routing Report",
        "",
        f"- Changed files: **{len(changed_files)}**",
        f"- Diff lines: **+{report['insertions']} / -{report['deletions']}**",
        (
            "- Large structural change: "
            f"**{'yes' if report['large_structural_change'] else 'no'}**"
        ),
    ]

    llm_reason = report.get("llm_recommended_reason")
    if llm_reason:
        lines.append(f"- LLM summary recommended: **yes** ({llm_reason})")
    else:
        lines.append("- LLM summary recommended: **no**")

    lines.extend(["", "### Triggered Rules"])
    if triggered_rules:
        for rule in triggered_rules:
            lines.append(f"- `{rule['id']}`: {rule['description']}")
    else:
        lines.append("- none")

    lines.extend(["", "### Selected Checks"])
    if selected_checks:
        for check in selected_checks:
            wd = check.get("working_directory") or "."
            lines.append(f"- `{check['id']}` (`{wd}`): `{check['command']}`")
    else:
        lines.append("- none")

    lines.extend(["", "### Changed Files"])
    if changed_files:
        for file in changed_files:
            lines.append(f"- `{file}`")
    else:
        lines.append("- none")

    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--json-out", required=True)
    parser.add_argument("--md-out", required=True)
    args = parser.parse_args()

    cfg_path = Path(args.config)
    config = yaml.safe_load(cfg_path.read_text())

    changed_files = _git_diff_name_only(args.base, args.head)
    insertions, deletions = _git_diff_numstat(args.base, args.head)

    thresholds = config.get("thresholds", {})
    large_change_files = int(thresholds.get("large_change_files", 50))
    large_change_lines = int(thresholds.get("large_change_lines", 1200))

    triggered_rules: list[dict[str, str]] = []
    selected_checks: list[Check] = []

    for rule in config.get("rules", []):
        rule_id = str(rule.get("id", "unknown"))
        rule_description = str(rule.get("description", ""))
        patterns = list(rule.get("paths", []))
        if not patterns:
            continue

        if any(_matches_any(path, patterns) for path in changed_files):
            triggered_rules.append({"id": rule_id, "description": rule_description})
            for check in rule.get("checks", []):
                selected_checks.append(
                    Check(
                        id=str(check["id"]),
                        command=str(check["command"]),
                        working_directory=check.get("working_directory"),
                    )
                )

    selected_checks = _dedupe_checks(selected_checks)

    large_structural_change = (
        len(changed_files) >= large_change_files
        or (insertions + deletions) >= large_change_lines
    )

    llm_reason: str | None = None
    if large_structural_change:
        llm_reason = (
            "diff exceeds configured thresholds "
            f"(files>={large_change_files} or lines>={large_change_lines})"
        )

    report = {
        "version": config.get("version", 1),
        "base": args.base,
        "head": args.head,
        "changed_files": changed_files,
        "insertions": insertions,
        "deletions": deletions,
        "triggered_rules": triggered_rules,
        "selected_checks": [
            {
                "id": check.id,
                "command": check.command,
                "working_directory": check.working_directory,
            }
            for check in selected_checks
        ],
        "large_structural_change": large_structural_change,
        "llm_recommended_reason": llm_reason,
    }

    Path(args.json_out).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    Path(args.md_out).write_text(_markdown_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
