# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import json
from dataclasses import asdict
from datetime import datetime
from importlib.resources import as_file, files
from pathlib import Path
from typing import Any, Iterable, List
from unittest.mock import create_autospec

import pytest
from _pytest.logging import LogCaptureFixture
from click.testing import CliRunner
from gcm.exporters.graph_api import GraphAPI
from gcm.exporters.stdout import Stdout

from gcm.monitoring.cli.sacct_publish import CliObject, main as sacct_publish_main
from gcm.monitoring.clock import ClockImpl, PT
from gcm.monitoring.sink.protocol import SinkAdditionalParams
from gcm.schemas.log import Log
from gcm.tests import data

SYSTEM_TZ = datetime.now().astimezone().tzinfo
TEST_TIME = ClockImpl().unixtime()


class GraphAPIStub(GraphAPI):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.write_count = 0

    def _write_log(self, data: Log, additional_params: SinkAdditionalParams) -> None:
        self.write_count += 1
        for message in data.message:
            print(
                json.dumps(
                    {
                        "message": json.dumps(asdict(message)),
                        "write_count": self.write_count,
                    }
                )
            )


class StdoutStub(Stdout):
    def __init__(self) -> None:
        self.write_count = 0

    @property
    def scribe_category(self) -> str:
        return "fair_cluster_sacct_test"

    def write(self, data: Log, additional_params: SinkAdditionalParams) -> None:
        self.write_count += 1
        for message in data.message:
            print(
                json.dumps(
                    {
                        "message": json.dumps(asdict(message)),
                        "write_count": self.write_count,
                    }
                )
            )


@pytest.fixture
def stub_obj() -> CliObject:
    stub = create_autospec(CliObject, instance=True)
    stub.registry = {
        "graph_api": GraphAPIStub,
        "stdout": StdoutStub,
    }
    stub.clock.unixtime = lambda: TEST_TIME
    stub.cluster.return_value = "cluster_name"
    return stub


class TestSacctPublish:
    @staticmethod
    @pytest.mark.parametrize(
        "opts, expected_sink",
        [
            (["-n"], "stdout"),
            (
                [
                    "--sink",
                    "graph_api",
                    "-o",
                    "app_secret=app_id|secret",
                    "-o",
                    "scribe_category=test",
                ],
                "graph_api",
            ),
        ],
    )
    @pytest.mark.parametrize(
        "dataset", ["sample-sacct-output.txt", "sample-sacct-output-large.txt"]
    )
    def test_from_filename(
        dataset: str, stub_obj: CliObject, opts: Iterable[str], expected_sink: str
    ) -> None:
        runner = CliRunner()

        with as_file(files(data).joinpath(dataset)) as path:
            result = runner.invoke(
                sacct_publish_main,
                [*opts, "--log-level=DEBUG", str(path), "--delimiter", "|"],
                catch_exceptions=False,
                obj=stub_obj,
            )

        assert result.exit_code == 0, result.stdout
        assert (
            stub_obj.registry.get(expected_sink)
        ) is not None, f"Sink '{expected_sink}' is not registered"
        lines = result.stdout.strip().split("\n")
        assert len(lines) > 0

    @staticmethod
    @pytest.mark.parametrize(
        "opts, expected_sink",
        [
            (["-n"], "stdout"),
            (
                [
                    "--sink",
                    "graph_api",
                    "-o",
                    "app_secret=app_id|secret",
                    "-o",
                    "scribe_category=test",
                ],
                "graph_api",
            ),
        ],
    )
    @pytest.mark.parametrize(
        "dataset", ["sample-sacct-output.txt", "sample-sacct-output-large.txt"]
    )
    def test_from_stdin(
        dataset: str, stub_obj: CliObject, opts: Iterable[str], expected_sink: str
    ) -> None:
        runner = CliRunner()

        with as_file(files(data).joinpath(dataset)) as path, path.open() as f:
            result = runner.invoke(
                sacct_publish_main,
                [*opts, "--log-level=DEBUG", "--delimiter", "|"],
                catch_exceptions=False,
                obj=stub_obj,
                input=f,
            )

        assert result.exit_code == 0, result.stdout
        assert (
            stub_obj.registry.get(expected_sink)
        ) is not None, f"Sink '{expected_sink}' is not registered"
        lines = result.stdout.strip().split("\n")
        assert len(lines) > 0

    @staticmethod
    @pytest.mark.parametrize(
        "opts",
        [
            [
                "--sink",
                "graph_api",
                "-o",
                "app_secret=app_id|secret",
                "-o",
                "scribe_category=test",
            ],
            ["-n"],
        ],
    )
    def test_with_invalid_lines_bad(stub_obj: CliObject, opts: Iterable[str]) -> None:
        runner = CliRunner()
        with as_file(
            files(data).joinpath("sample-sacct-output-with-invalid-lines.txt")
        ) as path:
            result = runner.invoke(
                sacct_publish_main,
                [*opts, str(path), "--delimiter", "|"],
                catch_exceptions=False,
                obj=stub_obj,
            )

        assert result.exit_code != 0

    @staticmethod
    @pytest.mark.parametrize(
        "opts, expected_sink",
        [
            (["-n"], "stdout"),
            (
                [
                    "--sink",
                    "graph_api",
                    "-o",
                    "app_secret=app_id|secret",
                    "-o",
                    "scribe_category=test",
                ],
                "graph_api",
            ),
        ],
    )
    def test_with_invalid_lines(
        caplog: LogCaptureFixture,
        stub_obj: CliObject,
        opts: Iterable[str],
        expected_sink: str,
    ) -> None:
        runner = CliRunner(mix_stderr=False)

        with as_file(
            files(data).joinpath("sample-sacct-output-with-invalid-lines.txt")
        ) as path:
            result = runner.invoke(
                sacct_publish_main,
                [*opts, "--ignore-line-errors", str(path), "--delimiter", "|"],
                obj=stub_obj,
                catch_exceptions=False,
            )

        assert result.exit_code == 0
        assert len(caplog.records) > 0
        assert any(
            "Skipping invalid input on line" in record.getMessage()
            for record in caplog.records
        )
        assert (
            stub_obj.registry.get(expected_sink)
        ) is not None, f"Sink '{expected_sink}' is not registered"
        lines = result.stdout.strip().split("\n")
        assert len(lines) > 0

    @staticmethod
    @pytest.mark.parametrize(
        "opts, expected_sink",
        [
            (["-n"], "stdout"),
            (
                [
                    "--sink",
                    "graph_api",
                    "-o",
                    "app_secret=app_id|secret",
                    "-o",
                    "scribe_category=test",
                ],
                "graph_api",
            ),
        ],
    )
    @pytest.mark.parametrize("chunk_size", ["500k", "1M"])
    def test_chunking(
        chunk_size: str, stub_obj: CliObject, opts: List[str], expected_sink: str
    ) -> None:
        runner = CliRunner()
        with as_file(files(data).joinpath("sample-sacct-output.txt")) as path:
            result = runner.invoke(
                sacct_publish_main,
                [*opts, "--chunk-size", chunk_size, str(path), "--delimiter", "|"],
                obj=stub_obj,
                catch_exceptions=False,
            )
            with path.open() as f:
                f_iter = iter(f)
                fields = set(next(f_iter).strip().split("|"))
                num_data_rows = sum(1 for _ in f_iter)

        assert result.exit_code == 0
        assert (
            stub_obj.registry.get(expected_sink)
        ) is not None, f"Sink '{expected_sink}' is not registered"

        lines = result.stdout.strip().split("\n")
        assert len(lines) > 0
        assert len(lines) == num_data_rows
        for p in lines:
            payload = json.loads(p)
            message = json.loads(payload["message"])
            assert message["end_ds"] == "2020-11-16"
            assert set(message["sacct"].keys()) == fields
            # could also check the values match, but I think we're reasonably sure at this
            # point that we're writing the correct stuff

    @staticmethod
    @pytest.mark.parametrize(
        "opts, expected_sink",
        [
            (["-n"], "stdout"),
            (
                [
                    "--sink",
                    "graph_api",
                    "-o",
                    "app_secret=app_id|secret",
                    "-o",
                    "scribe_category=test",
                ],
                "graph_api",
            ),
        ],
    )
    @pytest.mark.parametrize("chunk_size", ["0", "0M"])
    def test_no_chunking(
        chunk_size: str, stub_obj: CliObject, opts: List[str], expected_sink: str
    ) -> None:
        runner = CliRunner()
        with as_file(files(data).joinpath("sample-sacct-output.txt")) as path:
            result = runner.invoke(
                sacct_publish_main,
                [*opts, "--chunk-size", chunk_size, str(path), "--delimiter", "|"],
                obj=stub_obj,
                catch_exceptions=False,
            )
            with path.open() as f:
                f_iter = iter(f)
                fields = set(next(f_iter).strip().split("|"))
                num_data_rows = sum(1 for _ in f_iter)

        assert result.exit_code == 0
        assert (
            stub_obj.registry.get(expected_sink)
        ) is not None, f"Sink '{expected_sink}' is not registered"
        lines = result.stdout.strip().split("\n")
        assert len(lines) > 0
        assert len(lines) == num_data_rows
        for p in lines:
            payload = json.loads(p)
            message = json.loads(payload["message"])
            write_count = payload["write_count"]
            # if we're not chunking at all, then we write all the data at once
            assert write_count == 1
            assert message["end_ds"] == "2020-11-16"
            assert set(message["sacct"].keys()) == fields
            # could also check the values match, but I think we're reasonably sure at this
            # point that we're writing the correct stuff

    @staticmethod
    @pytest.mark.parametrize(
        "opts",
        [
            ["-n"],
            [
                "--sink",
                "graph_api",
                "-o",
                "app_secret=app_id|secret",
                "-o",
                "scribe_category=test",
            ],
        ],
    )
    @pytest.mark.parametrize("io_opts", [[], ["--sacct-output-io-errors", "strict"]])
    def test_invalid_utf8_strict(
        opts: List[str], io_opts: List[str], stub_obj: CliObject
    ) -> None:
        runner = CliRunner(mix_stderr=False)

        with as_file(
            files(data).joinpath("sample-sacct-output-invalid-utf8.txt")
        ) as path:
            result = runner.invoke(
                sacct_publish_main,
                [*opts, *io_opts, str(path), "--delimiter", "|"],
                obj=stub_obj,
            )

        assert result.exit_code != 0
        assert "'utf-8' codec can't decode" in result.stderr

    @staticmethod
    @pytest.mark.parametrize(
        "opts, expected_sink",
        [
            (["-n"], "stdout"),
            (
                [
                    "--sink",
                    "graph_api",
                    "-o",
                    "app_secret=app_id|secret",
                    "-o",
                    "scribe_category=test",
                ],
                "graph_api",
            ),
        ],
    )
    @pytest.mark.parametrize("errors", ["ignore", "replace"])
    def test_invalid_utf8_not_strict(
        opts: List[str],
        expected_sink: str,
        errors: str,
        stub_obj: CliObject,
    ) -> None:
        runner = CliRunner()
        expected_num_payloads = 11

        with as_file(
            files(data).joinpath("sample-sacct-output-invalid-utf8.txt")
        ) as path:
            result = runner.invoke(
                sacct_publish_main,
                [
                    *opts,
                    "--sacct-output-io-errors",
                    errors,
                    str(path),
                    "--delimiter",
                    "|",
                ],
                obj=stub_obj,
            )
            with path.open() as f:
                fields = set(f.readline().strip().split("|"))

        assert result.exit_code == 0
        assert (
            stub_obj.registry.get(expected_sink)
        ) is not None, f"Sink '{expected_sink}' is not registered"

        lines = result.stdout.strip().split("\n")
        assert len(lines) > 0
        assert len(lines) == expected_num_payloads
        for p in lines:
            payload = json.loads(p)
            message = json.loads(payload["message"])

            if SYSTEM_TZ == PT:
                assert message["end_ds"] == "2018-06-27"
            else:
                assert message["end_ds"] in ["2018-06-26", "2018-06-27", "2018-06-28"]
            assert set(message["sacct"].keys()) == fields
            # could also check the values match, but I think we're reasonably sure at this
            # point that we're writing the correct stuff

    @staticmethod
    def test_errors_if_sink_not_registered(stub_obj: CliObject, tmp_path: Path) -> None:
        runner = CliRunner(mix_stderr=False)
        out = tmp_path / "out"
        out.touch()
        sink_name = "this_sink_does_not_exist"

        result = runner.invoke(
            sacct_publish_main,
            ["--sink", sink_name, str(out)],
            catch_exceptions=False,
            obj=stub_obj,
        )

        assert result.exit_code != 0
        assert (
            f"Sink '{sink_name}' could not be found. Here are the sinks that are registered:"
            in result.stderr
        )

    @staticmethod
    def test_errors_if_bad_sink_impl_selected(
        stub_obj: CliObject, tmp_path: Path
    ) -> None:
        class NotASink:
            pass

        runner = CliRunner(mix_stderr=False)
        out = tmp_path / "out"
        out.touch()
        sink_name = "not_a_sink"
        stub_obj.registry[sink_name] = NotASink  # type: ignore[index]

        result = runner.invoke(
            sacct_publish_main,
            ["--sink", sink_name, str(out)],
            catch_exceptions=False,
            obj=stub_obj,
        )

        assert result.exit_code != 0
        expected_lines = [
            "Error: Sink 'not_a_sink' defined in",
            "does not appear to implement SinkImpl defined in",
        ]
        it = iter(expected_lines)
        expected_line = next(it)
        for line in result.stderr.split("\n"):
            if line.strip() == expected_line:
                try:
                    expected_line = next(it)
                except StopIteration:
                    break
        else:
            raise AssertionError(
                f"'{expected_line}' does not appear in stderr: {result.stderr}"
            )
