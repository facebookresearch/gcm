# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import re
from typing import Callable, Dict, List, Optional, Tuple

from gcm.health_checks.types import ExitCode

# Map of MCE log patterns to ExitCode severity.
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
MCE_SEVERITY_PATTERNS: List[Tuple[re.Pattern[str], ExitCode]] = [
    # Critical: uncorrected hardware errors requiring immediate attention
    (re.compile(r"\[Hardware Error\]", re.IGNORECASE), ExitCode.CRITICAL),
    (re.compile(r"Processor context corrupt", re.IGNORECASE), ExitCode.CRITICAL),
    (re.compile(r"Machine Check Exception", re.IGNORECASE), ExitCode.CRITICAL),
    (re.compile(r"Uncorrected error", re.IGNORECASE), ExitCode.CRITICAL),
    (re.compile(r"Fatal error", re.IGNORECASE), ExitCode.CRITICAL),
    # Warning: corrected errors and thermal throttling (not immediately dangerous
    # but indicate degraded hardware that may fail)
    (re.compile(r"Corrected error", re.IGNORECASE), ExitCode.WARN),
    (re.compile(r"temperature above threshold", re.IGNORECASE), ExitCode.WARN),
    (re.compile(r"cpu clock throttled", re.IGNORECASE), ExitCode.WARN),
    (re.compile(r"CMCI storm", re.IGNORECASE), ExitCode.WARN),
    # OK: recovery messages and benign state changes
    (re.compile(r"temperature.*normal", re.IGNORECASE), ExitCode.OK),
    (re.compile(r"CPU is offline", re.IGNORECASE), ExitCode.OK),
    (re.compile(r"Disabling lock", re.IGNORECASE), ExitCode.OK),
]


def classify_mce_line(line: str) -> Optional[ExitCode]:
    """Classify a single MCE dmesg line by severity.

    Returns None if no pattern matches (line is not a recognized MCE event).
    """
    for pattern, severity in MCE_SEVERITY_PATTERNS:
        if pattern.search(line):
            return severity
    return None


def classify_lines(
    output: str,
    classifier: Callable[[str], Optional[ExitCode]],
) -> Dict[ExitCode, List[str]]:
    """Classify multiple dmesg lines and group by severity.

    Args:
        output: Raw dmesg output (newline-separated).
        classifier: A callable(str) -> Optional[ExitCode].

    Returns:
        Dict mapping ExitCode to list of matching lines.
    """
    result: Dict[ExitCode, List[str]] = {
        ExitCode.CRITICAL: [],
        ExitCode.WARN: [],
        ExitCode.OK: [],
    }
    for line in output.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        severity = classifier(stripped)
        if severity is not None:
            result[severity].append(stripped)
        else:
            # Unknown lines default to WARN for safety
            result[ExitCode.WARN].append(stripped)
    return result
