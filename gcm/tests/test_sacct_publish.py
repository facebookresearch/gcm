# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import json
import logging
from dataclasses import asdict
from datetime import datetime
from importlib.resources import as_file, files
from pathlib import Path
from typing import Any, cast, Iterable, List
from unittest.mock import create_autospec, MagicMock, patch

import pytest
from _pytest.logging import LogCaptureFixture
from click.testing import CliRunner
from gcm.exporters.graph_api import GraphAPI
from gcm.exporters.stdout import Stdout
from gcm.monitoring.cli.sacct_publish import (
    CliObject,
    CliObjectImpl,
    KUBERNETES_REQUEST_TIMEOUT_SECONDS,
    main as sacct_publish_main,
    resolve_sc_host,
    resolve_sc_node_host_map,
)
from gcm.monitoring.clock import ClockImpl, PT
from gcm.monitoring.kubernetes.fake_client import KubernetesFakeClient
from gcm.monitoring.sink.protocol import SinkAdditionalParams
from gcm.schemas.kubernetes.pod import KubernetesPodRow
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
    stub.create_kubernetes_client.return_value = KubernetesFakeClient()
    return stub


class TestSacctPublish:
    @staticmethod
    def test_kubernetes_resolution_is_disabled_by_default(stub_obj: CliObject) -> None:
        runner = CliRunner()

        with as_file(files(data).joinpath("sample-sacct-output.txt")) as path:
            result = runner.invoke(
                sacct_publish_main,
                ["-n", str(path), "--delimiter", "|"],
                catch_exceptions=False,
                obj=stub_obj,
            )

        assert result.exit_code == 0, result.stdout
        cast(MagicMock, stub_obj.create_kubernetes_client).assert_not_called()

    @staticmethod
    @patch("gcm.monitoring.kubernetes.api_client.KubernetesApiClient")
    def test_kubernetes_client_has_bounded_timeout(
        kubernetes_api_client: MagicMock,
    ) -> None:
        CliObjectImpl().create_kubernetes_client()

        kubernetes_api_client.assert_called_once_with(
            in_cluster=True,
            request_timeout_seconds=KUBERNETES_REQUEST_TIMEOUT_SECONDS,
        )

    @staticmethod
    @pytest.mark.parametrize(
        "node_list, expected",
        [
            ("g3-130-015", "sf8gg2h4"),
            ("g3-130-[015,021]", None),
            ("None assigned", None),
            ("unknown-node", None),
        ],
    )
    def test_resolve_sc_host(node_list: str, expected: str | None) -> None:
        assert (
            resolve_sc_host(
                {"NodeList": node_list},
                {"g3-130-015": "sf8gg2h4"},
            )
            == expected
        )

    @staticmethod
    @pytest.mark.parametrize(
        "node_list, pod_node_mapping, expected",
        [
            (
                "g3-130-015",
                {"g3-130-015": "sf8gg2h4"},
                {"g3-130-015": "sf8gg2h4"},
            ),
            (
                "g3-130-[015,021]",
                {
                    "g3-130-015": "sf8gg2h4",
                    "g3-130-021": "sf8gg2h9",
                },
                {
                    "g3-130-015": "sf8gg2h4",
                    "g3-130-021": "sf8gg2h9",
                },
            ),
            (
                "g3-130-[015,021],g3-131-001",
                {
                    "g3-130-015": "sf8gg2h4",
                    "g3-130-021": "sf8gg2h9",
                    "g3-131-001": "sf8gg3h1",
                },
                {
                    "g3-130-015": "sf8gg2h4",
                    "g3-130-021": "sf8gg2h9",
                    "g3-131-001": "sf8gg3h1",
                },
            ),
            (
                "g3-130-[015,021]",
                {"g3-130-015": "sf8gg2h4"},
                {"g3-130-015": "sf8gg2h4"},
            ),
            ("None assigned", {"g3-130-015": "sf8gg2h4"}, {}),
            ("unknown-node", {"g3-130-015": "sf8gg2h4"}, {}),
        ],
    )
    def test_resolve_sc_node_host_map(
        node_list: str,
        pod_node_mapping: dict[str, str],
        expected: dict[str, str],
    ) -> None:
        assert (
            resolve_sc_node_host_map(
                {"NodeList": node_list},
                pod_node_mapping,
            )
            == expected
        )

    @staticmethod
    def test_resolves_kubernetes_host(stub_obj: CliObject) -> None:
        runner = CliRunner()
        create_kubernetes_client = cast(MagicMock, stub_obj.create_kubernetes_client)
        create_kubernetes_client.return_value = KubernetesFakeClient(
            pods=[
                KubernetesPodRow(
                    name="node077",
                    namespace="tenant-slurm",
                    node_name="physical-host-1",
                )
            ]
        )

        with as_file(files(data).joinpath("sample-sacct-output.txt")) as path:
            result = runner.invoke(
                sacct_publish_main,
                [
                    "-n",
                    "--resolve-kubernetes-hosts",
                    "--kubernetes-namespace",
                    "tenant-slurm",
                    "--kubernetes-label-selector",
                    "app.kubernetes.io/component=compute",
                    str(path),
                    "--delimiter",
                    "|",
                ],
                catch_exceptions=False,
                obj=stub_obj,
            )

        assert result.exit_code == 0, result.stdout
        payload = json.loads(result.stdout.splitlines()[0])
        message = json.loads(payload["message"])
        assert message["sc_host"] == "physical-host-1"
        assert message["sc_node_hosts"] == json.dumps({"node077": "physical-host-1"})
        create_kubernetes_client.assert_called_once_with()

    @staticmethod
    @pytest.mark.parametrize(
        "error",
        [RuntimeError("API unavailable"), ValueError("Invalid client configuration")],
    )
    def test_kubernetes_host_resolution_failure_is_nonfatal(
        stub_obj: CliObject,
        caplog: LogCaptureFixture,
        error: Exception,
    ) -> None:
        runner = CliRunner()
        create_kubernetes_client = cast(MagicMock, stub_obj.create_kubernetes_client)
        create_kubernetes_client.side_effect = error

        with as_file(files(data).joinpath("sample-sacct-output.txt")) as path:
            result = runner.invoke(
                sacct_publish_main,
                [
                    "-n",
                    "--resolve-kubernetes-hosts",
                    "--kubernetes-namespace",
                    "tenant-slurm",
                    str(path),
                    "--delimiter",
                    "|",
                ],
                catch_exceptions=False,
                obj=stub_obj,
            )

        assert result.exit_code == 0, result.stdout
        payload = json.loads(result.stdout.splitlines()[0])
        message = json.loads(payload["message"])
        assert message["sc_host"] is None
        assert message["sc_node_hosts"] is None
        assert any(record.levelno == logging.WARNING for record in caplog.records)

    @staticmethod
    def test_kubernetes_pod_list_failure_is_nonfatal(
        stub_obj: CliObject,
        caplog: LogCaptureFixture,
    ) -> None:
        runner = CliRunner()
        kubernetes_client = create_autospec(KubernetesFakeClient, instance=True)
        kubernetes_client.list_pods.side_effect = RuntimeError("API unavailable")
        create_kubernetes_client = cast(MagicMock, stub_obj.create_kubernetes_client)
        create_kubernetes_client.return_value = kubernetes_client

        with as_file(files(data).joinpath("sample-sacct-output.txt")) as path:
            result = runner.invoke(
                sacct_publish_main,
                [
                    "-n",
                    "--resolve-kubernetes-hosts",
                    "--kubernetes-namespace",
                    "tenant-slurm",
                    str(path),
                    "--delimiter",
                    "|",
                ],
                catch_exceptions=False,
                obj=stub_obj,
            )

        assert result.exit_code == 0, result.stdout
        payload = json.loads(result.stdout.splitlines()[0])
        message = json.loads(payload["message"])
        assert message["sc_host"] is None
        assert any(record.levelno == logging.WARNING for record in caplog.records)

    @staticmethod
    def test_empty_kubernetes_mapping_is_nonfatal(
        stub_obj: CliObject,
        caplog: LogCaptureFixture,
    ) -> None:
        runner = CliRunner()

        with as_file(files(data).joinpath("sample-sacct-output.txt")) as path:
            result = runner.invoke(
                sacct_publish_main,
                [
                    "-n",
                    "--resolve-kubernetes-hosts",
                    "--kubernetes-namespace",
                    "tenant-slurm",
                    str(path),
                    "--delimiter",
                    "|",
                ],
                catch_exceptions=False,
                obj=stub_obj,
            )

        assert result.exit_code == 0, result.stdout
        payload = json.loads(result.stdout.splitlines()[0])
        message = json.loads(payload["message"])
        assert message["sc_host"] is None
        assert any(record.levelno == logging.WARNING for record in caplog.records)

    @staticmethod
    def test_kubernetes_host_resolution_requires_namespace(
        stub_obj: CliObject,
    ) -> None:
        runner = CliRunner()

        with as_file(files(data).joinpath("sample-sacct-output.txt")) as path:
            result = runner.invoke(
                sacct_publish_main,
                [
                    "-n",
                    "--resolve-kubernetes-hosts",
                    str(path),
                    "--delimiter",
                    "|",
                ],
                obj=stub_obj,
            )

        assert result.exit_code != 0
        assert "--kubernetes-namespace is required" in result.output
        cast(MagicMock, stub_obj.create_kubernetes_client).assert_not_called()

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
