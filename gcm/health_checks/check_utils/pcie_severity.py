# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import re
from typing import List, Optional, Tuple

from gcm.health_checks.types import ExitCode

# Map of PCIe AER log patterns to ExitCode severity.
#
# Sample dmesg lines (from Linux kernel PCIe AER subsystem):
#
#   [12345.678] pcieport 0000:00:01.0: AER: Corrected error received: 0000:01:00.0
#   [12345.679] pcieport 0000:00:02.0: AER: Uncorrectable (Non-Fatal) error received
#   [12345.680] pcieport 0000:00:03.0: AER: Uncorrectable (Fatal) error received
#   [12345.681] pcieport 0000:00:01.0: AER: Multiple Corrected error received
#   [12345.682] pcieport 0000:00:02.0: AER: Multiple Uncorrectable (Non-Fatal) error
#   [12345.683] nvidia 0000:01:00.0: AER: can't recover (no error_detected callback)
PCIE_AER_SEVERITY_PATTERNS: List[Tuple[re.Pattern[str], ExitCode]] = [
    # Critical: uncorrectable fatal errors — device is unusable
    (re.compile(r"Uncorrectable \(Fatal\)", re.IGNORECASE), ExitCode.CRITICAL),
    (re.compile(r"can't recover", re.IGNORECASE), ExitCode.CRITICAL),
    # Warning: uncorrectable non-fatal — device may still work but is degraded
    (re.compile(r"Uncorrectable", re.IGNORECASE), ExitCode.WARN),
    # OK: corrected errors — hardware auto-recovered, but high counts may
    # indicate degradation
    (re.compile(r"Corrected error", re.IGNORECASE), ExitCode.OK),
]


def classify_pcie_aer_line(line: str) -> Optional[ExitCode]:
    """Classify a single PCIe AER dmesg line by severity.

    Returns None if no pattern matches.
    """
    for pattern, severity in PCIE_AER_SEVERITY_PATTERNS:
        if pattern.search(line):
            return severity
    return None
