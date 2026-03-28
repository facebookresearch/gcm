# scontrol_config

## Overview
Collects SLURM cluster-wide configuration data using `scontrol show config` and publishes a single aggregated configuration record at regular intervals. Provides monitoring of cluster-wide SLURM configuration including controller and backup controller settings, authentication and security configuration, scheduler type and parameters, priority weights and decay settings, accounting storage configuration, job limits and timeout values, and plugin configurations.

**Data Type**: `DataType.LOG`, **Schema**: `ScontrolConfig`

## Execution Scope

Single node in the cluster.

## Output Schema

### ScontrolConfig
Published with `DataType.LOG`:

```python
{
    "cluster": str,                        # Cluster identifier
    "derived_cluster": str,                # Derived cluster for heterogeneous clusters

    # Controller Configuration
    "ClusterName": str | None,
    "ControlMachine": str | None,          # Primary controller hostname
    "ControlAddr": str | None,             # Primary controller address
    "BackupController": str | None,        # Backup controller hostname
    "BackupAddr": str | None,              # Backup controller address

    # User/Permission Configuration
    "SlurmUser": str | None,               # SLURM daemon user
    "SlurmUID": int | None,                # SLURM daemon UID
    "SlurmdUser": str | None,              # slurmd daemon user
    "SlurmdUID": int | None,               # slurmd daemon UID

    # Authentication
    "AuthType": str | None,                # Authentication type (auth/munge, etc.)
    "AuthInfo": str | None,                # Authentication info
    "CryptoType": str | None,              # Cryptography type

    # Scheduler Configuration
    "SchedulerType": str | None,           # Scheduler plugin (sched/backfill)
    "SchedulerParameters": str | None,     # Scheduler-specific parameters
    "SelectType": str | None,              # Resource selection plugin
    "SelectTypeParameters": str | None,    # Selection parameters

    # Priority Configuration
    "PriorityType": str | None,            # Priority plugin (priority/multifactor)
    "PriorityWeightAge": int | None,       # Weight for job age
    "PriorityWeightFairShare": int | None, # Weight for fair-share
    "PriorityWeightJobSize": int | None,   # Weight for job size
    "PriorityWeightPartition": int | None, # Weight for partition priority
    "PriorityWeightQOS": int | None,       # Weight for QoS priority
    "PriorityWeightAssoc": int | None,     # Weight for association
    "PriorityDecayHalfLife": str | None,   # Priority decay half-life
    "PriorityMaxAge": str | None,          # Maximum age for priority

    # Accounting
    "AccountingStorageType": str | None,   # Accounting plugin (slurmdbd)
    "AccountingStorageHost": str | None,   # Database host
    "AccountingStoragePort": int | None,   # Database port
    "AccountingStorageUser": str | None,   # Database user
    "AccountingStorageLoc": str | None,    # Database location/name

    # Timeouts and Limits
    "SlurmctldTimeout": str | None,        # Controller timeout
    "SlurmdTimeout": str | None,           # Daemon timeout
    "InactiveLimit": str | None,           # Inactive job timeout
    "MinJobAge": str | None,               # Minimum job record age
    "KillWait": str | None,                # Time to wait before SIGKILL
    "Waittime": int | None,                # Wait time for nodes

    # Job Limits
    "MaxJobCount": str | None,             # Maximum concurrent jobs
    "MaxNodeCount": str | None,            # Maximum nodes per job
    "MaxTasksPerNode": str | None,         # Maximum tasks per node
    "MaxArraySize": str | None,            # Maximum array job size

    # Logging
    "SlurmctldLogFile": str | None,        # Controller log file path
    "SlurmdLogFile": str | None,           # Daemon log file path
    "SlurmctldDebug": str | None,          # Controller debug level
    "SlurmdDebug": str | None,             # Daemon debug level

    # Plugins
    "JobAcctGatherType": str | None,       # Job accounting gather plugin
    "ProctrackType": str | None,           # Process tracking plugin
    "TaskPlugin": str | None,              # Task plugin
    "SwitchType": str | None,              # Switch/interconnect plugin

    # Additional fields (150+ total)
    # See gcm/schemas/slurm/scontrol_config.py for complete list
    ...
}
```

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--cluster` | String | Auto-detected | Cluster name for metadata enrichment |
| `--sink` | String | **Required** | Sink destination, see [Exporters](../exporters/README.md) |
| `--sink-opts` | Multiple | - | Sink-specific options |
| `--log-level` | Choice | INFO | DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `--log-folder` | String | `/var/log/fb-monitoring` | Log directory |
| `--stdout` | Flag | False | Display metrics to stdout in addition to logs |
| `--heterogeneous-cluster-v1` | Flag | False | Enable per-partition metrics for heterogeneous clusters |
| `--interval` | Integer | 300 | Seconds between collection cycles (5 minutes) |
| `--once` | Flag | False | Run once and exit (no continuous monitoring) |
| `--retries` | Integer | Shared default | Retry attempts on sink failures |
| `--dry-run` | Flag | False | Print to stdout instead of publishing to sink |
| `--chunk-size` | Integer | Shared default | The maximum size in bytes of each chunk when writing data to sink.  |

## Usage Examples

### Basic Daily Collection
```bash
gcm scontrol_config --sink otel --sink-opts "log_resource_attributes={'attr_1': 'value1'}"
```

### One-Time Snapshot
```bash
gcm scontrol_config --once --sink stdout
```

### Hourly Collection
```bash
# Monitor config changes more frequently
gcm scontrol_config --interval 3600 --sink file --sink-opts filepath=/tmp/config.json
```
