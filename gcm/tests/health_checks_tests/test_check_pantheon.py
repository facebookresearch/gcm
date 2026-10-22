# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Test the check_pantheon health-check."""

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest
from click.testing import CliRunner
from gcm.health_checks.checks.check_pantheon import (
    allocated_devices,
    assess_row,
    check_pantheon,
    PantheonRun,
    read_reports,
)
from gcm.health_checks.types import ExitCode
from gcm.tests.fakes import FakeShellCommandOut


def row(
    workload: str,
    gpu: int = 0,
    fields: Optional[Dict[str, Any]] = None,
    **changes: Any,
) -> Dict[str, Any]:
    """A result row as Pantheon writes it for a workload that passed.

    `fields` carries the columns whose names are not Python identifiers.
    """
    result: Dict[str, Any] = {
        "Test Name": workload,
        "GPU ID": gpu,
        "Score": 3141.87,
        "Unit": "GB/s",
        "Status": None,
        "Failure Stage": None,
        "RAS Status": "CLEAN",
        "RAS Error Delta": "None",
        "Limit Reason": "None",
        "Max Temp (C)": 46.0,
    }
    result.update(fields or {})
    result.update(changes)
    return result


@dataclass
class FakePantheonCheckImpl:
    """Supply pregenerated results instead of running Pantheon."""

    results: Dict[str, PantheonRun]
    cluster: str = "test cluster"
    type: str = "prolog"
    log_level: str = "INFO"
    log_folder: str = "/tmp"
    calls: List[Tuple[str, List[int], int, int]] = field(default_factory=list)
    environment: List[Optional[str]] = field(default_factory=list)

    def run_workload(
        self,
        pantheon_bin: Optional[str],
        workload: str,
        devices: List[int],
        duration: int,
        mem_percent: int,
        timeout_secs: int,
        logger: logging.Logger,
    ) -> PantheonRun:
        self.calls.append((workload, devices, duration, mem_percent))
        self.environment.append(os.getenv("CUDA_VISIBLE_DEVICES"))
        return self.results[workload]


def passed(*rows: Dict[str, Any], mock: bool = False) -> PantheonRun:
    return PantheonRun(FakeShellCommandOut([], 0, "done"), list(rows), mock)


@pytest.mark.parametrize(
    "memory_read, march_test, expected, expected_msg",
    [
        (
            passed(row("memory_read")),
            passed(row("march_test", Unit="march-ops/s")),
            ExitCode.OK,
            "GPU 0 memory_read: 3141.87 GB/s",
        ),
        # A memory test that fails means the memory returned wrong data.
        (
            passed(row("memory_read")),
            passed(row("march_test", Unit="ERR", Score=0.0)),
            ExitCode.CRITICAL,
            "GPU 0 march_test: failed, memory errors were detected",
        ),
        (
            passed(row("memory_read", Unit="ERR", Score=0.0)),
            passed(row("march_test")),
            ExitCode.CRITICAL,
            "GPU 0 memory_read: did not complete",
        ),
        (
            passed(
                row(
                    "memory_read",
                    fields={
                        "RAS Status": "ERROR",
                        "RAS Error Delta": "ecc.uncorrected +2",
                    },
                )
            ),
            passed(row("march_test")),
            ExitCode.CRITICAL,
            "uncorrectable errors (ecc.uncorrected +2)",
        ),
        (
            passed(
                row(
                    "memory_read",
                    fields={"Limit Reason": "Thermal", "Max Temp (C)": 95.0},
                )
            ),
            passed(row("march_test")),
            ExitCode.WARN,
            "thermally throttled at 95.0 C",
        ),
        (
            passed(row("memory_read", fields={"Max Temp (C)": 91.0})),
            passed(row("march_test")),
            ExitCode.WARN,
            "reached 91.0 C",
        ),
        (
            passed(
                row(
                    "memory_read",
                    fields={
                        "RAS Status": "WARNING",
                        "RAS Error Delta": "vendor_ras.pcie.bad_tlp +1972",
                    },
                )
            ),
            passed(row("march_test")),
            ExitCode.WARN,
            "correctable errors (vendor_ras.pcie.bad_tlp +1972)",
        ),
        # The link changing power state is not held against the card.
        (
            passed(
                row(
                    "memory_read",
                    fields={
                        "RAS Status": "WARNING",
                        "RAS Error Delta": "vendor_ras.pcie.l0_to_recovery +1",
                    },
                )
            ),
            passed(row("march_test")),
            ExitCode.OK,
            "GPU 0 memory_read: 3141.87 GB/s",
        ),
        # The worst GPU decides the result.
        (
            passed(row("memory_read", gpu=0), row("memory_read", gpu=1)),
            passed(row("march_test", gpu=0), row("march_test", gpu=1, Unit="ERR")),
            ExitCode.CRITICAL,
            "GPU 1 march_test: failed",
        ),
        # No report means nothing is known about the GPU.
        (
            PantheonRun(
                FakeShellCommandOut([], 127, "pantheon: command not found"), [], False
            ),
            PantheonRun(
                FakeShellCommandOut([], 127, "pantheon: command not found"), [], False
            ),
            ExitCode.UNKNOWN,
            "pantheon wrote no report (exit code 127). pantheon: command not found",
        ),
        # A pass on the CPU backend says nothing about the hardware.
        (
            passed(row("memory_read"), mock=True),
            passed(row("march_test"), mock=True),
            ExitCode.UNKNOWN,
            "no hardware was tested",
        ),
        # A failure that was measured outranks a workload that was not.
        (
            PantheonRun(FakeShellCommandOut([], 1, "no report"), [], False),
            passed(row("march_test", Unit="ERR")),
            ExitCode.CRITICAL,
            "GPU 0 march_test: failed",
        ),
    ],
)
def test_check_pantheon(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    memory_read: PantheonRun,
    march_test: PantheonRun,
    expected: ExitCode,
    expected_msg: str,
) -> None:
    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    fake_impl = FakePantheonCheckImpl(
        {"memory_read": memory_read, "march_test": march_test}
    )
    result = runner.invoke(
        check_pantheon,
        f"fair_cluster nagios --log-folder={tmp_path} --sink=do_nothing -gpu 0 -gpu 1",
        obj=fake_impl,
    )

    assert result.exit_code == expected.value
    assert expected_msg in caplog.text
    assert [call[0] for call in fake_impl.calls] == ["memory_read", "march_test"]
    assert all(call[1] == [0, 1] for call in fake_impl.calls)


def test_workloads_and_limits_are_passed_to_pantheon(tmp_path: Path) -> None:
    fake_impl = FakePantheonCheckImpl(
        {"galpat": passed(row("galpat", Unit="galpat-ops/s"))}
    )
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        check_pantheon,
        f"fair_cluster nagios --log-folder={tmp_path} --sink=do_nothing -w galpat --duration=45 --mem-percent=80",
        obj=fake_impl,
    )

    assert result.exit_code == ExitCode.OK.value
    # No device was named and this is not a prolog, so every GPU is tested.
    assert fake_impl.calls == [("galpat", [], 45, 80)]


@pytest.mark.parametrize(
    "variable, value, expected_devices",
    [
        ("SLURM_JOB_GPUS", "2,3", [2, 3]),
        ("CUDA_VISIBLE_DEVICES", "1", [1]),
    ],
)
def test_prolog_tests_the_gpus_of_the_job(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    variable: str,
    value: str,
    expected_devices: List[int],
) -> None:
    monkeypatch.delenv("SLURM_JOB_GPUS", raising=False)
    monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)
    monkeypatch.setenv(variable, value)
    fake_impl = FakePantheonCheckImpl(
        {
            "memory_read": passed(row("memory_read")),
            "march_test": passed(row("march_test")),
        }
    )
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        check_pantheon,
        f"fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing",
        obj=fake_impl,
    )

    assert result.exit_code == ExitCode.OK.value
    assert all(call[1] == expected_devices for call in fake_impl.calls)
    # The workloads name GPUs as the node numbers them, so the variable that
    # renumbers them is unset while they run, and restored afterwards.
    assert fake_impl.environment == [None, None]
    assert os.getenv(variable) == value


def test_prolog_of_a_job_without_gpus_tests_nothing(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Testing every GPU here would disturb the other jobs of the node.
    monkeypatch.delenv("SLURM_JOB_GPUS", raising=False)
    monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)
    fake_impl = FakePantheonCheckImpl({})
    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)
    result = runner.invoke(
        check_pantheon,
        f"fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing",
        obj=fake_impl,
    )

    assert result.exit_code == ExitCode.OK.value
    assert fake_impl.calls == []
    assert "No GPU is allocated to this job" in caplog.text


def test_gpus_named_by_uuid_are_not_guessed_at(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SLURM_JOB_GPUS", raising=False)
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "GPU-58e9026f-e228-b9ef")
    devices, reason = allocated_devices([], "epilog")
    assert devices is None
    assert "--gpu-devices" in reason


def test_a_workload_that_cannot_start_is_a_warning(
    caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    @dataclass
    class RaisingImpl(FakePantheonCheckImpl):
        def run_workload(self, *args: Any, **kwargs: Any) -> PantheonRun:
            raise TimeoutError("timed out")

    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)
    result = runner.invoke(
        check_pantheon,
        f"fair_cluster nagios --log-folder={tmp_path} --sink=do_nothing -w memory_read",
        obj=RaisingImpl({}),
    )

    assert result.exit_code == ExitCode.WARN.value
    assert "memory_read: could not run" in caplog.text


def test_reports_are_read_once_per_gpu(tmp_path: Path) -> None:
    gpus = [{"id": 0, "type": "NVIDIA"}, {"id": 1, "type": "NVIDIA"}]
    rows = [row("memory_read", gpu=1), row("memory_read", gpu=0)]
    # Pantheon writes the session report and one more per completed workload.
    (tmp_path / "pantheon_report_1.json").write_text(
        json.dumps({"gpu_static_info": gpus, "test_results": rows})
    )
    (tmp_path / "pantheon_report_1_0001_memory_read_gpu0.json").write_text(
        json.dumps({"gpu_static_info": gpus, "test_results": [rows[1]]})
    )
    (tmp_path / "other_workload.json").write_text(
        json.dumps({"gpu_static_info": gpus, "test_results": [row("march_test")]})
    )
    (tmp_path / "broken.json").write_text("{not json")

    found, mock = read_reports(tmp_path, "memory_read")
    assert [r["GPU ID"] for r in found] == [0, 1]
    assert mock is False


def test_the_cpu_backend_is_recognised(tmp_path: Path) -> None:
    (tmp_path / "pantheon_report_1.json").write_text(
        json.dumps(
            {
                "gpu_static_info": [{"id": 0, "type": "MOCK"}],
                "test_results": [row("memory_read")],
            }
        )
    )
    found, mock = read_reports(tmp_path, "memory_read")
    assert len(found) == 1 and mock is True


def test_a_missing_report_directory_has_no_rows(tmp_path: Path) -> None:
    assert read_reports(tmp_path / "database", "memory_read") == ([], False)


def test_a_workload_that_did_not_start_is_critical() -> None:
    exit_code, message = assess_row(
        row("tensor_virus", fields={"Failure Stage": "launch", "Unit": "ERR"})
    )
    assert exit_code == ExitCode.CRITICAL
    assert message == "GPU 0 tensor_virus: did not complete"
