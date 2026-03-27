#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Execute selected rubric checks and emit a structured report."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path
from typing import Any


def _run_check(command: str, cwd: str | None) -> dict[str, Any]:
    start = time.time()
    completed = subprocess.run(
        command,
        shell=True,
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    elapsed_s = round(time.time() - start, 2)
    status = "passed" if completed.returncode == 0 else "failed"

    return {
        "command": command,
        "working_directory": cwd or ".",
        "status": status,
        "return_code": int(completed.returncode),
        "duration_seconds": elapsed_s,
        "stdout_tail": "\n".join(completed.stdout.splitlines()[-25:]),
        "stderr_tail": "\n".join(completed.stderr.splitlines()[-25:]),
    }


def _to_markdown(report: dict[str, Any]) -> str:
    lines = ["## Rubric Check Results", ""]
    checks = report.get("checks", [])

    if not checks:
        lines.append("No checks were selected by routing rules.")
        lines.append("")
        return "\n".join(lines)

    for check in checks:
        status_emoji = "✅" if check["status"] == "passed" else "❌"
        lines.extend(
            [
                f"### {status_emoji} {check['id']}",
                f"- Status: **{check['status']}**",
                f"- Command: `{check['command']}`",
                f"- Working directory: `{check['working_directory']}`",
                f"- Duration: `{check['duration_seconds']}s`",
            ]
        )

        if check["stderr_tail"]:
            lines.extend(
                [
                    "",
                    "<details><summary>stderr (tail)</summary>",
                    "",
                    "```",
                    check["stderr_tail"],
                    "```",
                    "</details>",
                ]
            )

        if check["stdout_tail"]:
            lines.extend(
                [
                    "",
                    "<details><summary>stdout (tail)</summary>",
                    "",
                    "```",
                    check["stdout_tail"],
                    "```",
                    "</details>",
                ]
            )

        lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--routing-json", required=True)
    parser.add_argument("--results-json", required=True)
    parser.add_argument("--results-md", required=True)
    args = parser.parse_args()

    routing = json.loads(Path(args.routing_json).read_text())
    selected_checks = routing.get("selected_checks", [])

    checks_output: list[dict[str, Any]] = []
    failed = False

    for selected in selected_checks:
        check_id = selected["id"]
        command = selected["command"]
        cwd = selected.get("working_directory")

        result = _run_check(command, cwd)
        result["id"] = check_id
        checks_output.append(result)
        if result["status"] != "passed":
            failed = True

    report = {
        "checks": checks_output,
        "failed": failed,
    }

    Path(args.results_json).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    Path(args.results_md).write_text(_to_markdown(report))

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
