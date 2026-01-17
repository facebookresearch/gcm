<!--
Copyright (c) Meta Platforms, Inc. and affiliates.
All rights reserved.
-->
# Health check documentation

This repo contains a list of different checks for HPC clusters.
Documentation and examples for each test can be found below.

For more information please refer to the files in [`docs/`](../docs/).

Refer to [`CONTRIBUTING.md`](../CONTRIBUTING.md) and [`health_checks_onboarding.md`](../docs/health_checks_onboarding.md) for information about contributing to the repo and the health-checks code.

The checks are invoked as CLI commands, and need to pass some parameters to execute them. Information about these parameters can be obtained with the help message.
Here we only explain some of the important parameters.

### Telemetry Parameters

Each one of the checks has the `--sink` and `--sink-opt` (or `-o` for short) that specify how telemetry will be provided for each check.
To see the available parameters you can execute a command with the `--help` option.
By default the `do_nothing` sink will be used. An example of how to execute a check with specific `sink` options is:
```shell
health_checks check-dcgmi diag fair_cluster prolog --sink=graph_api -o app_secret=<secret key>
```
or if you want no telemetry you can specify the `--sink=do_nothing` parameter.
```shell
health_checks check-dcgmi diag fair_cluster prolog --sink=do_nothing
```
In the examples below we do not specify any telemetry for simplicity.
Telemetry cannot be utilized when the health-checks are being run as part of an application (i.e. `health_checks check-process check-running-process fair_cluster app`).

### Specifying parameters from a config file

To ease the process of providing parameters to the checks, one could use a config file that defines these parameters.
The `health_checks` command supports the `--config` option that can get a configuration file as in `toml` format to read the configuration parameters. This can be particularly handy for parameters that are the same across the different checks or to be able to change the parameters of the check without modifying the command.

An example of a `toml` file that specifies check parameters can be found at [./config/config.toml](./config/config.toml).
You can see from this example that you can define parameters for every check following the check's command-subcommand hierarchy.

Assuming that you have created a config file to specify the parameters for the check, you can then execute the health-check command as:
```shell
$ config_path=<path to config>
$ health_checks --config=$config_path check-dcgmi diag
```
This option is available for all the checks that are described below and you can use it.

### Specifying feature flags from a config file

To ease the process of making code changes without impacting other clusters, and to be able to add killswitches for quickly disabling a health-check, we've added features flags.

The `health_checks` command supports the `--features-config` ooption that can get a configuration file in `toml` format that contains the feature flags definitions.
An example of a `toml` file that has killswitches for the checks can be found at [./config/feature_example.toml](./config/feature_example.toml)

The process of adding new feature flags is automated. You can find details on how to add and use features in your code in [`health_checks_onboarding.md`](../docs/health_checks_onboarding.md).

Assuming that you have created a config file to specify the features you want to use, you can then execute the health-check command as:
```shell
$ config_path=<path to config>
$ features_path=<path to features config>
$ health_checks --features-config=$features_path --config=$config_path check-dcgmi diag
```


## Check Contents
- [check-telemetry](#check-telemetry)
- [check-dcgmi](#check-dcgmi)
- [check-process](#check-process)
- [check-nvidia-smi](#check-nvidia-smi)
- [check-syslogs](#check-syslogs)
- [cuda-memtest](#cuda-memtest)
- [check-nccl](#check-nccl)
- [check-hca](#check-hca)
- [check-storage](#check-storage)
- [check-ipmitool](#check-ipmitool)
- [check-processor](#check-processor)
- [check-service](#check-service)
- [check-ib](#check-ib)
- [check-authentication](#check-authentication)
- [check-node](#check-node)
- [check-pci](#check-pci)
- [check-blockdev](#check-blockdev)
- [check-ethlink](#check-ethlink)
- [check-sensors](#check-sensors)


# check-telemetry <div id='check-telemetry'/>
Perform the telemetry operation for a health-check without executing any of the current checks.

File: `gcm/health_checks/checks/check_telemetry.py`

Example of execution:
```shell
$ health_checks check-telemetry --help # to see al the available options
$ health_checks check-telemetry fair_cluster prolog --exit_code=2 --health-check-name="check zombie" --msg="test zombie" --node=node1000 --job-id=21 --sink=graph_api -o app_secret=<app secret> -o scribe_category=test_cluster_health # perform telemetry with the graph_api and the specified parameters

```


# check-dcgmi <div id='check-dcgmi'/>
Check the GPUs with:
1. the `dcgmi diag -r \<level\>` command to get diagnostics report
2. the `dcgmi nvlink -e` command for nvlink errors
3. the `dcgmi nvlink -s` command for nvlink status

File: `gcm/health_checks/checks/check_dcgmi.py`

Examples of execution:
```shell
$ health_checks check-dcgmi --help # For a list of the available options
$ health_checks check-dcgmi diag fair_cluster prolog -x "Blacklist" -x "Inforom" --sink=do_nothing
$ health_checks check-dcgmi diag fair_cluster prolog --log-folder="healthchecks" -x "Blacklist" -x "Inforom" --sink=do_nothing
$ health_checks check-dcgmi nvlink -c nvlink_errors fair_cluster prolog --data_error_threshold=10 --flit_error_threshold=30 --sink=do_nothing
$ health_checks check-dcgmi nvlink -c nvlink_errors -c nvlink_status fair_cluster prolog --gpu_num=8 --data_error_threshold=10 --sink=do_nothing
```

# check-process <div id='check-process'/>

Perform checks for processes on the on the node.
1. Check the node for zombie / defunct processes.
2. Check if specific processes are running on the node.

Files: `gcm/health_checks/checks/check_process.py`, `gcm/health_checks/checks/check_zombie.py`, `gcm/health_checks/checks/check_running_process.py`

Examples of execution:
```shell
$ health_checks check-process check-zombie --help # For a list of the available options
$ health_checks check-process check-zombie --elapsed=200 fair_cluster prolog --sink=do_nothing
$ health_checks check-process check-zombie fair_cluster prolog --log-folder="healthchecks" --elapsed=200 fair_cluster prolog --sink=do_nothing
$ health_checks check-process check-running-process fair_cluster prolog -p sshd -p slurmd --sink=do_nothing # check if sshd and slurmd processes are running
```

# check-nvidia-smi <div id='check-nvidia-smi'/>

Perform checks using the NVML library.
The supported checks are:
1. Check GPU number
2. Check for running processes on the GPUs
3. Check GPU clock frequencies
4. Check GPU temperature
5. Check GPU memory usage
6. Check GPU retired pages
7. Check ECC volatile errors
8. Check for remapped rows
9. Check VBIOS mismatch

File: `gcm/health_checks/checks/check_nvidia_smi.py`

Examples of execution:
```shell
$ health_checks check-nvidia-smi --help
$ health_checks check-nvidia-smi fair_cluster prolog -c gpu_num --sink=do_nothing
$ health_checks check-nvidia-smi fair_cluster prolog -c gpu_num -c running_procs -c clock_freq -c gpu_temperature --gpu_temperature_threshold=84 --sink=do_nothing
$ health_checks check-nvidia-smi fair_cluster prolog -c gpu_mem_usage --gpu_mem_usage_threshold=850 --sink=do_nothing # giving the critical threshold in MB for GPU mem utilization
$ health_checks check-nvidia-smi fair_cluster prolog -c gpu_retired_pages --gpu_retired_pages_threshold=10 --sink=do_nothing # Check if there are pending retired pages or retired pages are above the threshold
$ health_checks check-nvidia-smi fair_cluster prolog -c ecc_uncorrected_volatile_total -c ecc_corrected_volatile_total --ecc_uncorrected_volatile_threshold=0 --ecc_corrected_volatile_threshold=50000000 --sink=do_nothing # Check for ECC errors
$ health_checks check-nvidia-smi fair_cluster prolog -c row_remap --sink=do_nothing # Check that there are no pending or failed row remaps
```

# check-syslogs <div id='check-syslogs'/>

Check the system logs for error messages.
1. Check for link flap errors
2. Check for XID errors
3. Check for IO errors

File: `gcm/health_checks/checks/check_syslogs.py`

Example of execution:
```shell
$ health_checks check-syslogs --help # For a list of the available options
$ health_checks check-syslogs link-flaps fair_cluster prolog  --sink=do_nothing # to check for link flaps
$ health_checks check-syslogs xid fair_cluster prolog --sink=do_nothing # to check for xid errors
$ health_checks check-syslogs io-errors fair_cluster prolog --sink=do_nothing # to check for IO errors
```

# cuda memtest <div id='cuda-memtest'/>
Check to make sure cuda memory can be allocated.

File: `gcm/health_checks/checks/check_memtest.py`

Example of execution:
```shell
$ health_checks cuda memtest --help
$ health_checks cuda memtest fair_cluster prolog  --size=10 --sink=do_nothing
$ health_checks cuda memtest fair_cluster prolog  --log-folder="healthchecks" --size=10 --sink=do_nothing
```

# check-nccl <div id='check-nccl'/>
Run NCCL tests on the nodes.
1. Run single node nccl-tests
2. Run pairwise nccl-tests

File: `gcm/health_checks/checks/check_nccl.py`

Example of execution:
```shell
# For a list of the available options
$ health_checks check-nccl --help

# Single node all_reduce_perf nccl test wihout nvlink
$ health_checks check-nccl fair_cluster prolog -p all_reduce --nccl-tdir /shared/home/abinesh/nccl-tests/build/ --critical-threshold 18 --sink=do_nothing

# Single node all_reduce_perf nccl test wih nvlink
$ health_checks check-nccl fair_cluster prolog -p all_reduce --nvlink --nccl-tdir /shared/home/abinesh/nccl-tests/build/ --critical-threshold 180 --sink=do_nothing

# Exhaustive pairwise all_reduce_perf nccl test - pairwise nccl test run on all possible pairs.
$ health_checks check-nccl fair_cluster prolog -p all_reduce --pairwise --hostlist=fairwus3-1-htc-[740,742-743] --nccl-tdir /shared/home/abinesh/nccl-tests/build/ --critical-threshold 100 --sink=do_nothing

# Quick pairwise all_reduce_perf nccl test - each node is covered by only one pair.
# SLURM_JOB_NODELIST env var can be use be directly passed on to the hostlist option if running within slurm.
$ health_checks check-nccl fair_cluster prolog -p all_reduce --pairwise-quick --hostlist=$SLURM_JOB_NODELIST --nccl-tdir /shared/home/abinesh/nccl-tests/build/ --critical-threshold 100 --sink=do_nothing
```

# check-hca <div id='check-hca'/>
Check if HCAs are present and count matches the expectation.

File: `gcm/health_checks/checks/check_hca.py`

Example of execution:
```shell
$ health_checks check-hca fair_cluster prolog  --expected-count 9 --sink=do_nothing
```

# check-storage <div id='check-storage'/>
1. Check if there is enough space/inodes on the specified disks.
2. Check if a directory is mounted.
3. Check if a file exists.
4. Check if a directory exists.
5. Check if fstab and mounts are the same for a mountpoint

File: `gcm/health_checks/checks/check_storage.py`

Example of execution:
```shell
$ health_checks check-storage --help # For a list of the available options
$ health_checks check-storage disk-usage fair_cluster prolog -v /dev/loop3 -v /dev/root --usage-critical-threshold=83 --usage-warning-threshold=70 --sink=do_nothing # to check the disk usage
$ health_checks check-storage disk-usage fair_cluster prolog -v /dev/loop3 -v /dev/root --usage-critical-threshold=83 --usage-warning-threshold=70 --inode-check --sink=do_nothing # to check the inode usage
$ health_checks check-storage mounted-directory fair_cluster prolog -d /shared -d /sched --sink=do_nothing # check if the specified directories are mounted
$ health_checks check-storage file-exists -f /usr/bin/ls -f /usr/bin/cat fair_cluster nagios # check that the files exist
$ health_checks check-storage file-exists -d /usr/bin/ -d /scratch # check that the directories exist
$ health_checks check-storage check-mountpoint --mountpoint=/checkpoint/ fair_cluster nagios
```


# check-ipmitool <div id='check-ipmitool'/>
1. Check System Event (sel) Logs for errors. (sudo might be required)

File: `gcm/health_checks/checks/check_ipmitool.py`

Example of execution:
```shell
$ health_checks check-ipmitool --help --help # For a list of the available options
$ health_checks check-ipmitool check-sel fair_cluster prolog --clear_log_threshold=40 --sink=do_nothing
```

# check-processor <div id='check-processor'/>
Processor based checks.

1. Check if the processor frequency is at least as specified
2. Check that the processor frequency governor is as specified
3. Check memory size and number of DIMMs is as specified
4. Check buddy info for memory fragmentation

File: `gcm/health_checks/checks/check_processor.py`

Example of execution:
```shell
$ health_checks check-processor --help # For a list of the available options
$ health_checks check-processor processor-freq fair_cluster prolog --proc_freq=1500 --sink=do_nothing # to check that processor freq is at list 1500MHz
$ health_checks check-processor cpufreq-governor fair_cluster prolog --governor="performance" --sink=do_nothing # check that frequency governor is performance.
$ health_checks check-processor check-mem-size --dimms=12 --total-size=768 fair_cluster nagios # Specify the expected values
$ health_checks check-processor check-mem-size fair_cluster nagios # use known values for the DIMMs and size
$ health_checks check-processor check-buddyinfo fair_cluster nagios --sink=do_nothing
```

# check-service <div id='check-service'/>

Check cluster services.

1. Check if a service is active with systemctl
2. Check if the version of a package matches the expected
3. Slurm service checks:
 * Check if the node can communicate to sufficient number of slurmctld daemon controllers
 * Check if the node is in a state to accept new jobs according to slurm
 * Check cluster availability by checking the percentage of nodes in DOWN and DRAIN states across the cluster
4. ssh service checks:
* Check ssh connection to remote nodes

 Files: `gcm/health_checks/checks/check_service.py`, `gcm/health_checks/checks/check_slurm.py`, `gcm/health_checks/checks/check_ssh.py`

 Example of execution:
 Example of execution:
```shell
$ health_checks check-service --help # For a list of the available service checks
$ health_checks check-service service-status fair_cluster prolog -s slurmd -s sssd --sink=do_nothing # check if slurmd and sssd services are active
$ health_checks check-service package-version fair_cluster prolog -p slurm -v 22.05.6-1.cluster_name.1 --sink=do_nothing # check package's version
$ health_checks check-service slurmctld-count fair_cluster prolog --slurmctld-count=2 --sink=do_nothing # check if node can reach at least two slurm controllers
$ health_checks check-service node-slurm-state fair_cluster prolog --sink=do_nothing # check that node is in state to accept job
$ health_checks check-service ssh-connection fair_cluster prolog --host fairwus3-3-htc-715 --host fairwus3-3-htc-712 --sink=do_nothing # check that ssh connection to hosts is possible
$ health_checks check-service cluster-availability fair_cluster nagios --critical_threshold=25 --warning_threshold=15 --sink=do_nothing # check if the percentage of nodes in DRAIN and DOWN states is above 15% for a warning or 25% for a critical error
```


# check-ib <div id='check-ib'/>

Query the status of IB devices.
1. Check ibstat
2. Check ib-interfaces
3. Check iblinks

 Files: `gcm/health_checks/checks/check_ibstat.py`

 Example of execution:
```shell
$ health_checks check-ib --help
$ health_checks check-ib check-ibstat fair_cluster nagios --sink=do_nothing
$ health_checks check-ib check-ib-interfaces fair_cluster nagios --sink=do_nothing
$ health_checks check-ib check-iblink cluster_name nagios --sink=do_nothing
```

# check-authentication <div id='check-authentication'/>
Authentication related checks.

1. Check password status

Files: `gcm/health_checks/checks/check_authentication.py`

 Example of execution:
```shell
$ health_checks check-authentication --help
$ health_checks check-authentication password-status fair_cluster nagios -u akokolis -s L --sink=do_nothing
```

# check-node <div id='check-node'/>

Perform node related checks.

1. Check node uptime
2. Check module
3. Check dnf repos

 Files: `gcm/health_checks/checks/check_node.py`

  Example of execution:
```shell
$ health_checks check-node --help
$ health_checks check-node uptime fair_cluster nagios --sink=do_nothing
$ health_checks check-node check-module -m nv_peer --mod_count=1 fair_cluster nagios --sink=do_nothing
$ health_checks check-node check-dnf-repos cluster_name nagios
```


# check-pci <div id='check-pci'/>

Perform PCI related checks.

1. Check PCI subsystem

 Files: `gcm/health_checks/checks/check_pci.py`

  Example of execution:
```shell
$ health_checks check-pci --help
$ health_checks check-pci --manifest_file=manifest.json fair_cluster nagios --sink=do_nothing
```

# check-blockdev <div id='check-blockdev'/>

Perform block devices related checks.

1. Check block devices

 Files: `gcm/health_checks/checks/check_blockdev.py`

  Example of execution:
```shell
$ health_checks check-blockdev --help
$ health_checks check-blockdev --manifest_file=manifest.json cluster_name nagios --sink=do_nothing
```

# check-ethlink <div id='check-ethlink'/>

Perform node related checks.

1. Check eth links

 Files: `gcm/health_checks/checks/check_ethlink.py`

  Example of execution:
```shell
$ health_checks check-ethlink --help
$ health_checks check-ethlink --manifest_file=manifest.json cluster_name nagios --sink=do_nothing
```

# check-sensors <div id='check-sensors'/>

Invoke `ipmi-sensors` and parse the output for errors.

1. Check ipmi-sensors output
 Files: `gcm/health_checks/checks/check_sensors.py`

  Example of execution:
```shell
$ health_checks check-sensors --help
$ health_checks check-sensors cluster_name nagios --sink=do_nothing
```
