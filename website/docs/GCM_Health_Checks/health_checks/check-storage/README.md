# check-storage

Storage validation suite with health checks for disk space, mount points, file/directory existence, and filesystem monitoring.

## Available Health Checks

| Check | Purpose | Key Feature |
|-------|---------|-------------|
| [disk-usage](./disk-usage.md) | Disk space & inode monitoring | Configurable thresholds for usage alerting |
| [mounted-directory](./mounted-directory.md) | Mount verification | Verify directories are mounted |
| [file-exists](./file-exists.md) | File existence validation | Check files exist or optionally do not exist |
| [directory-exists](./directory-exists.md) | Directory validation | Verify directories exist on filesystem |
| [check-mountpoint](./check-mountpoint.md) | Mountpoint consistency | Ensure fstab matches /proc/mounts |
| [disk-size](./disk-size.md) | Disk size validation | Validate disk size meets criteria |

## Quick Start

```shell
# Disk usage check
health_checks check-storage disk-usage --volume /home [CLUSTER] app

# Verify mounted directories
health_checks check-storage mounted-directory --directory /mnt/nfs [CLUSTER] app

# Check file exists
health_checks check-storage file-exists --file /etc/slurm/slurm.conf [CLUSTER] app

# Check directory exists
health_checks check-storage directory-exists --directory /scratch [CLUSTER] app

# Verify mountpoint consistency
health_checks check-storage check-mountpoint --mountpoint /mnt [CLUSTER] app

# Validate disk size
health_checks check-storage disk-size --volume /scratch --size-unit T --operator ">=" --value 10 [CLUSTER] app
```
