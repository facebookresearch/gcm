# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from dataclasses import dataclass, field
from typing import List, Optional, Union

from gcm.health_checks.types import ExitCode


@dataclass
class Metric:
    """
    A metric object, which converts to string in nagios format:
        'metric_name'=value[units][;warn][;crit][;max][;min]'

    This also lines up with nagios threshholds, see here:
        https://nagios-plugins.org/doc/guidelines.html#THRESHOLDFORMAT
    """

    name: str
    value: Union[float, str]
    units: str = ""
    metric_warn: Optional[str] = None
    metric_crit: Optional[str] = None
    metric_max: Optional[str] = None
    metric_min: Optional[str] = None

    def __str__(self) -> str:
        return (
            f"'{self.name}'={self.value}{self.units}"
            + (f";{self.metric_warn}" if self.metric_warn is not None else ";")
            + (f";{self.metric_crit}" if self.metric_crit is not None else ";")
            + (f";{self.metric_min}" if self.metric_min is not None else ";")
            + (f";{self.metric_max}" if self.metric_max is not None else ";")
        ).rstrip(";")


@dataclass
class CheckOutput:
    check_name: str
    check_status: ExitCode = ExitCode.UNKNOWN
    short_out: str = ""
    long_out: List[str] = field(default_factory=list)
    short_metrics: List[Metric] = field(default_factory=list)
    long_metrics: List[List[Metric]] = field(default_factory=list)

    def __eq__(self, other: object) -> bool:
        # We consider two check outputs to be the same if their string outputs are the same
        if isinstance(other, CheckOutput):
            return str(self) == str(other)

        else:
            return False

    def __str__(self) -> str:
        msg = f"{self.check_name}" + (f" - {self.short_out}" if self.short_out else "")

        long_output = "\n".join(self.long_out).strip()

        if self.short_metrics or self.long_out or self.long_metrics:
            msg += f" | {' '.join([str(metric) for metric in self.short_metrics])}\n"
        if long_output != "" or self.long_metrics:
            msg += long_output

        if self.long_metrics:
            msg += " | " + "\n".join(
                [
                    " ".join(list(map(lambda x: str(x), metric_set)))
                    for metric_set in self.long_metrics
                ]
            )

        return msg
