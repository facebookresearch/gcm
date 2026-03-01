# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
from unittest.mock import create_autospec, MagicMock

import pytest
import requests
from gcm.monitoring.slurm.rest_client import SlurmRestClient
from gcm.schemas.slurm.sdiag import Sdiag
from gcm.schemas.slurm.squeue import JobData
from gcm.schemas.slurm.sshare import SshareRow


class TestSlurmRestClient:
    def _make_client(
        self,
        session: requests.Session,
        token: str | None = None,
    ) -> SlurmRestClient:
        return SlurmRestClient(
            base_url="http://slurm.example.com",
            token=token,
            session=session,
        )

    def _mock_response(self, json_data: dict, status_code: int = 200) -> MagicMock:
        response = MagicMock()
        response.status_code = status_code
        response.json.return_value = json_data
        return response

    def test_sinfo_returns_pipe_delimited_lines(self) -> None:
        session = create_autospec(requests.Session, instance=True)
        session.get.return_value = self._mock_response(
            {
                "nodes": [
                    {
                        "name": "node01",
                        "state": "idle",
                        "cpus": 64,
                        "memory": 256000,
                    },
                    {
                        "name": "node02",
                        "state": "allocated",
                        "cpus": 128,
                        "memory": 512000,
                    },
                ]
            }
        )

        client = self._make_client(session)
        lines = list(client.sinfo())

        assert len(lines) == 3
        assert lines[0] == "name|state|cpus|memory"
        assert lines[1] == "node01|idle|64|256000"
        assert lines[2] == "node02|allocated|128|512000"

    def test_sinfo_empty_returns_empty(self) -> None:
        session = create_autospec(requests.Session, instance=True)
        session.get.return_value = self._mock_response({"nodes": []})

        client = self._make_client(session)
        lines = list(client.sinfo())

        assert lines == []

    def _sdiag_stats(self) -> dict:
        return {
            "statistics": {
                "server_thread_count": 5,
                "agent_queue_size": 0,
                "agent_count": 2,
                "agent_thread_count": 4,
                "dbd_agent_queue_size": 1,
                "schedule_cycle_max": 100,
                "schedule_cycle_mean": 50,
                "schedule_cycle_sum": 500,
                "schedule_cycle_total": 10,
                "schedule_cycle_per_minute": 6,
                "schedule_queue_length": 20,
                "jobs_submitted": 1000,
                "jobs_started": 900,
                "jobs_completed": 800,
                "jobs_canceled": 50,
                "jobs_failed": 30,
                "jobs_pending": 100,
                "jobs_running": 70,
                "bf_backfilled_jobs": 200,
                "bf_cycle_mean": 10,
                "bf_cycle_sum": 100,
                "bf_cycle_max": 50,
                "bf_queue_len": 15,
            }
        }

    def test_sdiag_structured_returns_sdiag(self) -> None:
        session = create_autospec(requests.Session, instance=True)
        session.get.return_value = self._mock_response(self._sdiag_stats())

        client = self._make_client(session)
        result = client.sdiag_structured()

        assert isinstance(result, Sdiag)
        assert result.server_thread_count == 5
        assert result.agent_queue_size == 0
        assert result.agent_count == 2
        assert result.sdiag_jobs_submitted == 1000
        assert result.sdiag_jobs_running == 70
        assert result.bf_backfilled_jobs == 200
        assert result.schedule_cycle_max == 100

    def test_sshare_returns_pipe_delimited_lines(self) -> None:
        session = create_autospec(requests.Session, instance=True)
        session.get.return_value = self._mock_response(
            {
                "shares": {
                    "shares": [
                        {
                            "name": "research",
                            "user": "alice",
                            "shares": {"raw": 100, "normalized": 0.5},
                            "usage": {"raw": 50000, "normalized": 0.3},
                            "fairshare": {"factor": 0.8},
                        },
                        {
                            "name": "engineering",
                            "user": "bob",
                            "shares": {"raw": 200, "normalized": 0.7},
                            "usage": {"raw": 30000, "normalized": 0.2},
                            "fairshare": {"factor": 0.9},
                        },
                    ]
                }
            }
        )

        client = self._make_client(session)
        lines = list(client.sshare())

        assert len(lines) == 3
        assert (
            lines[0] == "Account|User|RawShares|NormShares|RawUsage|NormUsage|FairShare"
        )
        assert lines[1] == "research|alice|100|0.5|50000|0.3|0.8"
        assert lines[2] == "engineering|bob|200|0.7|30000|0.2|0.9"

    def test_sshare_empty_returns_empty(self) -> None:
        session = create_autospec(requests.Session, instance=True)
        session.get.return_value = self._mock_response({"shares": {"shares": []}})

        client = self._make_client(session)
        lines = list(client.sshare())

        assert lines == []

    def test_sacctmgr_qos_returns_pipe_delimited_lines(self) -> None:
        session = create_autospec(requests.Session, instance=True)
        session.get.return_value = self._mock_response(
            {
                "qos": [
                    {"name": "normal", "priority": 10, "max_wall": 86400},
                    {"name": "high", "priority": 100, "max_wall": 172800},
                ]
            }
        )

        client = self._make_client(session)
        lines = list(client.sacctmgr_qos())

        assert len(lines) == 3
        assert lines[0] == "name|priority|max_wall"
        assert lines[1] == "normal|10|86400"
        assert lines[2] == "high|100|172800"

    def test_sacctmgr_user_returns_pipe_delimited_lines(self) -> None:
        session = create_autospec(requests.Session, instance=True)
        session.get.return_value = self._mock_response(
            {
                "users": [
                    {"name": "alice"},
                    {"name": "bob"},
                    {"name": "charlie"},
                ]
            }
        )

        client = self._make_client(session)
        lines = list(client.sacctmgr_user())

        assert len(lines) == 3
        assert lines[0] == "alice"
        assert lines[1] == "bob"
        assert lines[2] == "charlie"

    def test_sprio_not_implemented(self) -> None:
        session = create_autospec(requests.Session, instance=True)
        client = self._make_client(session)

        with pytest.raises(NotImplementedError, match="sprio"):
            client.sprio()

    def test_count_runaway_not_implemented(self) -> None:
        session = create_autospec(requests.Session, instance=True)
        client = self._make_client(session)

        with pytest.raises(NotImplementedError, match="count_runaway_jobs"):
            client.count_runaway_jobs()

    def test_scontrol_config_not_implemented(self) -> None:
        session = create_autospec(requests.Session, instance=True)
        client = self._make_client(session)

        with pytest.raises(NotImplementedError, match="scontrol_config"):
            client.scontrol_config()

    def test_auth_token_header(self) -> None:
        session = create_autospec(requests.Session, instance=True)
        session.headers = {}
        client = self._make_client(session, token="test-jwt-token-123")

        assert session.headers["X-SLURM-USER-TOKEN"] == "test-jwt-token-123"
        assert client.session is session

    def test_request_error_raises_runtime_error(self) -> None:
        session = create_autospec(requests.Session, instance=True)
        session.get.return_value = self._mock_response(
            {"error": "internal server error"}, status_code=500
        )

        client = self._make_client(session)

        with pytest.raises(RuntimeError, match="500"):
            # sinfo is a generator; must iterate to trigger _get()
            list(client.sinfo())

    def test_sinfo_structured_returns_sinfo(self) -> None:
        session = create_autospec(requests.Session, instance=True)
        session.get.return_value = self._mock_response(
            {
                "nodes": [
                    {
                        "name": "gpu-node-01",
                        "alloc_cpus": 32,
                        "cpus": 64,
                        "gres": "gpu:a100:8",
                        "gres_used": "gpu:a100:4",
                        "state": "mixed",
                        "partitions": ["gpu", "default"],
                    },
                ]
            }
        )

        client = self._make_client(session)
        result = client.sinfo_structured()

        assert len(list(result.nodes)) == 1
        node = list(result.nodes)[0]
        assert node.name == "gpu-node-01"
        assert node.alloc_cpus == 32
        assert node.total_cpus == 64
        assert node.gres == "gpu:a100:8"
        assert node.state == "mixed"
        assert node.partition == "gpu"

    def test_scontrol_partition_returns_key_value_lines(self) -> None:
        session = create_autospec(requests.Session, instance=True)
        session.get.return_value = self._mock_response(
            {
                "partitions": [
                    {
                        "name": "gpu",
                        "state": "UP",
                        "total_nodes": 10,
                    },
                ]
            }
        )

        client = self._make_client(session)
        lines = list(client.scontrol_partition())

        assert len(lines) == 1
        assert "name=gpu" in lines[0]
        assert "state=UP" in lines[0]

    def test_sacctmgr_user_info_returns_user_details(self) -> None:
        session = create_autospec(requests.Session, instance=True)
        session.get.return_value = self._mock_response(
            {
                "users": [
                    {
                        "name": "alice",
                        "default": {
                            "account": "research",
                            "qos": "normal",
                        },
                        "associations": [
                            {
                                "account": "research",
                                "qos": ["normal", "high"],
                            },
                        ],
                    }
                ]
            }
        )

        client = self._make_client(session)
        lines = list(client.sacctmgr_user_info("alice"))

        assert len(lines) == 2
        assert lines[0] == "User|DefaultAccount|Account|DefaultQOS|QOS"
        assert lines[1] == "alice|research|research|normal|normal,high"

    def test_sshare_structured_returns_sshare_rows(self) -> None:
        session = create_autospec(requests.Session, instance=True)
        session.get.return_value = self._mock_response(
            {
                "shares": {
                    "shares": [
                        {
                            "name": "research",
                            "user": "alice",
                            "shares": {"raw": 100, "normalized": 0.5},
                            "usage": {"raw": 50000, "normalized": 0.3},
                            "fairshare": {"factor": 0.8},
                        },
                    ]
                }
            }
        )

        client = self._make_client(session)
        rows = list(client.sshare_structured())

        assert len(rows) == 1
        assert isinstance(rows[0], SshareRow)
        assert rows[0].Account == "research"
        assert rows[0].User == "alice"
        assert rows[0].RawShares == "100"
        assert rows[0].FairShare == "0.8"

    def test_squeue_returns_job_data(self) -> None:
        session = create_autospec(requests.Session, instance=True)
        session.get.return_value = self._mock_response(
            {
                "jobs": [
                    {
                        "job_id": 12345,
                        "array_job_id": 12345,
                        "name": "train_model",
                        "time_limit": {"number": 3600, "set": True},
                        "minimum_cpus_per_node": 4,
                        "minimum_memory_per_node": "16000M",
                        "command": "/home/alice/train.sh",
                        "priority": 1000.0,
                        "job_state": "RUNNING",
                        "user_name": "alice",
                        "cpus": 8,
                        "node_count": 1,
                        "time_left": "1:00:00",
                        "time_used": "0:30:00",
                        "nodes": "gpu-node-01",
                        "dependency": "",
                        "excluded_nodes": "",
                        "start_time": "2024-01-15T10:00:00",
                        "submit_time": "2024-01-15T09:50:00",
                        "eligible_time": "2024-01-15T09:55:00",
                        "accrue_time": "2024-01-15T09:55:00",
                        "pending_time": 0,
                        "comment": "",
                        "partition": "gpu",
                        "account": "research",
                        "qos": "normal",
                        "state_reason": "None",
                        "tres_alloc_str": "cpu=8,node=1",
                        "tres_per_node": "",
                        "reservation": "",
                        "requeue": "0",
                        "features": "",
                        "restart_cnt": 0,
                        "scheduled_nodes": "",
                    },
                ]
            }
        )

        client = self._make_client(session)
        test_logger = logging.getLogger("test")
        jobs = list(
            client.squeue(
                derived_cluster_fetcher=lambda row: "test-cluster",
                logger=test_logger,
                attributes={"collection_unixtime": 1700000100, "cluster": "prod"},
            )
        )

        assert len(jobs) == 1
        job = jobs[0]
        assert isinstance(job, JobData)
        assert job.JOBID_RAW == "12345"
        assert job.NAME == "train_model"
        assert job.STATE == "RUNNING"
        assert job.USER == "alice"
        assert job.PARTITION == "gpu"
        assert job.ACCOUNT == "research"
        assert job.QOS == "normal"
        assert job.derived_cluster == "test-cluster"
        assert job.PENDING_RESOURCES == "False"

    def test_squeue_empty_returns_empty(self) -> None:
        session = create_autospec(requests.Session, instance=True)
        session.get.return_value = self._mock_response({"jobs": []})

        client = self._make_client(session)
        test_logger = logging.getLogger("test")
        jobs = list(
            client.squeue(
                derived_cluster_fetcher=lambda row: "test-cluster",
                logger=test_logger,
            )
        )

        assert jobs == []

    def test_base_url_trailing_slash_stripped(self) -> None:
        session = create_autospec(requests.Session, instance=True)
        client = SlurmRestClient(
            base_url="http://slurm.example.com/",
            session=session,
        )
        assert client.base_url == "http://slurm.example.com"
