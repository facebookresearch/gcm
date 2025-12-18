# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import itertools
import logging

import os
import re
import socket
import sys
from contextlib import ExitStack
from dataclasses import dataclass
from typing import (
    Any,
    Callable,
    Collection,
    get_args,
    List,
    Literal,
    NoReturn,
    Optional,
    Tuple,
)

import click

import gni_lib
from gcm.health_checks.check_utils.output_context_manager import OutputContext
from gcm.health_checks.check_utils.telem import TelemetryContext
from gcm.health_checks.click import (
    common_arguments,
    telemetry_argument,
    timeout_argument,
)
from gcm.health_checks.subprocess import (
    handle_subprocess_exception,
    shell_command,
    ShellCommandOut,
)
from gcm.health_checks.types import CHECK_TYPE, ExitCode, LOG_LEVEL
from gcm.monitoring.click import heterogeneous_cluster_v1_option

from gcm.monitoring.features.gen.generated_features_healthchecksfeatures import (
    FeatureValueHealthChecksFeatures,
)
from gcm.monitoring.slurm.derived_cluster import get_derived_cluster
from gcm.monitoring.slurm.nodelist_parsers import nodelist
from gcm.monitoring.utils.monitor import init_logger
from gcm.schemas.health_check.health_check_name import HealthCheckName

FnShellCommand = Callable[[str, int], ShellCommandOut]

Flavor = Literal["single", "pairwise", "pairwise-quick"]
NCCL_OPERATION = Literal["all_gather", "all_reduce", "alltoall"]


class PairwiseRequiredOption(click.Option):
    def process_value(self, ctx: click.Context, value: Any) -> Any:
        value = super(PairwiseRequiredOption, self).process_value(ctx, value)

        if value is None and ctx.params["flavor"] != "single":
            msg = "Host list required for pairwise NCCL testing"
            raise click.MissingParameter(ctx=ctx, param=self, message=msg)

        return value


@dataclass
class NCCLTestProcessedOutput:
    message: str
    exitcode: ExitCode
    stdout: Optional[str]
    innererrorcode: Optional[int]


def get_hosts(
    flavor: Flavor,
    hostlist: Optional[str],
    logger: logging.Logger,
    timeout: Optional[int] = None,
) -> List[Tuple[str, ...]]:
    hosts: List[Tuple[str, ...]]

    hostnames = [socket.gethostname()]

    if hostlist is not None:
        hostlist_parser = nodelist()
        parsed, unparsed = hostlist_parser(hostlist)

        if parsed is None:
            logger.info(f'Invalid hostlist: "{unparsed}"')
            raise click.BadParameter(
                message=f'Invalid hostlist: "{unparsed}"',
                param_hint="--hostlist",
            )

        logger.info(f'Parsed hostlist: "{parsed}"')
        hostnames = parsed

    if flavor == "single":
        return [(host,) for host in hostnames]

    if len(hostnames) < 2:
        raise click.BadParameter(
            message="Need to specify at least two hosts in the hostlists when used with any of the pairwise options",
            param_hint="--hostlist",
        )

    if flavor == "pairwise":  # All pairs for --pairwise / --pairwise-exhaustive option
        return list(itertools.combinations(hostnames, 2))

    if flavor == "pairwise-quick":
        hosts = list(zip(hostnames[::2], hostnames[1::2]))
        if len(hostnames) % 2:
            hosts += [(hostnames[-1], hostnames[0])]
        return hosts

    def assert_never(value: NoReturn) -> NoReturn:
        raise TypeError(f"Unhandled value : {value}")

    assert_never(flavor)


def get_avg_bus_bw(output: ShellCommandOut) -> Optional[float]:
    if output.returncode > 0 or "Avg bus bandwidth" not in output.stdout:
        return None

    for line in output.stdout.split("\n"):
        if "Avg bus bandwidth" in line:
            match = re.search(r"[-+]?(\d*\.*\d+)", line)
            avg_bus_bw = float(match.group()) if match else 0.0
            return avg_bus_bw

    return None


def process_nccl_test_ouput(
    output: ShellCommandOut,
    op: NCCL_OPERATION,
    critical_threshold: float,
    warn_threshold: Optional[float],
) -> NCCLTestProcessedOutput:
    processed_output = NCCLTestProcessedOutput(
        f"NCCL Test - {op} - FAILED to run.",
        ExitCode.CRITICAL,
        output.stdout,
        output.returncode,
    )
    if output.returncode > 0:
        processed_output.exitcode = ExitCode.WARN
        return processed_output

    avg_bus_bw = get_avg_bus_bw(output)

    if avg_bus_bw is None:
        processed_output.exitcode = ExitCode.WARN
        return processed_output

    if avg_bus_bw < critical_threshold:
        processed_output.message = (
            f"NCCL Test - {op} - ran successfully. "
            "But bus bandwidth value lower than critical threshold."
        )
        processed_output.exitcode = ExitCode.CRITICAL
        return processed_output

    if warn_threshold is not None and avg_bus_bw < warn_threshold:
        processed_output.message = (
            f"NCCL Test - {op} - ran successfully. "
            "But bus bandwidth value lower than warning threshold."
        )
        processed_output.exitcode = ExitCode.WARN
        return processed_output

    processed_output.message = f"NCCL Test - {op} - ran successfully"
    processed_output.exitcode = ExitCode.OK
    return processed_output


@click.command()
@common_arguments
@timeout_argument
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.option(
    "--single",
    "flavor",
    flag_value="single",
    default=True,
    help="Use for single node  NCCL testing",
    show_default=True,
)
@click.option(
    "--pairwise",
    "--pairwise-exhaustive",
    "flavor",
    flag_value="pairwise",
    help="Use for pairwise NCCL testing for all possible pairs in the hostlist. "
    "If hostlist is node[1-3], then this will run pairwise nccl tests on pairs (node1, node2), "
    "(node1, node3) and (node2, node3).",
    show_default=True,
)
@click.option(
    "--pairwise-quick",
    "flavor",
    flag_value="pairwise-quick",
    help="Use for pairwise NCCL testing such that each node in the hostlist is covered just once. "
    "If hostlist is node[1-3], then this will run pairwise nccl tests on pairs (node1, node2) "
    "and (node1, node3)",
    show_default=True,
)
@click.option(
    "--np",
    "-n",
    "copies",
    type=int,
    help="Run this many copies of the program on the given nodes. "
    "By default this will be set to (num of nodes) * (num of gpus per node)",
)
@click.option(
    "--gpus-per-node",
    type=int,
    default=8,
    show_default=True,
    help="Number of GPUs in each compute node. This will be used to set "
    "the num of copies to run on the given node as (num of nodes) * (num of gpus per node)",
)
@click.option(
    "--nvlink/--no-nvlink",
    default=False,
    help="Run the nccl test with or without nvlink",
    show_default=True,
)
@click.option(
    "--mpi-binpath",
    type=click.Path(dir_okay=False),
    help="Path to the mpirun binary.",
)
@click.option(
    "--hostlist",  # TODO  T141884292: handle comma-separated list of valid hostnames like hostname1,hostname2
    type=str,
    cls=PairwiseRequiredOption,
    help="List of hosts to run the tests. "
    "For --single option, hostlist is optional. "
    "If specified, the test will be run on each of the node in this hostlist, else just on the local host.\n"
    "For --pairwise option, the test will be run on each pair of nodes in this hostlist (required)",
)
@click.option(
    "--mpi-opts",
    type=str,
    help="Options to pass to the underlying mpirun command. "
    "Default includes: -mca coll_hcoll_enable 0 --bind-to numa"
    "See https://www.open-mpi.org/doc/current/man1/mpirun.1.php",
    default="-mca coll_hcoll_enable 0 --bind-to numa",
    show_default=True,
)
@click.option(
    "exports",
    "--export",
    "-x",
    type=str,
    multiple=True,
    help="Export the specified environment variables before executing the program. "
    "Only one environment variable can be specified per -x option.",
    default=[
        "NCCL_IB_PCI_RELAXED_ORDERING=1",
        "CUDA_DEVICE_ORDER=PCI_BUS_ID",
        "NCCL_SOCKET_IFNAME=eth0",
        "NCCL_DEBUG=WARN",
    ],
    show_default=True,
)
@click.option(
    "--nccl-tdir",
    type=click.Path(file_okay=False),
    help="Path to the directory with the nccl-tests binaries.",
    required=True,  # TODO T140440592: include external binaries within gcm package
)
@click.option(
    "--nccl-topts",
    type=str,
    help="NCCL test options. See https://github.com/NVIDIA/nccl-tests#arguments",
    default="-g 1 -b 32M -e 1G -f 2",
    show_default=True,
)
@click.option(
    "--op",
    "-p",
    "operations",
    type=click.Choice(get_args(NCCL_OPERATION)),
    multiple=True,
    help="NCCL collective operations to run. "
    "Multiple operations can be specified, but only one operation per -p option",
    required=True,
)
@click.option(
    "--critical-threshold",
    type=float,
    help="Command exits with a critical exit code if avg bus bw value (in GB/s) is below this threshold",
    required=True,
)
@click.option(
    "--warn-threshold",
    type=float,
    help="Command exits with a warning exit code if avg bus bw value (in GB/s) is below this threshold",
)
@click.pass_obj
def check_nccl(
    obj: Optional[FnShellCommand],
    cluster: str,
    type: CHECK_TYPE,
    log_level: LOG_LEVEL,
    log_folder: str,
    timeout: int,
    sink: str,
    sink_opts: Collection[str],
    verbose_out: bool,
    heterogeneous_cluster_v1: bool,
    flavor: Flavor,
    copies: Optional[int],
    gpus_per_node: int,
    nvlink: bool,
    mpi_binpath: Optional[str],
    hostlist: Optional[str],
    mpi_opts: str,
    exports: Tuple[str],
    nccl_tdir: str,
    nccl_topts: str,
    operations: Tuple[NCCL_OPERATION],
    critical_threshold: float,
    warn_threshold: Optional[float],
) -> None:
    """
    Run NCCL tests to check both the performance and the correctness of NCCL operations.
    """

    node: str = socket.gethostname()

    logger, _ = init_logger(
        logger_name=type,
        log_dir=os.path.join(log_folder, type + "_logs"),
        log_name=node + ".log",
        log_level=getattr(logging, log_level),
    )

    logger.info(f"check_nccl: cluster: {cluster}, node: {node}, type: {type}")
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

    # TODO T140440592: include external binaries within this package
    # Currently, we assume that the user either has mpirun installed or
    # they should pass in the path to the binary
    mpirun_cmd = ["mpirun" if not mpi_binpath else mpi_binpath]

    hosts: List[Tuple[str, ...]] = get_hosts(flavor, hostlist, logger, timeout)

    cmd_args: List[str] = [
        "--np",
        str(
            gpus_per_node * (1 if flavor == "single" else 2)
            if copies is None
            else copies
        ),
    ]

    mpi_opts = mpi_opts.strip()
    if mpi_opts:
        cmd_args += [mpi_opts]

    if exports:
        for export in exports:
            cmd_args += ["-x", export]

    if not nvlink:
        cmd_args += ["-x", "NCCL_P2P_DISABLE=1"]
        cmd_args += ["-x", "NCCL_SHM_DISABLE=1"]

    runner = obj
    if runner is None:
        runner = shell_command

    outputs: List[NCCLTestProcessedOutput] = []
    exit_code = ExitCode.UNKNOWN
    msg = ""
    with ExitStack() as s:
        s.enter_context(
            TelemetryContext(
                sink=sink,
                sink_opts=sink_opts,
                logger=logger,
                cluster=cluster,
                derived_cluster=derived_cluster,
                type=type,
                name=HealthCheckName.NCCL_TESTS.value,
                node=node,
                get_exit_code_msg=lambda: (exit_code, msg),
                gpu_node_id=gpu_node_id,
            )
        )
        s.enter_context(
            OutputContext(
                type, HealthCheckName.NCCL_TESTS, lambda: (exit_code, msg), verbose_out
            )
        )
        ff = FeatureValueHealthChecksFeatures()
        if ff.get_healthchecksfeatures_disable_nccl_tests():
            exit_code = ExitCode.OK
            msg = f"{HealthCheckName.NCCL_TESTS.value} is disabled by killswitch."
            logger.info(msg)
            sys.exit(exit_code.value)
        for host in hosts:
            for op in operations:
                op_bin = nccl_tdir.rstrip("/") + "/" + op + "_perf"
                host_arg = [
                    "--host",
                    ",".join([f"{hostname}:{gpus_per_node}" for hostname in host]),
                ]
                cmd = mpirun_cmd + host_arg + cmd_args + [op_bin, nccl_topts]
                cmd_str = " ".join(cmd)

                logger.info(f"Running command '{cmd_str}'")
                try:
                    output: ShellCommandOut = runner(cmd_str, timeout)
                except Exception as e:
                    output = handle_subprocess_exception(e)

                processed_output: NCCLTestProcessedOutput = process_nccl_test_ouput(
                    output, op, critical_threshold, warn_threshold
                )
                msg = f"Exit Code {processed_output.exitcode.value}: {processed_output.message}"
                logger.info(msg)
                logger.info(f"Output:\n{processed_output.stdout}")
                print(processed_output.stdout)

                outputs += [processed_output]

        if any(output.exitcode == ExitCode.CRITICAL for output in outputs):
            exit_code = ExitCode.CRITICAL
        elif any(output.exitcode == ExitCode.WARN for output in outputs):
            exit_code = ExitCode.WARN
        else:
            exit_code = ExitCode.OK

        sys.exit(exit_code.value)
