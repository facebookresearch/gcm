# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
# see T79576706
# Reference: https://slurm.schedmd.com/sacct.html#lbAG
TERMINAL_JOB_STATES = frozenset(
    [
        "boot_fail",
        "bf",
        "cancelled",
        "ca",
        "completed",
        "cd",
        "deadline",
        "dl",
        "failed",
        "f",
        "node_fail",
        "nf",
        "out_of_memory",
        "oom",
        "preempted",
        "pr",
        "requeued",
        "rq",
        "resizing",
        "rs",
        "revoked",
        "rv",
        "timeout",
        "to",
    ]
)
# Slurm job states that would be considered failed to complete.
FAILED_JOB_STATES = frozenset(
    [
        "boot_fail",
        "bf",
        "cancelled",
        "ca",
        "deadline",
        "dl",
        "failed",
        "f",
        "node_fail",
        "nf",
        "out_of_memory",
        "oom",
        "preempted",
        "pr",
        "timeout",
        "to",
    ]
)
# Slurm job states that would be considered pending/waiting
PENDING_JOB_STATES = frozenset(
    [
        "pending",
        "pd",
        "requeued",
        "rq",
        "suspended",
        "s",
    ]
)

RUNNING_JOB_STATES = frozenset(
    [
        "running",
        "r",
    ]
)

# from https://slurm.schedmd.com/sinfo.html#SECTION_NODE-STATE-CODES
NODE_STATES = frozenset(
    [
        "allocated",
        "allocated+",
        "blocked",
        "completing",
        "down",
        "drained",
        "draining",
        "fail",
        "failing",
        "future",
        "idle",
        "inval",
        "maint",
        "reboot_issued",
        "reboot_requested",
        "mixed",
        "perfctrs",
        "planned",
        "power_down",
        "powered_down",
        "powering_down",
        "powering_up",
        "reserved",
        "unknown",
    ]
)

NODE_DOWN_STATES = frozenset(
    [
        "drained",
        "down",
        "maint",
        "powered_down",
        "powering_down",
        "powering_up",
        "fail",
        "future",
        "inval",
        "perfctrs",
    ]
)

NODE_RUNNING_JOB_STATES = frozenset(
    ["allocated", "allocated+", "mixed", "draining", "completing", "failing"]
)

PENDING_RESOURCE_REASONS = frozenset({"Resources", "Priority"})

SLURM_CLI_DELIMITER = "|#"

# sacct fields that should be interpreted as date to do timezone conversions
SACCT_DATE_FIELDS = frozenset(["Start", "Submit", "End", "Eligible"])
