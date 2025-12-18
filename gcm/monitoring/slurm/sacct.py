# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging

import subprocess
from typing import Generator, Hashable, Optional

from gcm.monitoring.dataclass_utils import instantiate_dataclass
from gcm.monitoring.utils.shell import get_command_output
from gcm.schemas.slurm.sacct import SacctMetrics


def parse_slurm_jobs(
    start_time: str,
    end_time: str,
    logger: logging.Logger,
    partition: Optional[str] = None,
) -> list[SacctMetrics]:
    """Parse SLURM's job accounting data over the time window.

    Precondition:
        start_time - The sacct starting interval for jobs.
                Format: "YYYY-MM-DDThh:mm:ss"
        end_time - The sacct ending interval for jobs.
                Format: YYYY-MM-DDThh:mm:ss"

    Postcondition:
        Return a list of SLURM jobs.

    sacct (necessary fields)
        -a Retrieve job information from all users
        -T Truncate the start/end time of jobs to fit the interval
           (Avoid - this results in incorrect elapsed times)
        -D Keep all occurances of jobs that have duplicate ids
           (Necessary in the case where slurm job ids are reset.)
        -X Show cumulative statistics for each job, not intermediate steps.
        -P Use the '|' delimiter.
    """

    # Retrieve the sacct information
    # List of fields for sacct can be referenced here https://slurm.schedmd.com/sacct.html#SECTION_Job-Accounting-Fields
    fields = "jobid,user,alloccpus,alloctres,reqnodes,reqtres,submit,start,end,state,allocnodes,elapsed,suspended,account"
    sacct_cmd = [
        "sacct",
        "-a",
        "-D",
        "-X",
        "-P",
        "--noconvert",
        "-S {}".format(start_time),
        "-E {}".format(end_time),
        "--format={}".format(fields),
    ]
    if partition is not None:
        sacct_cmd.extend(["--partition", partition])
    result = get_command_output(sacct_cmd)

    # Extract the lines
    lines = result.split("\n")

    # If the last line is empty, remove it.
    if lines[-1].strip() == "":
        lines = lines[:-1]

    # The header is included; provides dict keys.
    header = lines[0]

    # The values are split using "|" as the delimiter.
    keys = header.split("|")

    # Create list of jobs.
    jobs = []

    # Start at the third line. The previous ones provide header & cluster info.
    for line in lines[1:]:
        values = line.split("|")

        # For correct parsing, convert unicode strings to ASCII.
        job_item: dict[Hashable, str | int] = {
            key: values[idx].strip() for idx, key in enumerate(keys)
        }
        # If the job is currently running, ending times are "Unknown".
        if job_item["End"] == "Unknown":
            # Truncate the ending time.
            job_item["End"] = end_time
        sacct_metrics = instantiate_dataclass(SacctMetrics, job_item, logger=logger)
        jobs.append(sacct_metrics)
    return jobs


def get_sacct_lines(p: subprocess.Popen, delimiter: str) -> Generator[str, None, None]:
    """
    Gets a sacct stdout (does post processing to clean
    user generated fields) and generates a single sacct line
    at a time.

    post processing steps:
    - \n (line breaker) removal: \n in user generated fields cause
        issues when parsing.

    """
    with p:
        stdout = p.stdout
        assert stdout is not None, "It should be piped due to subprocess.PIPE"

        first_line = stdout.readline()
        yield first_line
        fields_number = first_line.count(delimiter)

        prev_line, prev_line_delimiters = "", 0
        for line in stdout:
            line_delimiters = line.count(delimiter)
            if line_delimiters < fields_number:
                if prev_line_delimiters + line_delimiters == fields_number:
                    yield prev_line + line
                    prev_line = ""
                    prev_line_delimiters = 0
                    continue
                elif prev_line_delimiters + line_delimiters > fields_number:
                    raise Exception(
                        f"The following sacct line has more delimiters than expected: {line}"
                    )

                # escape line breakers
                prev_line += line.replace("\n", "\\n")
                prev_line_delimiters += line_delimiters
            else:
                yield line
