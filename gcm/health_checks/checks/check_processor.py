# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
import os
import re
import socket
import sys
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Collection, Dict, Iterable, List, Optional, Protocol, Tuple

import click

import gni_lib
from gcm.health_checks.check_utils.output_context_manager import OutputContext
from gcm.health_checks.check_utils.processor_memory_utils import (
    get_mem_attributes,
    MemAttrs,
)
from gcm.health_checks.check_utils.telem import TelemetryContext
from gcm.health_checks.click import (
    common_arguments,
    telemetry_argument,
    timeout_argument,
)
from gcm.health_checks.subprocess import (
    handle_subprocess_exception,
    piped_shell_command,
    PipedShellCommandOut,
    shell_command,
    ShellCommandOut,
)
from gcm.health_checks.types import CHECK_TYPE, CheckEnv, ExitCode, LOG_LEVEL
from gcm.monitoring.click import heterogeneous_cluster_v1_option

from gcm.monitoring.features.gen.generated_features_healthchecksfeatures import (
    FeatureValueHealthChecksFeatures,
)
from gcm.monitoring.slurm.derived_cluster import get_derived_cluster
from gcm.monitoring.utils.monitor import init_logger
from gcm.schemas.health_check.health_check_name import HealthCheckName
from typeguard import typechecked


@click.group()
def check_processor() -> None:
    """processor based checks. i.e. CPU freq, freq governor etc."""


class ProcessorCheck(CheckEnv, Protocol):
    def get_cpu_freq(
        self, timeout_secs: int, logger: logging.Logger
    ) -> ShellCommandOut: ...

    def get_cpufreq_governor(
        self, timeout_secs: int, sys_freq_file: str, logger: logging.Logger
    ) -> PipedShellCommandOut: ...

    def get_mem_info(
        self, timeout_secs: int, logger: logging.Logger
    ) -> PipedShellCommandOut: ...

    def get_buddyinfo_lines(self, buddyinfo_path: Path) -> Iterable[str]: ...

    def get_clocksource(
        self, timeout_secs: int, sys_clocksource_file: str, logger: logging.Logger
    ) -> ShellCommandOut: ...


@dataclass
class ProcessorCheckImpl:
    cluster: str
    type: str
    log_level: str
    log_folder: str

    def get_cpu_freq(
        self, timeout_secs: int, logger: logging.Logger
    ) -> ShellCommandOut:
        """Get the processor's frequency"""
        cmd = "awk '/MHz/{ sum+=int($4); count+=1 };END{ print int(sum/count) };' /proc/cpuinfo"
        logger.info(f"Running command {cmd}")
        return shell_command(cmd, timeout_secs)

    def get_cpufreq_governor(
        self, timeout_secs: int, sys_freq_file: str, logger: logging.Logger
    ) -> PipedShellCommandOut:
        """Get the processor's frequency governor"""
        logger.info(f"Running command `cat {sys_freq_file} | uniq'")
        return piped_shell_command([f"cat {sys_freq_file}", "uniq"], timeout_secs)

    def get_mem_info(
        self, timeout_secs: int, logger: logging.Logger
    ) -> PipedShellCommandOut:
        # type 17 is for memory
        cmd = [
            "sudo dmidecode --type 17",
            "sed -ne 's/^\\tSize: \\([0-9]*\\) GB/\\1/p'",
            "uniq -c",
        ]
        logger.info(f"Running command: {' | '.join(cmd)}")
        return piped_shell_command(cmd, timeout_secs)

    def get_buddyinfo_lines(self, buddyinfo_path: Path) -> Iterable[str]:
        with open(buddyinfo_path) as f:
            return [line.strip() for line in filter(None, f.readlines())]

    def get_clocksource(
        self, timeout_secs: int, sys_clocksource_file: str, logger: logging.Logger
    ) -> ShellCommandOut:
        cmd = f"cat {sys_clocksource_file}"
        logger.info(f"Running command {cmd}")
        return shell_command(cmd, timeout_secs)


def process_cpu_freq(
    output: str, error_code: int, proc_freq: int
) -> Tuple[ExitCode, str]:
    if error_code > 0 or len(output) == 0:
        return (
            ExitCode.WARN,
            f"processor freq command FAILED to execute. error_code: {error_code} output: {output}\n",
        )

    try:
        current_proc_freq = int(output)
    except Exception:
        return ExitCode.WARN, f"Invalid processor freq output: {output}.\n"

    if current_proc_freq < proc_freq:
        return (
            ExitCode.CRITICAL,
            f"current processor freq, {current_proc_freq}, is lower than expected, {proc_freq}.\n",
        )

    return (
        ExitCode.OK,
        f"current processor freq, {current_proc_freq}, is higher or equal than expected, {proc_freq}.\n",
    )


def process_cpufreq_governor(
    output: str, error_code: int, governor: str
) -> Tuple[ExitCode, str]:
    if error_code > 0 or len(output) == 0:
        return (
            ExitCode.WARN,
            f"processor cpufreq governor command FAILED to execute. error_code: {error_code} output: {output}\n",
        )

    text = output.splitlines()
    if len(text) > 1:
        return (
            ExitCode.CRITICAL,
            f"different governors detected among the cpus. output: {text}\n",
        )

    if governor == text[0]:
        return (
            ExitCode.OK,
            f"all cpu governors are {governor}\n",
        )

    return (
        ExitCode.CRITICAL,
        f"different governor detected. expected: {governor}, and found: {text[0]}\n",
    )


@check_processor.command()
@common_arguments
@timeout_argument
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.option(
    "--proc_freq",
    type=click.INT,
    default=1498,
    help="Minimum acceptable CPU frequency",
)
@click.pass_obj
@typechecked
def processor_freq(
    obj: Optional[ProcessorCheck],
    cluster: str,
    type: CHECK_TYPE,
    log_level: LOG_LEVEL,
    log_folder: str,
    timeout: int,
    sink: str,
    sink_opts: Collection[str],
    verbose_out: bool,
    heterogeneous_cluster_v1: bool,
    proc_freq: int,
) -> None:
    """Check if the processor freq is at least as specified"""

    node: str = socket.gethostname()
    logger, _ = init_logger(
        logger_name=type,
        log_dir=os.path.join(log_folder, type + "_logs"),
        log_name=node + ".log",
        log_level=getattr(logging, log_level),
    )
    logger.info(
        f"check-processor processor-freq: cluster: {cluster}, node: {node}, type: {type}."
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
        obj = ProcessorCheckImpl(cluster, type, log_level, log_folder)

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
                name=HealthCheckName.PROC_FREQ.value,
                node=node,
                get_exit_code_msg=lambda: (exit_code, msg),
                gpu_node_id=gpu_node_id,
            )
        )
        s.enter_context(
            OutputContext(
                type, HealthCheckName.PROC_FREQ, lambda: (exit_code, msg), verbose_out
            )
        )
        ff = FeatureValueHealthChecksFeatures()
        if ff.get_healthchecksfeatures_disable_proc_freq():
            exit_code = ExitCode.OK
            msg = f"{HealthCheckName.PROC_FREQ.value} is disabled by killswitch."
            logger.info(msg)
            sys.exit(exit_code.value)
        try:
            cpu_freq_out: ShellCommandOut = obj.get_cpu_freq(timeout, logger)
        except Exception as e:
            cpu_freq_out = handle_subprocess_exception(e)

        exit_code, msg = process_cpu_freq(
            cpu_freq_out.stdout, cpu_freq_out.returncode, proc_freq
        )

        logger.info(f"exit code {exit_code}: {msg}")

        sys.exit(exit_code.value)


@check_processor.command()
@common_arguments
@timeout_argument
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.option(
    "--governor",
    type=click.STRING,
    default="performance",
    help="The required processor frequency governor",
)
@click.option(
    "--sys_freq_file",
    type=click.STRING,
    default="/sys/devices/system/cpu/cpu*/cpufreq/scaling_governor",
    help="File or file glob pattern to read processor governor from",
)
@click.pass_obj
@typechecked
def cpufreq_governor(
    obj: Optional[ProcessorCheck],
    cluster: str,
    type: CHECK_TYPE,
    log_level: LOG_LEVEL,
    log_folder: str,
    timeout: int,
    sink: str,
    sink_opts: Collection[str],
    verbose_out: bool,
    governor: str,
    heterogeneous_cluster_v1: bool,
    sys_freq_file: str,
) -> None:
    """Check that all processors have the specified scaling governor"""

    node: str = socket.gethostname()
    logger, _ = init_logger(
        logger_name=type,
        log_dir=os.path.join(log_folder, type + "_logs"),
        log_name=node + ".log",
        log_level=getattr(logging, log_level),
    )
    logger.info(
        f"check-processor cpufreq-governor: cluster: {cluster}, node: {node}, type: {type}, governor: {governor},  sys_freq_file: {sys_freq_file}."
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
        obj = ProcessorCheckImpl(cluster, type, log_level, log_folder)

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
                name=HealthCheckName.FREQ_GOVERNOR.value,
                node=node,
                get_exit_code_msg=lambda: (exit_code, msg),
                gpu_node_id=gpu_node_id,
            )
        )
        s.enter_context(
            OutputContext(
                type,
                HealthCheckName.FREQ_GOVERNOR,
                lambda: (exit_code, msg),
                verbose_out,
            )
        )
        ff = FeatureValueHealthChecksFeatures()
        if ff.get_healthchecksfeatures_disable_freq_governor():
            exit_code = ExitCode.OK
            msg = f"{HealthCheckName.FREQ_GOVERNOR.value} is disabled by killswitch."
            logger.info(msg)
            sys.exit(exit_code.value)
        try:
            cpufreq_governor_out: PipedShellCommandOut = obj.get_cpufreq_governor(
                timeout, sys_freq_file, logger
            )
        except Exception as e:
            exc_out = handle_subprocess_exception(e)
            cpufreq_governor_out = PipedShellCommandOut(
                [exc_out.returncode], exc_out.stdout
            )

        exit_code, msg = process_cpufreq_governor(
            cpufreq_governor_out.stdout,
            cpufreq_governor_out.returncode[0],
            governor,
        )

        logger.info(f"exit code {exit_code}: {msg}")

        sys.exit(exit_code.value)


class CheckIfRequiredOptionDimm(click.Option):
    def process_value(self, ctx: click.Context, value: Any) -> Any:
        value = super().process_value(ctx, value)
        if (
            value is None
            and "total_size" in ctx.params
            and ctx.params["total_size"] is not None
        ):
            msg = "You have to specify both dimms and total-size"
            raise click.MissingParameter(ctx=ctx, param=self, message=msg)
        return value


class CheckIfRequiredOptionTotalSize(click.Option):
    def process_value(self, ctx: click.Context, value: Any) -> Any:
        value = super().process_value(ctx, value)
        if value is None and "dimms" in ctx.params and ctx.params["dimms"] is not None:
            msg = "You have to specify both dimms and total-size"
            raise click.MissingParameter(ctx=ctx, param=self, message=msg)
        return value


def process_mem_info(
    output: str,
    error_code: int,
    dimms: int,
    total_size: int,
) -> Tuple[ExitCode, str]:
    if error_code > 0 or len(output) == 0:
        return (
            ExitCode.WARN,
            f"dmidecode command FAILED to execute. error_code: {error_code} output: {output}\n",
        )
    proc_total_size = 0
    proc_dimms = 0
    for line in output.strip().split("\n"):
        split_line = line.strip().split()
        try:
            d = int(split_line[0])
            size = int(split_line[1])
            proc_dimms += d
            proc_total_size += d * size
        except ValueError:
            return ExitCode.WARN, f"Invalid output returned: {output}"

    if dimms == proc_dimms and proc_total_size == total_size:
        return (
            ExitCode.OK,
            f"Memory size as expected. DIMMs: {dimms} and Total size: {total_size} GB",
        )
    else:
        return (
            ExitCode.CRITICAL,
            f"Memory size not as expected. Expected DIMMs/Total size GB: {dimms}/{total_size} and found {proc_dimms}/{proc_total_size}.",
        )


@check_processor.command()
@common_arguments
@timeout_argument
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.option(
    "--dimms",
    type=click.INT,
    cls=CheckIfRequiredOptionDimm,
    help="Number of expected DIMMS",
)
@click.option(
    "--total-size",
    type=click.INT,
    cls=CheckIfRequiredOptionTotalSize,
    help="Total memory size in GB. Calculated as DIMMs*Size per DIMM",
)
@click.pass_obj
@typechecked
def check_mem_size(
    obj: Optional[ProcessorCheck],
    cluster: str,
    type: CHECK_TYPE,
    log_level: LOG_LEVEL,
    log_folder: str,
    timeout: int,
    sink: str,
    sink_opts: Collection[str],
    verbose_out: bool,
    heterogeneous_cluster_v1: bool,
    dimms: Optional[int],
    total_size: Optional[int],
) -> None:
    """Check if the memory size, dimms and total size, is as expected"""

    node: str = socket.gethostname()
    logger, _ = init_logger(
        logger_name=type,
        log_dir=os.path.join(log_folder, type + "_logs"),
        log_name=node + ".log",
        log_level=getattr(logging, log_level),
    )

    logger.info(
        f"check-processor check-mem-size: cluster: {cluster}, node: {node}, type: {type}."
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
        obj = ProcessorCheckImpl(cluster, type, log_level, log_folder)

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
                name=HealthCheckName.CHECK_MEM_SIZE.value,
                node=node,
                get_exit_code_msg=lambda: (exit_code, msg),
                gpu_node_id=gpu_node_id,
            )
        )
        s.enter_context(
            OutputContext(
                type,
                HealthCheckName.CHECK_MEM_SIZE,
                lambda: (exit_code, msg),
                verbose_out,
            )
        )
        ff = FeatureValueHealthChecksFeatures()
        if ff.get_healthchecksfeatures_disable_check_mem_size():
            exit_code = ExitCode.OK
            msg = f"{HealthCheckName.CHECK_MEM_SIZE.value} is disabled by killswitch."
            logger.info(msg)
            sys.exit(exit_code.value)

        if dimms is None or total_size is None:
            mem_attributes: MemAttrs = get_mem_attributes(node)
            dimms = mem_attributes["dimms"]
            total_size = mem_attributes["total_size_gb"]
        try:
            mem_out: PipedShellCommandOut = obj.get_mem_info(timeout, logger)
        except Exception as e:
            exc_out = handle_subprocess_exception(e)
            mem_out = PipedShellCommandOut([exc_out.returncode], exc_out.stdout)

        exit_code, msg = process_mem_info(
            mem_out.stdout, mem_out.returncode[0], dimms, total_size
        )

        logger.info(f"exit code {exit_code}: {msg}")

        sys.exit(exit_code.value)


def parse_buddy_info_lines(
    buddyinfo_lines: Iterable[str], order: int
) -> Iterable[Tuple[str, str, List[int]]]:
    def parse(line: str) -> Tuple[str, str, List[int]]:
        match_result = re.match(
            "^\\s*Node\\s+(?P<node>\\d+).*zone\\s+(?P<zone>\\w+)\\s+(?P<blocks>[\\d ]+\\s*$)",
            line,
        )
        if match_result is not None:
            d: Dict[str, str] = match_result.groupdict()
            blocks = list(map(int, d["blocks"].split()))
            return d["node"], d["zone"], blocks[order:]
        else:
            raise ValueError(
                f"buddyinfo_lines do not contain required info: {buddyinfo_lines}"
            )

    return [parse(line) for line in buddyinfo_lines]


def check_threshold(
    node: str, zone: str, blocks: List[int], order: int, threshold: int
) -> Tuple[ExitCode, str]:
    if zone == "Normal" and not any(n >= threshold for n in blocks):
        return (
            ExitCode.CRITICAL,
            f"insufficient number of memory blocks of order {order} or higher on node: {node} zone: {zone} blocks: {blocks}",
        )
    return ExitCode.OK, "sufficient number of memory"


def process_buddy_info(buddy_info_lines: Iterable[str]) -> Tuple[ExitCode, str]:
    minimum_required_free_blocks_by_page_order = {8: 10}
    overall_exit_code = ExitCode.OK
    overall_msg = "sufficient number of memory"
    for order, threshold in minimum_required_free_blocks_by_page_order.items():
        for node, zone, blocks in parse_buddy_info_lines(buddy_info_lines, order=order):
            exit_code, msg = check_threshold(node, zone, blocks, order, threshold)
            if exit_code > overall_exit_code:
                overall_exit_code = exit_code
                overall_msg = msg

    return overall_exit_code, overall_msg


@check_processor.command()
@common_arguments
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.option(
    "--buddyinfo_path",
    type=click.Path(dir_okay=False, path_type=Path, exists=True),
    default=Path("/proc/buddyinfo"),
    help="Path to read buddy info.",
    show_default=True,
)
@click.pass_obj
@typechecked
def check_buddyinfo(
    obj: Optional[ProcessorCheck],
    cluster: str,
    type: CHECK_TYPE,
    log_level: LOG_LEVEL,
    log_folder: str,
    sink: str,
    sink_opts: Collection[str],
    verbose_out: bool,
    heterogeneous_cluster_v1: bool,
    buddyinfo_path: Path,
) -> None:
    """Query the `/proc` special file system for system state, such as memory fragmentation"""

    node: str = socket.gethostname()
    logger, _ = init_logger(
        logger_name=type,
        log_dir=os.path.join(log_folder, type + "_logs"),
        log_name=node + ".log",
        log_level=getattr(logging, log_level),
    )

    logger.info(
        f"check-processor check-buddyinfo: cluster: {cluster}, node: {node}, type: {type} buddyinfo_path: {buddyinfo_path}."
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
        obj = ProcessorCheckImpl(cluster, type, log_level, log_folder)

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
                name=HealthCheckName.CHECK_BUDDYINFO.value,
                node=node,
                get_exit_code_msg=lambda: (exit_code, msg),
                gpu_node_id=gpu_node_id,
            )
        )
        s.enter_context(
            OutputContext(
                type,
                HealthCheckName.CHECK_BUDDYINFO,
                lambda: (exit_code, msg),
                verbose_out,
            )
        )
        ff = FeatureValueHealthChecksFeatures()
        if ff.get_healthchecksfeatures_disable_check_buddyinfo():
            exit_code = ExitCode.OK
            msg = f"{HealthCheckName.CHECK_BUDDYINFO.value} is disabled by killswitch."
            logger.info(msg)
            sys.exit(exit_code.value)

        try:
            buddy_info_lines = obj.get_buddyinfo_lines(buddyinfo_path)
            exit_code, msg = process_buddy_info(buddy_info_lines)
        except Exception as e:
            exit_code = ExitCode.WARN
            msg = f"check-buddyinfo failed to execute with exception: {e}"

        logger.info(f"exit code {exit_code}: {msg}")

    sys.exit(exit_code.value)


@check_processor.command()
@common_arguments
@timeout_argument
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.option(
    "--expected-source",
    type=click.STRING,
    required=True,
    help="Expected configured clock source",
)
@click.option(
    "--sys-clocksource-file",
    type=click.STRING,
    default="/sys/devices/system/clocksource/clocksource0/current_clocksource",
    help="Path to clocksource definition",
)
@click.pass_obj
@typechecked
def check_clocksource(
    obj: Optional[ProcessorCheck],
    cluster: str,
    type: CHECK_TYPE,
    log_level: LOG_LEVEL,
    log_folder: str,
    timeout: int,
    sink: str,
    sink_opts: Collection[str],
    verbose_out: bool,
    heterogeneous_cluster_v1: bool,
    sys_clocksource_file: str,
    expected_source: str,
) -> None:
    """
    Check if clocksource device is configured as expected
    """

    node: str = socket.gethostname()
    logger, _ = init_logger(
        logger_name=type,
        log_dir=os.path.join(log_folder, type + "_logs"),
        log_name=node + ".log",
        log_level=getattr(logging, log_level),
    )

    logger.info(
        f"check-processor check-clocksource: cluster: {cluster}, node: {node}, type: {type}"
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
        obj = ProcessorCheckImpl(cluster, type, log_level, log_folder)

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
                name=HealthCheckName.CHECK_CLOCKSOURCE.value,
                node=node,
                get_exit_code_msg=lambda: (exit_code, msg),
                gpu_node_id=gpu_node_id,
            )
        )
        s.enter_context(
            OutputContext(
                type,
                HealthCheckName.CHECK_CLOCKSOURCE,
                lambda: (exit_code, msg),
                verbose_out,
            )
        )
        ff = FeatureValueHealthChecksFeatures()
        if ff.get_healthchecksfeatures_disable_check_clocksource():
            exit_code = ExitCode.OK
            msg = (
                f"{HealthCheckName.CHECK_CLOCKSOURCE.value} is disabled by killswitch."
            )
            logger.info(msg)
            sys.exit(exit_code.value)

        try:
            output = obj.get_clocksource(
                timeout_secs=timeout,
                sys_clocksource_file=sys_clocksource_file,
                logger=logger,
            )
            if output.returncode > 0:
                exit_code = ExitCode.WARN
                msg = f"Exit Code {exit_code}: Failed to run command."
                logger.info(msg)
                sys.exit(exit_code.value)

            logger.info(f"Output:\n{output.stdout}")

            found_source = output.stdout.strip()
            if found_source != expected_source:
                exit_code = ExitCode.CRITICAL
                msg = f"Exit Code {exit_code}: Node {node} reports {found_source} source, but expected {expected_source}"
                logger.info(msg)
                sys.exit(exit_code.value)

            if exit_code == ExitCode.UNKNOWN:
                exit_code = ExitCode.OK

        except Exception as e:
            exit_code = ExitCode.WARN
            msg = f"check-clocksource failed to execute with exception: {e}"

        logger.info(f"exit code {exit_code}: {msg}")

    sys.exit(exit_code.value)
