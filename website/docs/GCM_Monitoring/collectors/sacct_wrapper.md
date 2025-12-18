# sacct_wrapper

## Overview
A wrapper around `sacct` which strictly respects time bounds when using `--parsable2` and only jobs in terminal states are requested.

Occasionally, when using `sacct -S $start -E $end -s $states`, you will get jobs with `End` time just outside of the given [$start, $end] interval (typically 2-3 minutes before $start or 2-3 minutes after $end`). This wrapper filters out these jobs at the boundary so that for all jobs returned, `End` is strictly in [$start, $end].

**Data Type**: N/A (wrapper utility)
**Schemas**: N/A

## Execution Scope

Invoked as a command wrapper (replaces `sacct` in scripts and pipelines).

### Pass-Through
All other `sacct` options are passed through unchanged to the underlying command.

## Usage Examples

### Basic Time Range Query
```bash
# Query jobs from specific date range
gcm fsacct -S 2024-01-01T00:00:00 -E 2024-01-31T23:59:59 -P -o all
```

### State Filtering
```bash
# Get completed and failed jobs
gcm fsacct -S "7 days ago" -E "now" -s "COMPLETED,FAILED" -P -o JobID,User,State
```

### Pipe to Publisher
```bash
# Typical pipeline usage
gcm fsacct -S "1 day ago" -E "now" -P -o all | \
  gcm sacct_publish --sink graph_api
```

### Large Batch Processing
```bash
# Process large date ranges with custom batch size
gcm fsacct \
  -S "2023-01-01" \
  -E "2023-12-31" \
  --batch-size 50000 \
  -P -o all > output.txt
```

### With sacct_backfill
```bash
# Used internally by sacct_backfill
gcm sacct_backfill new \
  -s "jan 1" -e "jan 31" \
  -- \
  gcm sacct_publish --sink otel
```

### Drop-in Replacement
```bash
# Replace existing sacct calls
# Before:
sacct -S 2024-01-01 -P -o all

# After:
gcm fsacct -S 2024-01-01 -P -o all
```
