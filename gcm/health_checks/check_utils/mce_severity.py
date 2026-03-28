# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import re
from typing import Dict, List, Optional, Tuple

from gcm.health_checks.types import ExitCode

# Type alias for severity pattern lists used by classify_line().
SeverityPatterns = List[Tuple[re.Pattern[str], ExitCode]]

# Map of MCE log patterns to ExitCode severity.
#
# Patterns are matched against individual dmesg lines containing "mce:".
# Order matters: first match wins. More specific patterns should come first.
#
# Sample log lines: https://gist.github.com/gustcol/6a701dc0358795cee099cec3e0e596e7
MCE_SEVERITY_PATTERNS: SeverityPatterns = [
    # OK: recovery messages and benign state changes
    (re.compile(r"temperature.*normal", re.IGNORECASE), ExitCode.OK),
    (re.compile(r"CPU is offline", re.IGNORECASE), ExitCode.OK),
    (re.compile(r"Disabling lock", re.IGNORECASE), ExitCode.OK),
    # Warning: corrected errors and thermal throttling (not immediately dangerous
    # but indicate degraded hardware that may fail)
    (re.compile(r"Corrected error", re.IGNORECASE), ExitCode.WARN),
    (re.compile(r"temperature above threshold", re.IGNORECASE), ExitCode.WARN),
    (re.compile(r"cpu clock throttled", re.IGNORECASE), ExitCode.WARN),
    (re.compile(r"CMCI storm", re.IGNORECASE), ExitCode.WARN),
    # Critical: uncorrected hardware errors requiring immediate attention
    (re.compile(r"\[Hardware Error\]", re.IGNORECASE), ExitCode.CRITICAL),
    (re.compile(r"Processor context corrupt", re.IGNORECASE), ExitCode.CRITICAL),
    (re.compile(r"Machine Check Exception", re.IGNORECASE), ExitCode.CRITICAL),
    (re.compile(r"Uncorrected error", re.IGNORECASE), ExitCode.CRITICAL),
    (re.compile(r"Fatal error", re.IGNORECASE), ExitCode.CRITICAL),
]


def classify_line(line: str, patterns: SeverityPatterns) -> Optional[ExitCode]:
    """Classify a single dmesg line by severity.

    Returns None if no pattern matches (line is not a recognized event).
    """
    for pattern, severity in patterns:
        if pattern.search(line):
            return severity
    return None


def classify_lines(
    output: str,
    patterns: SeverityPatterns,
) -> Dict[ExitCode, List[str]]:
    """Classify multiple dmesg lines and group by severity.

    Args:
        output: Raw dmesg output (newline-separated).
        patterns: List of (compiled_regex, ExitCode) tuples.

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
        severity = classify_line(stripped, patterns)
        if severity is not None:
            result[severity].append(stripped)
        else:
            # Unknown lines default to WARN for safety
            result[ExitCode.WARN].append(stripped)
    return result
