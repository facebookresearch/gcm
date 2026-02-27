# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import re

from gcm.health_checks.check_utils.mce_severity import SeverityPatterns
from gcm.health_checks.types import ExitCode

# Map of PCIe AER log patterns to ExitCode severity.
# Order matters: first match wins. More specific patterns should come first.
#
# Sample log lines: https://gist.github.com/gustcol/6a701dc0358795cee099cec3e0e596e7
PCIE_AER_SEVERITY_PATTERNS: SeverityPatterns = [
    # OK: corrected errors — hardware auto-recovered, but high counts may
    # indicate degradation
    (re.compile(r"Corrected error", re.IGNORECASE), ExitCode.OK),
    # Warning: uncorrectable non-fatal — device may still work but is degraded
    (re.compile(r"Uncorrectable \(Non-Fatal\)", re.IGNORECASE), ExitCode.WARN),
    # Critical: uncorrectable fatal errors — device is unusable
    (re.compile(r"Uncorrectable", re.IGNORECASE), ExitCode.CRITICAL),
    (re.compile(r"can't recover", re.IGNORECASE), ExitCode.CRITICAL),
]
