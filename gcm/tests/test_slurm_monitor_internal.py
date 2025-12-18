# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from gcm.monitoring.cli.slurm_monitor import main
from gcm.tests.config import Config
from gcm.tests.conftest import report_url


@pytest.mark.skipif(shutil.which("sinfo") is None, reason="Machine does not have sinfo")
@pytest.mark.skipif(
    shutil.which("squeue") is None, reason="Machine does not have squeue"
)
@pytest.mark.skipif(
    shutil.which("sacctmgr") is None, reason="Machine does not have sacctmgr"
)
@pytest.mark.skipif(shutil.which("sdiag") is None, reason="Machine does not have sdiag")
@pytest.mark.parametrize(
    "ods_entity",
    ["test_fair_cluster", 123],
)
@report_url(("ODS", "https://fburl.com/canvas/70jl4w3l"))
def test_slurm_monitor_graph_api_e2e(
    config: Config,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    ods_entity: str | int,
) -> None:
    """Write to a test ODS category using the real Graph API."""
    runner = CliRunner(mix_stderr=False)

    result = runner.invoke(
        main,
        [
            "--sink",
            "graph_api",
            "-o",
            f"app_secret={config.graph_api_access_token}",
            "-o",
            "scribe_category=test",
            "-o",
            f"ods_entity={ods_entity}",
            f"--log-folder={tmp_path}",
            "--once",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.stderr
    assert [r for r in caplog.records if r.levelno >= logging.ERROR] == []


@pytest.mark.skipif(shutil.which("sinfo") is None, reason="Machine does not have sinfo")
@pytest.mark.skipif(
    shutil.which("squeue") is None, reason="Machine does not have squeue"
)
@pytest.mark.skipif(
    shutil.which("sacctmgr") is None, reason="Machine does not have sacctmgr"
)
@pytest.mark.skipif(shutil.which("sdiag") is None, reason="Machine does not have sdiag")
@report_url(("ODS heterogeneous cluster", "https://fburl.com/canvas/sie2wbyb"))
def test_slurm_monitor_derived_cluster_graph_api_e2e(
    config: Config,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Write to a test ODS category using the real Graph API."""
    runner = CliRunner(mix_stderr=False)

    result = runner.invoke(
        main,
        [
            "--sink",
            "graph_api",
            "-o",
            f"app_secret={config.graph_api_access_token}",
            "-o",
            "scribe_category=test",
            "-o",
            "ods_entity=test_fair_cluster",
            f"--log-folder={tmp_path}",
            "--once",
            "--heterogeneous-cluster-v1",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.stderr
    assert [r for r in caplog.records if r.levelno >= logging.ERROR] == []
