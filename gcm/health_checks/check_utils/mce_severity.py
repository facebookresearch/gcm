# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import re
from enum import Enum
from typing import Dict, List, Optional, Tuple


class MceSeverity(Enum):
    """Severity level for MCE (Machine Check Exception) log entries.

    Based on the Linux kernel MCE subsystem log format.
    See: https://www.kernel.org/doc/html/latest/arch/x86/x86_64/machinecheck.html
    """

    CRITICAL = "critical"
    WARN = "warn"
    INFO = "info"


# Map of MCE log patterns to severity.
#
# Patterns are matched against individual dmesg lines containing "mce:".
# Order matters: first match wins. More specific patterns should come first.
#
# Sample dmesg lines (from Linux kernel MCE subsystem):
#
#   [12345.678] mce: [Hardware Error]: Machine check events logged
#   [12345.679] mce: [Hardware Error]: CPU 0: Machine Check Exception: 5 Bank 9
#   [12345.680] mce: [Hardware Error]: RIP !SYM ...
#   [12345.681] mce: [Hardware Error]: TSC ... ADDR ... MISC ...
#   [12345.682] mce: [Hardware Error]: PROCESSOR 0:...
#   [12345.683] mce: Processor context corrupt
#   [12345.684] mce: CPU0: Core temperature above threshold, cpu clock throttled
#   [12345.685] mce: CPU0: Core temperature/speed normal
#   [12345.686] mce: CPU0: Package temperature above threshold, cpu clock throttled
#   [12345.687] mce: CPU0: Package temperature/speed normal
#   [12345.688] mce: [Hardware Error]: Machine check events logged
#   [12345.689] mce: CPU0: 1 Corrected error(s) detected. Check CMCI storm count.
#   [12345.690] mce: CPU is offline
#   [12345.691] mce: Disabling lock cmpxchg
MCE_SEVERITY_PATTERNS: List[Tuple[re.Pattern[str], MceSeverity]] = [
    # Critical: uncorrected hardware errors requiring immediate attention
    (re.compile(r"\[Hardware Error\]", re.IGNORECASE), MceSeverity.CRITICAL),
    (re.compile(r"Processor context corrupt", re.IGNORECASE), MceSeverity.CRITICAL),
    (re.compile(r"Machine Check Exception", re.IGNORECASE), MceSeverity.CRITICAL),
    (re.compile(r"Uncorrected error", re.IGNORECASE), MceSeverity.CRITICAL),
    (re.compile(r"Fatal error", re.IGNORECASE), MceSeverity.CRITICAL),
    # Warning: corrected errors and thermal throttling (not immediately dangerous
    # but indicate degraded hardware that may fail)
    (re.compile(r"Corrected error", re.IGNORECASE), MceSeverity.WARN),
    (re.compile(r"temperature above threshold", re.IGNORECASE), MceSeverity.WARN),
    (re.compile(r"cpu clock throttled", re.IGNORECASE), MceSeverity.WARN),
    (re.compile(r"CMCI storm", re.IGNORECASE), MceSeverity.WARN),
    # Informational: recovery messages and benign state changes
    (re.compile(r"temperature.*normal", re.IGNORECASE), MceSeverity.INFO),
    (re.compile(r"CPU is offline", re.IGNORECASE), MceSeverity.INFO),
    (re.compile(r"Disabling lock", re.IGNORECASE), MceSeverity.INFO),
]


# Map of PCIe AER log patterns to severity.
#
# Sample dmesg lines (from Linux kernel PCIe AER subsystem):
#
#   [12345.678] pcieport 0000:00:01.0: AER: Corrected error received: 0000:01:00.0
#   [12345.679] pcieport 0000:00:02.0: AER: Uncorrectable (Non-Fatal) error received
#   [12345.680] pcieport 0000:00:03.0: AER: Uncorrectable (Fatal) error received
#   [12345.681] pcieport 0000:00:01.0: AER: Multiple Corrected error received
#   [12345.682] pcieport 0000:00:02.0: AER: Multiple Uncorrectable (Non-Fatal) error
#   [12345.683] nvidia 0000:01:00.0: AER: can't recover (no error_detected callback)
PCIE_AER_SEVERITY_PATTERNS: List[Tuple[re.Pattern[str], MceSeverity]] = [
    # Critical: uncorrectable fatal errors — device is unusable
    (
        re.compile(r"Uncorrectable \(Fatal\)", re.IGNORECASE),
        MceSeverity.CRITICAL,
    ),
    (
        re.compile(r"can't recover", re.IGNORECASE),
        MceSeverity.CRITICAL,
    ),
    # Warning: uncorrectable non-fatal — device may still work but is degraded
    (
        re.compile(r"Uncorrectable", re.IGNORECASE),
        MceSeverity.WARN,
    ),
    # Info: corrected errors — hardware auto-recovered, but high counts may
    # indicate degradation
    (
        re.compile(r"Corrected error", re.IGNORECASE),
        MceSeverity.INFO,
    ),
]


def classify_mce_line(line: str) -> Optional[MceSeverity]:
    """Classify a single MCE dmesg line by severity.

    Returns None if no pattern matches (line is not a recognized MCE event).
    """
    for pattern, severity in MCE_SEVERITY_PATTERNS:
        if pattern.search(line):
            return severity
    return None


def classify_pcie_aer_line(line: str) -> Optional[MceSeverity]:
    """Classify a single PCIe AER dmesg line by severity.

    Returns None if no pattern matches.
    """
    for pattern, severity in PCIE_AER_SEVERITY_PATTERNS:
        if pattern.search(line):
            return severity
    return None


def classify_lines(
    output: str,
    classifier: object,
) -> Dict[MceSeverity, List[str]]:
    """Classify multiple dmesg lines and group by severity.

    Args:
        output: Raw dmesg output (newline-separated).
        classifier: A callable(str) -> Optional[MceSeverity].

    Returns:
        Dict mapping severity to list of matching lines.
    """
    result: Dict[MceSeverity, List[str]] = {
        MceSeverity.CRITICAL: [],
        MceSeverity.WARN: [],
        MceSeverity.INFO: [],
    }
    for line in output.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        severity = classifier(stripped)  # type: ignore[operator]
        if severity is not None:
            result[severity].append(stripped)
        else:
            # Unknown MCE/AER lines default to WARN for safety
            result[MceSeverity.WARN].append(stripped)
    return result
