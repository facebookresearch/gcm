# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import json
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Iterable, Mapping

from click.testing import CliRunner
from gcm.exporters.stdout import Stdout

from gcm.monitoring.cli.scontrol_config import CliObject, main
from gcm.monitoring.clock import Clock
from gcm.monitoring.sink.protocol import SinkImpl
from gcm.monitoring.sink.utils import Factory
from gcm.monitoring.slurm.client import SlurmClient
from gcm.tests import data
from gcm.tests.fakes import FakeClock

TEST_CLUSTER = "fake_cluster"


class FakeSlurmClient(SlurmClient):
    def scontrol_config(self) -> Iterable[str]:
        with resources.open_text(data, "sample-scontrol-show-config-output.txt") as f:
            for line in f:
                yield line.rstrip("\n")


@dataclass
class FakeCliObject:
    clock: Clock = field(default_factory=FakeClock)
    slurm_client: SlurmClient = field(default_factory=FakeSlurmClient)
    registry: Mapping[str, Factory[SinkImpl]] = field(
        default_factory=lambda: {"stdout": Stdout}
    )

    def cluster(self) -> str:
        return TEST_CLUSTER

    def format_epilog(self) -> str:
        return ""


def test_cli(tmp_path: Path) -> None:
    runner = CliRunner(mix_stderr=False)
    fake_obj: CliObject = FakeCliObject()
    expected_scontrol_config_info = [
        {
            "cluster": TEST_CLUSTER,
            "derived_cluster": TEST_CLUSTER,
            "AccountingStorageBackupHost": "(null)",
            "AccountingStorageEnforce": "associations,limits,qos,safe",
            "AccountingStorageHost": "slurmdb",
            "AccountingStorageExternalHost": "(null)",
            "AccountingStorageParameters": "(null)",
            "AccountingStoragePort": 6819,
            "AccountingStorageTRES": "cpu,mem,energy,node,billing,fs/disk,vmem,pages,gres/gpu,gres/gpumem,gres/gpuutil",
            "AccountingStorageType": "accounting_storage/slurmdbd",
            "AccountingStorageUser": "N/A",
            "AccountingStoreFlags": "(null)",
            "AcctGatherEnergyType": "acct_gather_energy/none",
            "AcctGatherFilesystemType": "acct_gather_filesystem/none",
            "AcctGatherInterconnectType": "acct_gather_interconnect/none",
            "AcctGatherNodeFreq": "0 sec",
            "AcctGatherProfileType": "acct_gather_profile/none",
            "AllowSpecResourcesUsage": "No",
            "AuthAltTypes": "(null)",
            "AuthAltParameters": "(null)",
            "AuthInfo": "(null)",
            "AuthType": "auth/munge",
            "BatchStartTimeout": "300 sec",
            "BcastExclude": "/lib,/usr/lib,/lib64,/usr/lib64",
            "BcastParameters": "(null)",
            "BOOT_TIME": "2023-07-11T14:15:02",
            "BurstBufferType": "(null)",
            "CliFilterPlugins": "(null)",
            "ClusterName": "cluster_name",
            "CommunicationParameters": "(null)",
            "CompleteWait": "0 sec",
            "CoreSpecPlugin": "core_spec/none",
            "CpuFreqDef": "Unknown",
            "CpuFreqGovernors": "OnDemand,Performance,UserSpace",
            "CredType": "cred/munge",
            "DebugFlags": "(null)",
            "DefMemPerNode": "61440",
            "DependencyParameters": "(null)",
            "DisableRootJobs": "No",
            "EioTimeout": "60",
            "EnforcePartLimits": "ANY",
            "Epilog": "/public/slurm/prolog/epilogs.sh",
            "EpilogMsgTime": "2000 usec",
            "EpilogSlurmctld": "(null)",
            "ExtSensorsType": "ext_sensors/none",
            "ExtSensorsFreq": "0 sec",
            "FairShareDampeningFactor": "1",
            "FederationParameters": "(null)",
            "FirstJobId": "1",
            "GetEnvTimeout": "2 sec",
            "GresTypes": "gpu",
            "GpuFreqDef": "(null)",
            "GroupUpdateForce": "1",
            "GroupUpdateTime": "600 sec",
            "HASH_VAL": "Match",
            "HealthCheckInterval": "0 sec",
            "HealthCheckNodeState": "ANY",
            "HealthCheckProgram": "(null)",
            "InactiveLimit": "0 sec",
            "InteractiveStepOptions": "--interactive --preserve-env --pty $SHELL",
            "JobAcctGatherFrequency": "30",
            "JobAcctGatherType": "jobacct_gather/cgroup",
            "JobAcctGatherParams": "NoOverMemoryKill",
            "JobCompHost": "localhost",
            "JobCompLoc": "(null)",
            "JobCompParams": "(null)",
            "JobCompPort": 0,
            "JobCompType": "jobcomp/none",
            "JobCompUser": "root",
            "JobContainerType": "job_container/none",
            "JobCredentialPrivateKey": "(null)",
            "JobCredentialPublicCertificate": "(null)",
            "JobDefaults": "(null)",
            "JobFileAppend": "0",
            "JobRequeue": "1",
            "JobSubmitPlugins": "lua",
            "KillOnBadExit": "1",
            "KillWait": "30 sec",
            "LaunchParameters": "slurm_params",
            "Licenses": "(null)",
            "LogTimeFormat": "iso8601_ms",
            "MailDomain": "(null)",
            "MailProg": "/usr/bin/mail",
            "MaxArraySize": "25000",
            "MaxBatchRequeue": "5",
            "MaxDBDMsgs": "712560",
            "MaxJobCount": "350000",
            "MaxJobId": "67043328",
            "MaxMemPerNode": "UNLIMITED",
            "MaxNodeCount": "3140",
            "MaxStepCount": "40000",
            "MaxTasksPerNode": "512",
            "MCSPlugin": "mcs/none",
            "MCSParameters": "(null)",
            "MessageTimeout": "100 sec",
            "MinJobAge": "50 sec",
            "MpiDefault": "none",
            "MpiParams": "(null)",
            "NEXT_JOB_ID": "12641405",
            "NodeFeaturesPlugins": "(null)",
            "OverTimeLimit": "0 min",
            "PluginDir": "/public/slurm/23.02.2/lib/slurm",
            "PlugStackConfig": "(null)",
            "PowerParameters": "(null)",
            "PowerPlugin": "",
            "PreemptMode": "REQUEUE",
            "PreemptParameters": "(null)",
            "PreemptType": "preempt/partition_prio",
            "PreemptExemptTime": "00:00:00",
            "PrEpParameters": "(null)",
            "PrEpPlugins": "prep/script",
            "PriorityParameters": "(null)",
            "PrioritySiteFactorParameters": "(null)",
            "PrioritySiteFactorPlugin": "(null)",
            "PriorityDecayHalfLife": "7-00:00:00",
            "PriorityCalcPeriod": "00:05:00",
            "PriorityFavorSmall": "No",
            "PriorityFlags": "",
            "PriorityMaxAge": "7-00:00:00",
            "PriorityUsageResetPeriod": "NONE",
            "PriorityType": "priority/multifactor",
            "PriorityWeightAge": 20160,
            "PriorityWeightAssoc": 0,
            "PriorityWeightFairShare": 250000,
            "PriorityWeightJobSize": 1000,
            "PriorityWeightPartition": 1000000,
            "PriorityWeightQOS": 1000000,
            "PriorityWeightTRES": "(null)",
            "PrivateData": "none",
            "ProctrackType": "proctrack/cgroup",
            "Prolog": "/public/slurm/prolog/prologs.sh",
            "PrologEpilogTimeout": "300",
            "PrologSlurmctld": "(null)",
            "PrologFlags": "Alloc,Contain",
            "PropagatePrioProcess": "0",
            "PropagateResourceLimits": "ALL",
            "PropagateResourceLimitsExcept": "(null)",
            "RebootProgram": "/sbin/reboot",
            "ReconfigFlags": "(null)",
            "RequeueExit": "(null)",
            "RequeueExitHold": "(null)",
            "ResumeFailProgram": "(null)",
            "ResumeProgram": "(null)",
            "ResumeRate": "300 nodes/min",
            "ResumeTimeout": "60 sec",
            "ResvEpilog": "(null)",
            "ResvOverRun": "0 min",
            "ResvProlog": "(null)",
            "ReturnToService": "1",
            "RoutePlugin": "route/default",
            "SchedulerParameters": "defer,max_rpc_cnt=64,nohold_on_prolog_fail,bf_continue,bf_max_job_test=1500,bf_window=4320,bf_resolution=180,bf_max_job_user=128,bf_interval=90,bf_ignore_newly_avail_nodes,bf_max_time=600,max_sched_time=1,partition_job_depth=100,bf_yield_interval=1000000,bf_yield_sleep=1000000,sched_min_interval=5000000,8847_node_trace,enable_user_top",
            "SchedulerTimeSlice": "30 sec",
            "SchedulerType": "sched/backfill",
            "ScronParameters": "(null)",
            "SelectType": "select/cons_tres",
            "SelectTypeParameters": "CR_CPU",
            "SlurmUser": "slurm(2000)",
            "SlurmctldAddr": "(null)",
            "SlurmctldDebug": "info",
            "SlurmctldLogFile": "/var/log/slurm/slurmctld.log",
            "SlurmctldPort": "6810-6817",
            "SlurmctldSyslogDebug": "(null)",
            "SlurmctldPrimaryOffProg": "(null)",
            "SlurmctldPrimaryOnProg": "(null)",
            "SlurmctldTimeout": "120 sec",
            "SlurmctldParameters": "preempt_send_user_signal",
            "SlurmdDebug": "error",
            "SlurmdLogFile": "/var/log/slurmd.log",
            "SlurmdParameters": "(null)",
            "SlurmdPidFile": "/var/run/slurmd.pid",
            "SlurmdPort": 6818,
            "SlurmdSpoolDir": "/var/spool/slurm/",
            "SlurmdSyslogDebug": "(null)",
            "SlurmdTimeout": "300 sec",
            "SlurmdUser": "root(0)",
            "SlurmSchedLogFile": "(null)",
            "SlurmSchedLogLevel": "0",
            "SlurmctldPidFile": "/var/run/slurm/slurmctld.pid",
            "SLURM_CONF": "/public/slurm/23.02.2/etc/slurm.conf",
            "SLURM_VERSION": "23.02.2",
            "SrunEpilog": "(null)",
            "SrunPortRange": "0-0",
            "SrunProlog": "(null)",
            "StateSaveLocation": "/slurm/state_save",
            "SuspendExcNodes": "(null)",
            "SuspendExcParts": "(null)",
            "SuspendExcStates": "(null)",
            "SuspendProgram": "(null)",
            "SuspendRate": "60 nodes/min",
            "SuspendTime": "INFINITE",
            "SuspendTimeout": "30 sec",
            "SwitchParameters": "(null)",
            "SwitchType": "switch/none",
            "TaskEpilog": "(null)",
            "TaskPlugin": "task/cgroup,task/affinity",
            "TaskPluginParam": "(null type)",
            "TaskProlog": "(null)",
            "TCPTimeout": "10 sec",
            "TmpFS": "/tmp",
            "TopologyParam": "(null)",
            "TopologyPlugin": "topology/tree",
            "TrackWCKey": "No",
            "TreeWidth": "50",
            "UsePam": "No",
            "UnkillableStepProgram": "(null)",
            "UnkillableStepTimeout": "180 sec",
            "VSizeFactor": "0 percent",
            "WaitTime": "0 sec",
            "X11Parameters": "(null)",
        }
    ]

    result = runner.invoke(
        main,
        [
            "--sink=stdout",
            f"--log-folder={tmp_path}",
            "--once",
        ],
        obj=fake_obj,
        catch_exceptions=True,
    )
    lines = result.stdout.strip().split("\n")
    assert json.loads(lines[0]) == expected_scontrol_config_info
