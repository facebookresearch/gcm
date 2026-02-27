---
sidebar_position: 5
---

# Adding New Health Check

GCM Health Checks are designed to be easily extensible. Each check follows the same patterns, so adding a new one is mostly about copying the right structure and plugging in your logic. This guide walks through each step.

For a deep dive into the boilerplate and annotated code examples, see the [Deep Dive](health_checks_deep_dive.md).

## 1. Create the check file

Create a new file under [`gcm/health_checks/checks/`](https://github.com/facebookresearch/gcm/tree/main/gcm/health_checks/checks). The naming convention is `check_<name>.py`.

```python
# gcm/health_checks/checks/check_example.py
import logging
import socket
import sys
from collections.abc import Collection
from contextlib import ExitStack
from dataclasses import dataclass
from typing import Optional, Protocol

import click
import gni_lib
from gcm.health_checks.check_utils.output_context_manager import OutputContext
from gcm.health_checks.check_utils.telem import TelemetryContext
from gcm.health_checks.click import common_arguments, telemetry_argument, timeout_argument
from gcm.health_checks.subprocess import handle_subprocess_exception, shell_command, ShellCommandOut
from gcm.health_checks.types import CHECK_TYPE, CheckEnv, ExitCode, LOG_LEVEL
from gcm.monitoring.click import heterogeneous_cluster_v1_option
from gcm.monitoring.features.gen.generated_features_healthchecksfeatures import FeatureValueHealthChecksFeatures
from gcm.monitoring.slurm.derived_cluster import get_derived_cluster
from gcm.monitoring.utils.monitor import init_logger
from gcm.schemas.health_check.health_check_name import HealthCheckName
from typeguard import typechecked
```

## 2. Define the Protocol and implementation

Define a `Protocol` class that describes what external commands your check needs, then implement it in a `@dataclass`. This enables dependency injection for testing.

```python
class ExampleCheck(CheckEnv, Protocol):
    """Protocol for the example check."""
    def get_example_data(
        self, timeout_secs: int, logger: logging.Logger
    ) -> ShellCommandOut: ...


@dataclass
class ExampleCheckImpl:
    """Production implementation that runs the actual command."""
    cluster: str
    type: str
    log_level: str
    log_folder: str

    def get_example_data(
        self, timeout_secs: int, logger: logging.Logger
    ) -> ShellCommandOut:
        cmd = "your-command --flags"
        logger.info("Running command '%s'", cmd)
        return shell_command(cmd, timeout_secs)
```

For piped commands (e.g. `dmesg | grep ...`), use `piped_shell_command()` from [`gcm/health_checks/subprocess.py`](https://github.com/facebookresearch/gcm/blob/main/gcm/health_checks/subprocess.py) and return `PipedShellCommandOut` instead.

## 3. Write the processing function

Separate command output parsing from the Click command itself. This keeps the logic unit-testable without invoking the CLI:

```python
def process_example_output(output: str, error_code: int) -> tuple[ExitCode, str]:
    if error_code > 0:
        return (
            ExitCode.WARN,
            f"Command FAILED. error_code: {error_code} output: {output}",
        )
    # Your check logic here
    if "error_condition" in output:
        return ExitCode.CRITICAL, "Error detected: ..."
    return ExitCode.OK, "No errors found."
```

Exit codes follow the [Nagios Plugin API](https://nagios-plugins.org/doc/guidelines.html): `OK` (0), `WARN` (1), `CRITICAL` (2), `UNKNOWN` (3).

## 4. Implement the Click command

Use the standard decorator stack and boilerplate. For a single check, use `@click.command()`. For a group with sub-commands (like `check_syslogs`), use `@click.group()` and `@group.command()`.

```python
@click.command()
@common_arguments          # --cluster, --type, --log-level, --log-folder
@timeout_argument          # --timeout (default: 300s)
@telemetry_argument        # --sink, --sink-opt, --verbose-out
@heterogeneous_cluster_v1_option
@click.pass_obj            # enables object injection for tests
@typechecked
def check_example(
    obj: Optional[ExampleCheck],
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
    """One-line description of what this check does."""
    node: str = socket.gethostname()
    logger, _ = init_logger(
        logger_name=type,
        log_dir=os.path.join(log_folder, type + "_logs"),
        log_name=node + ".log",
        log_level=getattr(logging, log_level),
    )
    try:
        gpu_node_id = gni_lib.get_gpu_node_id()
    except Exception as e:
        gpu_node_id = None
        logger.warning(f"Could not get gpu_node_id, likely not a GPU host: {e}")

    derived_cluster = get_derived_cluster(
        cluster=cluster,
        heterogeneous_cluster_v1=heterogeneous_cluster_v1,
        data={"Node": node},
    )

    if obj is None:
        obj = ExampleCheckImpl(cluster, type, log_level, log_folder)

    exit_code = ExitCode.UNKNOWN
    msg = ""
    with ExitStack() as s:
        s.enter_context(
            TelemetryContext(
                sink=sink, sink_opts=sink_opts, logger=logger,
                cluster=cluster, derived_cluster=derived_cluster,
                type=type, name=HealthCheckName.YOUR_CHECK.value,
                node=node, get_exit_code_msg=lambda: (exit_code, msg),
                gpu_node_id=gpu_node_id,
            )
        )
        s.enter_context(
            OutputContext(type, HealthCheckName.YOUR_CHECK, lambda: (exit_code, msg), verbose_out)
        )

        # Killswitch: allows disabling the check remotely
        ff = FeatureValueHealthChecksFeatures()
        if ff.get_healthchecksfeatures_disable_your_check():
            exit_code = ExitCode.OK
            msg = f"{HealthCheckName.YOUR_CHECK.value} is disabled by killswitch."
            logger.info(msg)
            sys.exit(exit_code.value)

        try:
            result: ShellCommandOut = obj.get_example_data(timeout, logger)
        except Exception as e:
            result = handle_subprocess_exception(e)

        exit_code, msg = process_example_output(result.stdout, result.returncode)
        logger.info(f"exit code {exit_code}: {msg}")

    sys.exit(exit_code.value)
```

## 5. Register the check

Two files need to be updated:

**a)** Add the import in [`gcm/health_checks/checks/__init__.py`](https://github.com/facebookresearch/gcm/blob/main/gcm/health_checks/checks/__init__.py):

```python
from gcm.health_checks.checks.check_example import check_example

__all__ = [
    ...,
    "check_example",
]
```

**b)** Add the command in [`gcm/health_checks/cli/health_checks.py`](https://github.com/facebookresearch/gcm/blob/main/gcm/health_checks/cli/health_checks.py):

```python
list_of_checks: List[click.core.Command] = [
    ...,
    checks.check_example,
]
```

**c)** Add the check name to the [`HealthCheckName`](https://github.com/facebookresearch/gcm/blob/main/gcm/schemas/health_check/health_check_name.py) enum:

```python
class HealthCheckName(Enum):
    ...
    YOUR_CHECK = "your check"
```

## 6. Add the killswitch feature flag

Every check must have a killswitch that allows disabling it remotely without a code deploy. Add a new boolean field to [`gcm/monitoring/features/feature_definitions/health_checks_features.py`](https://github.com/facebookresearch/gcm/blob/main/gcm/monitoring/features/feature_definitions/health_checks_features.py):

```python
class HealthChecksFeatures:
    ...
    disable_your_check: bool
```

After adding the field, regenerate the feature value class and format it:

```shell
python bin/generate_features.py
ufmt format gcm
```

This generates the `FeatureValueHealthChecksFeatures` class with a `get_healthchecksfeatures_disable_your_check()` method, which you use in the Click command (see step 4). The killswitch pattern in the command body should be:

```python
ff = FeatureValueHealthChecksFeatures()
if ff.get_healthchecksfeatures_disable_your_check():
    exit_code = ExitCode.OK
    msg = f"{HealthCheckName.YOUR_CHECK.value} is disabled by killswitch."
    logger.info(msg)
    sys.exit(exit_code.value)
```

Killswitch tests are centralized in [`test_killswitches.py`](https://github.com/facebookresearch/gcm/blob/main/gcm/tests/health_checks_tests/test_killswitches.py) — add your check there as well.

## 7. Write tests

Create `gcm/tests/health_checks_tests/test_check_example.py`. Tests follow a consistent pattern:

**a)** Define a fake implementation that returns pre-built output instead of running real commands:

```python
@dataclass
class FakeExampleCheckImpl:
    example_out: ShellCommandOut

    cluster = "test cluster"
    type = "prolog"
    log_level = "INFO"
    log_folder = "/tmp"

    def get_example_data(
        self, _timeout_secs: int, _logger: logging.Logger
    ) -> ShellCommandOut:
        return self.example_out
```

**b)** Create test data using `FakeShellCommandOut` from `gcm.tests.fakes`:

```python
from gcm.tests.fakes import FakeShellCommandOut

ok_output = FakeShellCommandOut([], 0, "all good")
error_output = FakeShellCommandOut([], 0, "error_condition found")
cmd_failed = FakeShellCommandOut([], 1, "command error")
```

**c)** Use `pytest.fixture` with `indirect` and `@pytest.mark.parametrize` for comprehensive scenario coverage:

```python
@pytest.fixture
def example_tester(request: pytest.FixtureRequest) -> FakeExampleCheckImpl:
    return FakeExampleCheckImpl(request.param)


@pytest.mark.parametrize(
    "example_tester, expected",
    [
        (ok_output, (ExitCode.OK, "No errors found.")),
        (error_output, (ExitCode.CRITICAL, "Error detected")),
        (cmd_failed, (ExitCode.WARN, "FAILED")),
    ],
    indirect=["example_tester"],
)
def test_check_example(
    tmp_path: Path,
    example_tester: FakeExampleCheckImpl,
    expected: tuple[ExitCode, str],
) -> None:
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        check_example,
        f"fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing",
        obj=example_tester,
    )
    assert result.exit_code == expected[0].value
    assert expected[1] in result.output
```

**d)** Also test the processing function directly for fast, focused unit tests:

```python
class TestProcessExampleOutput:
    def test_ok(self) -> None:
        exit_code, msg = process_example_output("all good", 0)
        assert exit_code == ExitCode.OK

    def test_error(self) -> None:
        exit_code, msg = process_example_output("error_condition found", 0)
        assert exit_code == ExitCode.CRITICAL
```

## 8. Add website documentation

Create a documentation page for your check under [`website/docs/GCM_Health_Checks/health_checks/`](https://github.com/facebookresearch/gcm/tree/main/website/docs/GCM_Health_Checks/health_checks). A template is available at [`check-example.md`](health_checks/check-example.md) — copy it and fill in your check's details.

The page should include:
- **Overview**: What the check does and what system aspect it monitors
- **Requirements** (if any): External tools, packages, or hardware needed
- **Command-Line Options**: Table of check-specific options (common options are inherited)
- **Exit Conditions**: Table mapping exit codes to specific conditions
- **Usage Examples**: Basic and telemetry-enabled invocation examples

For checks that are part of a group (sub-commands), create a folder instead of a single file (e.g. `check-syslogs/` with a `README.md` and one page per sub-command).

## 9. Verify

Run the full validation suite before submitting your PR:

```shell
nox -s format    # ufmt/usort formatting
nox -s lint      # flake8 linting
nox -s tests     # pytest unit tests
nox -s typecheck # mypy type checking
```

## How to test a new health check

1. **Unit tests**: Follow step 7 above. Run with `nox -s tests` or directly: `pytest gcm/tests/health_checks_tests/test_check_example.py -v`
2. **Cluster execution**: Deploy the check and run it with `--sink=do_nothing` to verify it works against real system commands. Check the log files for execution details.

## Quick reference

| What | Where |
|------|-------|
| All checks | [`gcm/health_checks/checks/`](https://github.com/facebookresearch/gcm/tree/main/gcm/health_checks/checks) |
| Common decorators | [`gcm/health_checks/click.py`](https://github.com/facebookresearch/gcm/blob/main/gcm/health_checks/click.py) |
| Subprocess utilities | [`gcm/health_checks/subprocess.py`](https://github.com/facebookresearch/gcm/blob/main/gcm/health_checks/subprocess.py) |
| Exit codes & types | [`gcm/health_checks/types.py`](https://github.com/facebookresearch/gcm/blob/main/gcm/health_checks/types.py) |
| Check name enum | [`gcm/schemas/health_check/health_check_name.py`](https://github.com/facebookresearch/gcm/blob/main/gcm/schemas/health_check/health_check_name.py) |
| Feature flags (killswitches) | [`gcm/monitoring/features/feature_definitions/health_checks_features.py`](https://github.com/facebookresearch/gcm/blob/main/gcm/monitoring/features/feature_definitions/health_checks_features.py) |
| CLI entry point | [`gcm/health_checks/cli/health_checks.py`](https://github.com/facebookresearch/gcm/blob/main/gcm/health_checks/cli/health_checks.py) |
| Check documentation | [`website/docs/GCM_Health_Checks/health_checks/`](https://github.com/facebookresearch/gcm/tree/main/website/docs/GCM_Health_Checks/health_checks) |
| Documentation template | [`check-example.md`](health_checks/check-example.md) |
| Test fakes | [`gcm/tests/fakes.py`](https://github.com/facebookresearch/gcm/blob/main/gcm/tests/fakes.py) |
| Output utilities | [`gcm/health_checks/check_utils/output_utils.py`](https://github.com/facebookresearch/gcm/blob/main/gcm/health_checks/check_utils/output_utils.py) |
| Telemetry context | [`gcm/health_checks/check_utils/telem.py`](https://github.com/facebookresearch/gcm/blob/main/gcm/health_checks/check_utils/telem.py) |
| Deep dive | [Health Checks Deep Dive](health_checks_deep_dive.md) |
| Killswitch tests | [`gcm/tests/health_checks_tests/test_killswitches.py`](https://github.com/facebookresearch/gcm/blob/main/gcm/tests/health_checks_tests/test_killswitches.py) |
