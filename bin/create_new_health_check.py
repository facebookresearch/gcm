#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Scaffold tool for creating new GCM health checks."""

import argparse
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CHECK_PREFIX = "check_"
_PREFIX_LEN = len(_CHECK_PREFIX)

# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

CHECK_FILE_SIMPLE = '''\
# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""TODO: describe what {check_name} checks."""

from collections.abc import Collection
from dataclasses import dataclass
from typing import Optional, Protocol

import click

from gcm.health_checks.check_utils.runtime import HealthCheckRuntime
from gcm.health_checks.click import (
    common_arguments,
    telemetry_argument,
    timeout_argument,
)
from gcm.health_checks.types import CHECK_TYPE, CheckEnv, ExitCode, LOG_LEVEL
from gcm.monitoring.click import heterogeneous_cluster_v1_option
from gcm.monitoring.features.gen.generated_features_healthchecksfeatures import (
    FeatureValueHealthChecksFeatures,
)
from gcm.schemas.health_check.health_check_name import HealthCheckName
from typeguard import typechecked


class {PascalName}Check(CheckEnv, Protocol):
    """Provide a class stub definition."""

    def run(self) -> None:
        ...


@dataclass
class {PascalName}CheckImpl:
    """Implement the {check_name} check."""

    cluster: str
    type: str
    log_level: str
    log_folder: str

    def run(self) -> None:
        """TODO: implement the check logic."""
        raise NotImplementedError


@click.command()
@common_arguments
@timeout_argument
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.pass_obj
@typechecked
def {check_name}(
    obj: Optional[{PascalName}Check],
    cluster: str,
    type: CHECK_TYPE,
    log_level: LOG_LEVEL,
    log_folder: str,
    timeout: int,
    sink: str,
    sink_opts: Collection[str],
    verbose_out: bool,
    heterogeneous_cluster_v1: bool,
) -> None:
    """TODO: short description of {check_name}."""
    if not obj:
        obj = {PascalName}CheckImpl(cluster, type, log_level, log_folder)

    with HealthCheckRuntime(
        cluster=cluster,
        check_type=type,
        log_level=log_level,
        log_folder=log_folder,
        sink=sink,
        sink_opts=sink_opts,
        verbose_out=verbose_out,
        heterogeneous_cluster_v1=heterogeneous_cluster_v1,
        health_check_name=HealthCheckName.CHECK_{UPPER_NAME},
        killswitch_getter=lambda: FeatureValueHealthChecksFeatures()
        .get_healthchecksfeatures_disable_check_{name}(),
    ) as rt:
        # TODO: implement check logic; pass timeout to impl, e.g. obj.run(timeout, rt.logger)
        # Call rt.finish(ExitCode.OK, "msg") when done
        rt.finish(ExitCode.UNKNOWN, "Not implemented yet")
'''

CHECK_FILE_GROUP = '''\
# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""TODO: describe what {check_name} checks."""

from collections.abc import Collection
from dataclasses import dataclass
from typing import Optional, Protocol

import click

from gcm.health_checks.check_utils.runtime import HealthCheckRuntime
from gcm.health_checks.click import (
    common_arguments,
    telemetry_argument,
    timeout_argument,
)
from gcm.health_checks.types import CHECK_TYPE, CheckEnv, ExitCode, LOG_LEVEL
from gcm.monitoring.click import heterogeneous_cluster_v1_option
from gcm.monitoring.features.gen.generated_features_healthchecksfeatures import (
    FeatureValueHealthChecksFeatures,
)
from gcm.schemas.health_check.health_check_name import HealthCheckName
from typeguard import typechecked


class {PascalName}Check(CheckEnv, Protocol):
    """Provide a class stub definition."""

    def run(self) -> None:
        ...


@dataclass
class {PascalName}CheckImpl:
    """Implement the {check_name} check."""

    cluster: str
    type: str
    log_level: str
    log_folder: str

    def run(self) -> None:
        """TODO: implement the check logic."""
        raise NotImplementedError


@click.group()
def {check_name}() -> None:
    """TODO: short description of the {check_name} group."""


@{check_name}.command()
@common_arguments
@timeout_argument
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.pass_obj
@typechecked
def example_subcommand(
    obj: Optional[{PascalName}Check],
    cluster: str,
    type: CHECK_TYPE,
    log_level: LOG_LEVEL,
    log_folder: str,
    timeout: int,
    sink: str,
    sink_opts: Collection[str],
    verbose_out: bool,
    heterogeneous_cluster_v1: bool,
) -> None:
    """TODO: short description of this subcommand."""
    if not obj:
        obj = {PascalName}CheckImpl(cluster, type, log_level, log_folder)

    with HealthCheckRuntime(
        cluster=cluster,
        check_type=type,
        log_level=log_level,
        log_folder=log_folder,
        sink=sink,
        sink_opts=sink_opts,
        verbose_out=verbose_out,
        heterogeneous_cluster_v1=heterogeneous_cluster_v1,
        health_check_name=HealthCheckName.CHECK_{UPPER_NAME}_EXAMPLE_SUBCOMMAND,
        killswitch_getter=lambda: FeatureValueHealthChecksFeatures()
        .get_healthchecksfeatures_disable_check_{name}_example_subcommand(),
    ) as rt:
        # TODO: implement check logic; pass timeout to impl, e.g. obj.run(timeout, rt.logger)
        # Call rt.finish(ExitCode.OK, "msg") when done
        rt.finish(ExitCode.UNKNOWN, "Not implemented yet")
'''

TEST_FILE = '''\
# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Test the {check_name} health-check."""

import logging
from dataclasses import dataclass
from pathlib import Path

import pytest
from click.testing import CliRunner
from gcm.health_checks.checks.{check_name} import {check_name}
from gcm.health_checks.types import ExitCode


@dataclass
class Fake{PascalName}CheckImpl:
    """Supply pregenerated output instead of running the real check."""

    cluster: str = "test cluster"
    type: str = "prolog"
    log_level: str = "INFO"
    log_folder: str = "/tmp"

    def run(self) -> None:
        """No-op for testing."""
        pass


@pytest.mark.parametrize(
    ("expected_exit_code",),
    [
        # TODO: add real test cases
        (ExitCode.UNKNOWN,),
    ],
)
def test_{check_name}(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    expected_exit_code: ExitCode,
) -> None:
    """Invoke the {check_name} command."""
    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    fake_impl = Fake{PascalName}CheckImpl()
    result = runner.invoke(
        {check_name},
        f"fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing",
        obj=fake_impl,
    )

    assert result.exit_code == expected_exit_code.value
'''

TEST_FILE_GROUP = '''\
# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Test the {check_name} health-check."""

import logging
from dataclasses import dataclass
from pathlib import Path

import pytest
from click.testing import CliRunner
from gcm.health_checks.checks.{check_name} import example_subcommand
from gcm.health_checks.types import ExitCode


@dataclass
class Fake{PascalName}CheckImpl:
    """Supply pregenerated output instead of running the real check."""

    cluster: str = "test cluster"
    type: str = "prolog"
    log_level: str = "INFO"
    log_folder: str = "/tmp"

    def run(self) -> None:
        """No-op for testing."""
        pass


@pytest.mark.parametrize(
    ("expected_exit_code",),
    [
        # TODO: add real test cases
        (ExitCode.UNKNOWN,),
    ],
)
def test_example_subcommand(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    expected_exit_code: ExitCode,
) -> None:
    """Invoke the example_subcommand of {check_name}."""
    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    fake_impl = Fake{PascalName}CheckImpl()
    result = runner.invoke(
        example_subcommand,
        f"fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing",
        obj=fake_impl,
    )

    assert result.exit_code == expected_exit_code.value
'''

DOC_FILE_GROUP = """\
# {dash_name}

TODO: describe what this health check group monitors.

## Subcommands

| Subcommand | Purpose | Key Feature |
|------------|---------|-------------|
| [`example-subcommand`](./example-subcommand.md) | TODO: purpose | TODO: key feature |

## Quick Start

### Run Example Subcommand
```shell
health_checks {dash_name} example-subcommand [CLUSTER] app
```

### With Telemetry
```shell
health_checks {dash_name} example-subcommand \\
  --sink otel \\
  --sink-opts "log_resource_attributes={\'attr_1\': \'value1\'}" \\
  [CLUSTER] \\
  app
```
"""

DOC_FILE_GROUP_SUBCOMMAND = """\
# example-subcommand

## Overview
TODO: describe what this subcommand checks.

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--timeout` | Integer | 300 | Seconds until the check command times out |
| `--sink` | String | do_nothing | Telemetry sink destination |
| `--sink-opts` | Multiple | - | Sink-specific configuration |
| `--verbose-out` | Flag | False | Display detailed output |
| `--log-level` | Choice | INFO | DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `--log-folder` | String | `/var/log/fb-monitoring` | Log directory |
| `--heterogeneous-cluster-v1` | Flag | False | Enable heterogeneous cluster support |

## Exit Conditions

| Exit Code | Description |
|-----------|-------------|
| **OK (0)** | Feature flag disabled (killswitch active) |
| **OK (0)** | TODO: describe passing condition |
| **CRITICAL (2)** | TODO: describe failing condition |
| **UNKNOWN (3)** | Check not yet implemented |

## Usage Examples

### Basic Check
```shell
health_checks {dash_name} example-subcommand [CLUSTER] app
```

### With Telemetry
```shell
health_checks {dash_name} example-subcommand \\
  --sink otel \\
  --sink-opts "log_resource_attributes={\'attr_1\': \'value1\'}" \\
  [CLUSTER] \\
  app
```
"""

DOC_FILE = """\
# {dash_name}

## Overview
TODO: describe what this health check monitors.

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--timeout` | Integer | 300 | Seconds until the check command times out |
| `--sink` | String | do_nothing | Telemetry sink destination |
| `--sink-opts` | Multiple | - | Sink-specific configuration |
| `--verbose-out` | Flag | False | Display detailed output |
| `--log-level` | Choice | INFO | DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `--log-folder` | String | `/var/log/fb-monitoring` | Log directory |
| `--heterogeneous-cluster-v1` | Flag | False | Enable heterogeneous cluster support |

## Exit Conditions

| Exit Code | Description |
|-----------|-------------|
| **OK (0)** | Feature flag disabled (killswitch active) |
| **OK (0)** | TODO: describe passing condition |
| **CRITICAL (2)** | TODO: describe failing condition |
| **UNKNOWN (3)** | Check not yet implemented |

## Usage Examples

### Basic Check
```shell
health_checks {dash_name} [CLUSTER] app
```

### With Telemetry
```shell
health_checks {dash_name} \\
  --sink otel \\
  --sink-opts "log_resource_attributes={\'attr_1\': \'value1\'}" \\
  [CLUSTER] \\
  app
```
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def validate_name(name: str) -> str:
    """Validate check_name and return it if valid, else raise ValueError."""
    if not re.match(r"^check_[a-z][a-z0-9_]*$", name):
        raise ValueError(
            f"'{name}' is not a valid check name.\n"
            "Name must be lowercase letters, digits, and underscores only and match: "
            "^check_[a-z][a-z0-9_]*$\n"
            "Example: check_ntp_sync"
        )
    return name


def to_pascal_case(snake: str) -> str:
    """Convert snake_case to PascalCase."""
    return "".join(word.capitalize() for word in snake.split("_"))


def _render(template: str, **kwargs: str) -> str:
    """Simple {key} substitution without touching unrelated braces."""
    result = template
    for key, value in kwargs.items():
        result = result.replace("{" + key + "}", value)
    return result


# ---------------------------------------------------------------------------
# File-creation helpers
# ---------------------------------------------------------------------------


def create_check_file(check_name: str, group: bool, dry_run: bool) -> None:
    name = check_name[_PREFIX_LEN:]
    upper_name = name.upper()
    pascal_name = to_pascal_case(name)

    dest = PROJECT_ROOT / "gcm" / "health_checks" / "checks" / f"{check_name}.py"

    if dest.exists():
        print(f"Skipping check file: {dest} already exists")
        return

    template = CHECK_FILE_GROUP if group else CHECK_FILE_SIMPLE
    content = _render(
        template,
        check_name=check_name,
        name=name,
        UPPER_NAME=upper_name,
        PascalName=pascal_name,
    )

    if dry_run:
        print(f"[dry-run] Would create: {dest}")
        return

    dest.write_text(content)
    print(f"Created: {dest}")


def create_test_file(check_name: str, group: bool, dry_run: bool) -> None:
    pascal_name = to_pascal_case(check_name[_PREFIX_LEN:])

    dest = (
        PROJECT_ROOT / "gcm" / "tests" / "health_checks_tests" / f"test_{check_name}.py"
    )

    if dest.exists():
        print(f"Skipping test file: {dest} already exists")
        return

    template = TEST_FILE_GROUP if group else TEST_FILE
    content = _render(
        template,
        check_name=check_name,
        PascalName=pascal_name,
    )

    if dry_run:
        print(f"[dry-run] Would create: {dest}")
        return

    dest.write_text(content)
    print(f"Created: {dest}")


def create_doc_file(check_name: str, group: bool, dry_run: bool) -> None:
    dash_name = check_name.replace("_", "-")
    docs_base = (
        PROJECT_ROOT / "website" / "docs" / "GCM_Health_Checks" / "health_checks"
    )

    if group:
        dest_dir = docs_base / dash_name
        readme = dest_dir / "README.md"
        subcommand_doc = dest_dir / "example-subcommand.md"

        if dest_dir.exists():
            print(f"Skipping doc directory: {dest_dir} already exists")
            return

        if dry_run:
            print(f"[dry-run] Would create: {readme}")
            print(f"[dry-run] Would create: {subcommand_doc}")
            return

        dest_dir.mkdir(parents=True, exist_ok=True)
        readme.write_text(_render(DOC_FILE_GROUP, dash_name=dash_name))
        print(f"Created: {readme}")
        subcommand_doc.write_text(
            _render(DOC_FILE_GROUP_SUBCOMMAND, dash_name=dash_name)
        )
        print(f"Created: {subcommand_doc}")
    else:
        dest = docs_base / f"{dash_name}.md"

        if dest.exists():
            print(f"Skipping doc file: {dest} already exists")
            return

        if dry_run:
            print(f"[dry-run] Would create: {dest}")
            return

        dest.write_text(_render(DOC_FILE, dash_name=dash_name))
        print(f"Created: {dest}")


# ---------------------------------------------------------------------------
# File-modification helpers
# ---------------------------------------------------------------------------


def update_init(check_name: str, dry_run: bool) -> None:
    """Add import (alphabetical) and __all__ entry to checks/__init__.py."""
    init_path = PROJECT_ROOT / "gcm" / "health_checks" / "checks" / "__init__.py"
    content = init_path.read_text()

    import_line = f"from gcm.health_checks.checks.{check_name} import {check_name}\n"
    all_entry = f'    "{check_name}",\n'

    # --- import block ---
    if import_line.strip() in content:
        print("Skipping __init__.py import: already exists")
    else:
        # Find all existing check_ import lines and insert in alphabetical order.
        import_pattern = re.compile(
            r"^from gcm\.health_checks\.checks\.check_\S+ import \S+$",
            re.MULTILINE,
        )
        existing = list(import_pattern.finditer(content))
        if existing:
            # Find the correct insertion point.
            inserted = False
            for match in existing:
                if import_line.strip() < match.group().strip():
                    # Insert before this match.
                    pos = match.start()
                    content = content[:pos] + import_line + content[pos:]
                    inserted = True
                    break
            if not inserted:
                # Insert after the last existing import.
                last = existing[-1]
                pos = last.end() + 1  # after the newline
                content = content[:pos] + import_line + content[pos:]
        else:
            # No existing check_ imports; prepend before __all__.
            content = import_line + content

        if dry_run:
            print(f"[dry-run] Would add import to {init_path}")
        else:
            init_path.write_text(content)
            print(f"Updated imports in {init_path}")

    # Re-read on-disk content so __all__ check is consistent regardless
    # of whether the import block was written or skipped due to dry-run.
    content = init_path.read_text()

    # --- __all__ entry ---
    if f'"{check_name}"' in content:
        print("Skipping __init__.py __all__: already exists")
    else:
        # Find the __all__ block and its closing ] specifically.
        all_start = content.find("__all__ = [")
        if all_start == -1:
            print(
                f"Warning: could not find __all__ in {init_path}. "
                "Please add the __all__ entry manually.",
                file=sys.stderr,
            )
            return
        close_bracket = content.find("]", all_start)
        if close_bracket == -1:
            print(
                f"Warning: could not find closing ] for __all__ in {init_path}. "
                "Please add the __all__ entry manually.",
                file=sys.stderr,
            )
            return
        new_content = content[:close_bracket] + all_entry + content[close_bracket:]
        if dry_run:
            print(f"[dry-run] Would add __all__ entry to {init_path}")
        else:
            init_path.write_text(new_content)
            print(f"Updated __all__ in {init_path}")


def update_cli(check_name: str, dry_run: bool) -> None:
    """Add entry to list_of_checks in health_checks.py."""
    cli_path = PROJECT_ROOT / "gcm" / "health_checks" / "cli" / "health_checks.py"
    content = cli_path.read_text()

    entry = f"    checks.{check_name},\n"

    if f"checks.{check_name}" in content:
        print(f"Skipping health_checks.py: checks.{check_name} already exists")
        return

    # Find existing checks.* entries and insert alphabetically.
    entry_pattern = re.compile(r"^    checks\.\w+,$", re.MULTILINE)
    existing = list(entry_pattern.finditer(content))

    if existing:
        inserted = False
        for match in existing:
            if entry.strip() < match.group().strip():
                pos = match.start()
                content = content[:pos] + entry + content[pos:]
                inserted = True
                break
        if not inserted:
            # Append after the last entry.
            last = existing[-1]
            pos = last.end() + 1
            content = content[:pos] + entry + content[pos:]
    else:
        # Fallback: insert before the closing ] of list_of_checks.
        new_content = content.replace("]\n\nfor check", f"{entry}]\n\nfor check", 1)
        if new_content == content:
            print(
                f"Warning: could not find insertion point in {cli_path}. "
                "Please add the entry manually.",
                file=sys.stderr,
            )
            return
        content = new_content

    if dry_run:
        print(f"[dry-run] Would add checks.{check_name} to {cli_path}")
        return

    cli_path.write_text(content)
    print(f"Updated {cli_path}")


def update_enum(check_name: str, dry_run: bool) -> None:
    """Add entry to HealthCheckName enum in alphabetical order."""
    enum_path = (
        PROJECT_ROOT / "gcm" / "schemas" / "health_check" / "health_check_name.py"
    )
    content = enum_path.read_text()

    name = check_name[_PREFIX_LEN:]
    upper_name = name.upper()
    space_name = name.replace("_", " ")
    enum_key = f"CHECK_{upper_name}"
    enum_value = f"check {space_name}"
    new_line = f'    {enum_key} = "{enum_value}"\n'

    if enum_key in content:
        print(f"Skipping health_check_name.py: {enum_key} already exists")
        return

    # Find existing CHECK_ entries and insert alphabetically.
    check_pattern = re.compile(r"^    CHECK_\w+ = \".+\"$", re.MULTILINE)
    existing = list(check_pattern.finditer(content))

    if existing:
        inserted = False
        for match in existing:
            existing_key = match.group().strip().split(" = ")[0]
            if enum_key < existing_key:
                pos = match.start()
                content = content[:pos] + new_line + content[pos:]
                inserted = True
                break
        if not inserted:
            # Append after last CHECK_ entry.
            last = existing[-1]
            pos = last.end() + 1
            content = content[:pos] + new_line + content[pos:]
    else:
        # No existing CHECK_ entries; find class body and insert there.
        class_match = re.search(
            r"^class HealthCheckName\(Enum\):\s*$", content, re.MULTILINE
        )
        if class_match:
            pos = class_match.end() + 1
            content = content[:pos] + new_line + content[pos:]
        else:
            print(
                f"Warning: could not find HealthCheckName class in {enum_path}. "
                "Please add the entry manually.",
                file=sys.stderr,
            )
            return

    if dry_run:
        print(f"[dry-run] Would add {enum_key} to {enum_path}")
        return

    enum_path.write_text(content)
    print(f"Updated {enum_path}")


def update_features(check_name: str, dry_run: bool) -> None:
    """Add disable_check_{name} field to HealthChecksFeatures alphabetically."""
    features_path = (
        PROJECT_ROOT
        / "gcm"
        / "monitoring"
        / "features"
        / "feature_definitions"
        / "health_checks_features.py"
    )
    content = features_path.read_text()

    field_name = f"disable_{check_name}"
    new_line = f"    {field_name}: bool\n"

    if field_name in content:
        print(f"Skipping health_checks_features.py: {field_name} already exists")
        return

    # Find all disable_ field lines and insert alphabetically.
    field_pattern = re.compile(r"^    disable_\w+: bool$", re.MULTILINE)
    existing = list(field_pattern.finditer(content))

    if existing:
        inserted = False
        for match in existing:
            existing_field = match.group().strip().split(":")[0]
            if field_name < existing_field:
                pos = match.start()
                content = content[:pos] + new_line + content[pos:]
                inserted = True
                break
        if not inserted:
            # Append after the last disable_ field.
            last = existing[-1]
            pos = last.end() + 1
            content = content[:pos] + new_line + content[pos:]
    else:
        # No existing disable_ fields; find class body and insert there.
        class_match = re.search(
            r"^class HealthChecksFeatures:\s*$", content, re.MULTILINE
        )
        if class_match:
            pos = class_match.end() + 1
            content = content[:pos] + new_line + content[pos:]
        else:
            print(
                f"Warning: could not find HealthChecksFeatures class in "
                f"{features_path}. Please add the entry manually.",
                file=sys.stderr,
            )
            return

    if dry_run:
        print(f"[dry-run] Would add {field_name} to {features_path}")
        return

    features_path.write_text(content)
    print(f"Updated {features_path}")


# ---------------------------------------------------------------------------
# Post-scaffold automation
# ---------------------------------------------------------------------------


def run_post_scaffold(check_name: str) -> None:
    """Run feature generation and code formatting after scaffolding."""
    gen_script = PROJECT_ROOT / "bin" / "generate_features.py"
    if gen_script.exists():
        print("Running feature generation...")
        result = subprocess.run(
            [sys.executable, str(gen_script)],
            cwd=str(PROJECT_ROOT),
        )
        if result.returncode != 0:
            print(
                f"Warning: generate_features.py exited with code {result.returncode}",
                file=sys.stderr,
            )
    else:
        print(f"Skipping feature generation: {gen_script} not found")

    # Only format the files that were created or modified by the scaffold.
    files_to_format = [
        PROJECT_ROOT / "gcm" / "health_checks" / "checks" / f"{check_name}.py",
        PROJECT_ROOT
        / "gcm"
        / "tests"
        / "health_checks_tests"
        / f"test_{check_name}.py",
        PROJECT_ROOT / "gcm" / "health_checks" / "checks" / "__init__.py",
        PROJECT_ROOT / "gcm" / "health_checks" / "cli" / "health_checks.py",
        PROJECT_ROOT / "gcm" / "schemas" / "health_check" / "health_check_name.py",
        PROJECT_ROOT
        / "gcm"
        / "monitoring"
        / "features"
        / "feature_definitions"
        / "health_checks_features.py",
    ]
    targets = [str(f) for f in files_to_format if f.exists()]

    if targets:
        print("Running ufmt format on scaffolded files...")
        result = subprocess.run(
            [sys.executable, "-m", "ufmt", "format", *targets],
            cwd=str(PROJECT_ROOT),
        )
        if result.returncode != 0:
            print(
                f"Warning: ufmt format exited with code {result.returncode}",
                file=sys.stderr,
            )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scaffold a new GCM health check.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python bin/create_new_health_check.py check_ntp_sync\n"
            "  python bin/create_new_health_check.py check_ntp_sync --group\n"
            "  python bin/create_new_health_check.py check_ntp_sync --dry-run\n"
        ),
    )
    parser.add_argument(
        "check_name",
        help=(
            "Snake_case name of the new health check (e.g. check_ntp_sync). "
            "Must start with 'check_' and contain only lowercase letters, digits, and underscores."
        ),
    )
    parser.add_argument(
        "--group",
        action="store_true",
        default=False,
        help="Generate a @click.group() command instead of a @click.command().",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Print what would be created/modified without writing any files.",
    )

    args = parser.parse_args()
    try:
        check_name = validate_name(args.check_name)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        print(f"[dry-run] Scaffolding health check: {check_name}")

    # 1. Create check file
    create_check_file(check_name, group=args.group, dry_run=args.dry_run)
    # 2. Create test file
    create_test_file(check_name, group=args.group, dry_run=args.dry_run)
    # 3. Create doc file
    create_doc_file(check_name, group=args.group, dry_run=args.dry_run)
    # 4. Update checks/__init__.py
    update_init(check_name, dry_run=args.dry_run)
    # 5. Update health_checks.py CLI
    update_cli(check_name, dry_run=args.dry_run)
    # 6. Update health_check_name.py enum
    update_enum(check_name, dry_run=args.dry_run)
    # 7. Update health_checks_features.py feature flags
    update_features(check_name, dry_run=args.dry_run)
    if args.group:
        # 8. Add subcommand-level enum and feature flag entries
        subcmd_name = f"{check_name}_example_subcommand"
        update_enum(subcmd_name, dry_run=args.dry_run)
        update_features(subcmd_name, dry_run=args.dry_run)

    if not args.dry_run:
        # Regenerate feature flags and format generated code
        run_post_scaffold(check_name)

        print(f"\nDone! Health check '{check_name}' scaffolded successfully.")
        print("Next steps:")
        print(
            f"  1. Implement the check logic in "
            f"gcm/health_checks/checks/{check_name}.py"
        )
        print(
            f"  2. Update the test in "
            f"gcm/tests/health_checks_tests/test_{check_name}.py"
        )
        dash_name = check_name.replace("_", "-")
        if args.group:
            print(
                f"  3. Update the group README in "
                f"website/docs/GCM_Health_Checks/health_checks/{dash_name}/README.md\n"
                f"  4. Update the subcommand doc in "
                f"website/docs/GCM_Health_Checks/health_checks/{dash_name}/example-subcommand.md\n"
                f"  5. Rename 'example_subcommand' to a real subcommand name\n"
                f"  6. Rename 'example-subcommand.md' to match the subcommand\n"
                f"  7. Rename the scaffolded enum/feature entries to match your subcommand\n"
                f"     (in gcm/schemas/health_check/health_check_name.py and\n"
                f"     gcm/monitoring/features/feature_definitions/health_checks_features.py)\n"
                f"  8. Add enum and feature flag entries for any additional subcommands"
            )
        else:
            print(
                f"  3. Update the doc stub in "
                f"website/docs/GCM_Health_Checks/health_checks/{dash_name}.md"
            )


if __name__ == "__main__":
    main()
