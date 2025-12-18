# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import re
import string
from datetime import timedelta

from typing import cast, SupportsInt

from gcm.monitoring.utils.error import log_error
from gcm.monitoring.utils.parsing.combinators import (
    at_least_one,
    at_least_zero,
    begins_with,
    chain,
    discard_result,
    first_of,
)


def parse_cpus_alloc(v: str) -> int:
    return int(v.split("/")[0])


def parse_cpus_idle(v: str) -> int:
    return int(v.split("/")[1])


def parse_cpus_other(v: str) -> int:
    return int(v.split("/")[2])


def parse_cpus_total(v: str) -> int:
    return int(v.split("/")[3])


def elapsed_string_to_seconds(elapsed_string: str) -> timedelta:
    """Given the Elapsed field from sacct, return a timedelta object.

    The slurm elapsed_string is given in 3 possible formats
    %d-%H:%M:%S (4 values)
    %H:%M:%S    (3 values)
    %M:%S       (2 values)
    """
    elapsed_string = elapsed_string.replace("-", ":")
    units = [int(x.strip()) for x in elapsed_string.split(":")]

    # Fill the remaining positions with 0s
    units = [0] * (4 - len(units)) + units

    # Creates timedelta object that measures the Elapsed time
    run_time = timedelta(
        days=units[0], hours=units[1], minutes=units[2], seconds=units[3]
    )

    return run_time


def extract_gpus_from_gres(gres_string: str) -> int:
    """Extract the number of gpus from the GRES resources string"""
    gpus = 0
    gres_items = gres_string.split(",")
    for gres in gres_items:
        # If a gpu resource has been found.
        if gres.startswith("gpu:"):
            gpus = parse_gres(gres)

    return gpus


@log_error(__name__, return_on_error=0)
def parse_gres_or_tres(v: str) -> int:
    try:
        return parse_gres(v)
    except ValueError:
        return parse_tres(v)


def convert_memory_to_mb(value: str) -> int:
    """Helper function to convert memory values with units to MB.

    Args:
        value: Memory value string like "1000M", "2G", "1T", etc.

    Returns:
        Memory value converted to MB
    """
    if not value or value == "0":
        return 0

    suffix = value[-1]
    if suffix.isdigit():
        return int(int(value) * 1e-6)

    if suffix == "P":
        multiplier = 1_000_000_000
    elif suffix == "T":
        multiplier = 1_000_000
    elif suffix == "G":
        multiplier = 1_000
    elif suffix == "M":
        multiplier = 1
    else:
        raise ValueError(f"Unrecognized suffix in {value}")

    return int(float(value[:-1]) * multiplier)


def parse_gres(v: str) -> int:
    """Parse a GRES string of the form: gpu:{pascal|volta}:<number>[(<stuff>)]

    Examples:

    >>> parse_gres('gpu:volta:8(S:0-1)')
    8
    >>> parse_gres('gpu:pascal:2')
    2
    """
    if v in {"N/A", "(null)"}:
        return 0

    v = str.removeprefix(v, "gres:")
    v = str.removeprefix(v, "gres/")

    parser = chain(
        [
            # matches 'gpu:{volta|pascal}:'
            discard_result(
                chain(
                    [
                        begins_with("gpu:"),
                        at_least_zero(
                            chain(
                                [
                                    # GPU type, e.g. 'pascal', 'volta', or 'H100'.  Match
                                    # anything beginning with an ascii letter.
                                    at_least_one(
                                        first_of(
                                            [
                                                begins_with(c)
                                                for c in string.ascii_letters
                                                + string.digits
                                            ]
                                        )
                                    ),
                                    begins_with(":"),
                                ]
                            )
                        ),
                    ]
                )
            ),
            # the number we want to extract
            at_least_one(first_of([begins_with(c) for c in string.digits])),
        ]
    )
    result, _ = parser(v)
    if result is None:
        raise ValueError(f"Failed to parse {v}")

    parsed, *_ = result
    try:
        return int(cast(SupportsInt, parsed))
    except TypeError as e:
        raise ValueError(f"Failed to parse {v}") from e


def parse_tres(v: str) -> int:
    """Parse a TRES string of the form 'gpu:<number>'."""
    if v in {"N/A", "(null)"}:
        return 0

    v = str.removeprefix(v, "gres:")
    v = str.removeprefix(v, "gres/")

    result = re.match(r"gpu:([0-9]+)", v)
    if result is None:
        raise ValueError(f"Failed to parse '{v}'")
    return int(result[1])


def parse_value_from_tres(s: str, key: str) -> int:
    """Extract an integer value from a TRES string by key.

    Args:
        s: TRES string in format "key1=value1,key2=value2,..."
        key: The key to look for (e.g., "gres/gpu", "cpu", "mem", "node", "billing")

    Returns:
        The integer value associated with the key, or 0 if not found

    Examples:

    >>> parse_value_from_tres('cpu=5200,mem=32500000M,node=65,billing=17487,gres/gpu=520', 'gres/gpu')
    520

    >>> parse_value_from_tres('cpu=5200,mem=32500000M,node=65,billing=17487,gres/gpu=520', 'node')
    65
    """
    if s == "" or s in ["(null)"]:
        return 0

    for kv in s.split(","):
        k, v = kv.split("=")
        if k == key:
            # For memory values, convert to MB
            if key == "mem":
                return convert_memory_to_mb(v)
            else:
                return int(v)

    return 0


def parse_scontrol_maxnodes(v: str) -> int:
    """Parse a SControl MaxNodes string of either 'UNLIMITED' or a number.
    A value of 'UNLIMITED' will return -1
    otherwise will return the exact number

    Examples:

    >>> parse_scontrol_maxnodes('UNLIMITED')
    -1
    >>> parse_gres('64')
    64

    """
    if not v.isdigit():
        return int(-1)
    return int(v)


def parse_job_ids(s: str) -> list[str]:
    """Given a comma separated string of job ids, return a list of job ids."""
    return s.split(",") if s else []
