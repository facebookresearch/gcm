# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import datetime as dt
import subprocess
from dataclasses import dataclass
from tempfile import NamedTemporaryFile
from typing import Iterable, List, Optional


def get_datetime(date_str: str) -> dt.datetime:
    cmd = ["date", r"+%Y-%m-%dT%H:%M:%S%:z", "-d", date_str]

    try:
        p = subprocess.run(
            cmd,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as e:
        raise ValueError(e.stderr) from e

    return dt.datetime.fromisoformat(p.stdout.strip())


def get_datetimes(date_strs: Iterable[str]) -> List[dt.datetime]:
    """An optimized version of `get_datetime` when multiple dates need to be parsed.

    Each call of `get_datetime` creates a new subprocess, so the number of subprocesses
    that are created and destroyed is O(number of dates). This function only creates and
    destroys a single subprocess given any number of dates.
    """
    date_strs_list = list(date_strs)
    with NamedTemporaryFile("w") as f:
        f.write("\n".join(date_strs_list))
        f.flush()

        try:
            p = subprocess.run(
                ["date", r"+%Y-%m-%dT%H:%M:%S%:z", "-f", f.name],
                check=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except subprocess.CalledProcessError as e:
            raise ValueError(e.stderr) from e
        # Some versions of GNU date -f skip invalid lines without failing.
        # Check stderr for errors to catch these cases.
        if p.stderr:
            raise ValueError(p.stderr)
        date_iso_strs = p.stdout.strip().split("\n")
        return [dt.datetime.fromisoformat(s) for s in date_iso_strs]


@dataclass
class ClosedInterval:
    lower: Optional[dt.datetime] = None
    upper: Optional[dt.datetime] = None

    def __post_init__(self) -> None:
        if self.lower is None or self.upper is None:
            return

        if self.lower > self.upper:
            raise ValueError(
                f"Lower ({self.lower}) must be less than or equal to upper ({self.upper})"
            )

    def __contains__(self, x: dt.datetime) -> bool:
        # ugly because mypy is not very smart
        if self.lower is None:
            if self.upper is None:
                return True
            return x <= self.upper

        if self.upper is None:
            return self.lower <= x
        return self.lower <= x <= self.upper


@dataclass
class BoundedClosedInterval(ClosedInterval):
    lower: dt.datetime
    upper: dt.datetime
