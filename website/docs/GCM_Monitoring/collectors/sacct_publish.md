# sacct_publish

## Overview
Transforms and publishes `sacct` output in parsable2 format to configured sinks. Takes raw `sacct` command output, parses pipe-delimited (parsable2) format, converts timestamps to timezone-aware ISO8601 format, enriches with cluster metadata, and publishes to sink in batches with retry logic.

**Data Type**: `DataType.LOG`
**Schema**: `Sacct`

## Execution Scope

Invoked as a pipeline component (typically by `sacct_backfill` or in shell pipelines).

## Output Schema

### Sacct
Published with `DataType.LOG`:

```python
{
    # SLURM Fields (from sacct -o all)
    "JobID": str,                            # Job identifier
    "JobIDRaw": str,                         # Raw job ID
    "JobName": str,                          # User-specified job name
    "User": str,                             # Job owner
    "Account": str,                          # SLURM account
    "Partition": str,                        # Job partition
    "State": str,                            # Job state (COMPLETED, FAILED, etc.)
    "ExitCode": str,                         # Exit code
    "AllocCPUs": int,                        # Allocated CPUs
    "ReqMem": str,                           # Requested memory
    "AllocNodes": int,                       # Allocated nodes
    # ... plus 40+ additional sacct fields

    # Timestamps (converted to ISO8601 with timezone)
    "Start": str,                            # Job start time
    "End": str,                              # Job end time
    "Submit": str,                           # Submission time
    "Eligible": str,                         # Eligible time

    # Enriched Fields
    "cluster": str,                          # Cluster name
    "derived_cluster": str,                  # Sub-cluster (same as cluster if not `--heterogeneous-cluster-v1`)
    "time": int,                             # Collection timestamp (Unix epoch)
    "end_ds": str,                           # Date string in Pacific Time (YYYY-MM-DD)
}
```

**Note:** The exact fields depend on the SLURM version. See [sacct documentation](https://slurm.schedmd.com/sacct.html) for details.

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `SACCT_OUTPUT` | File/stdin | File or stdin containing sacct output |
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
| `--delimiter` | String | `\|#` | Field delimiter, must be unique enough such that no field has an instance of the delimiter. User input fields like `job name` can break parsing. |
| `--sacct-timezone` | String | System timezone | Timezone of sacct timestamps |
| `--sacct-output-io-errors` | Choice | `strict` | UTF-8 decoding: `strict`, `ignore`, `replace`. Occasionally, user-defined sacct fields (e.g. comment, job name) are not valid utf-8, so we allow the user to choose what should be done in this case |
| `--ignore-line-errors` | Flag | False | Skip lines with field count mismatches |

## Usage Examples

### From stdin (piped from sacct)
```bash
sacct -P -o all -S 2024-01-01 -E 2024-01-02 | \
  gcm sacct_publish --sink stdout
```

### From file
```bash
gcm sacct_publish sacct_output.txt \
  --sink graph_api \
  --sink-opts scribe_category=slurm_jobs
```

### With timezone handling
```bash
# sacct output is in UTC
gcm sacct_publish sacct_output.txt \
  --sacct-timezone UTC \
  --sink file \
  --sink-opts filepath=output.json
```

### Ignore invalid lines
```bash
# Skip lines with malformed data
gcm sacct_publish sacct.txt \
  --ignore-line-errors \
  --sacct-output-io-errors replace \
  --sink stdout
```

### With sacct_backfill
```bash
gcm sacct_backfill new \
  --publish-cmd "gcm sacct_publish --sink graph_api --sink-opts scribe_category=jobs"
```
