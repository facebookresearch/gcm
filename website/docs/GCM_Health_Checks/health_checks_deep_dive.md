---
sidebar_position: 5
---

# Deep dive into Health Checks code

All the Health Checks share some boiler plate code. In this section we'll go through some of the Health Checks code and annotate with comments the functionality of each piece of code.
Starting from  [`gcm/health_checks/cli/health_checks.py`](https://github.com/facebookresearch/gcm/blob/main/gcm/health_checks/cli/health_checks.py).
```python
@click.group() # <-- defines a new group of commands
@toml_config_option("health_checks", default_config_path=DEFAULT_CONFIG_PATH) # <-- common --config option to pass to health_checks command for defining parameters for the checks.
@click.version_option(__version__) # <-- version of the package. Invoked as: health_checks --version
def health_checks() -> None:
    """GPU Cluster Monitoring: Large-Scale AI Research Cluster Monitoring."""
```
This is the main `group()` that will include all of our commands. In `click` a `group()` can contain other `@click.commands`, and can also include another `group()` that has its own commands, creating a tree hierarchy of commands and subcommands.

All checks live in [gcm/health_checks/checks/](https://github.com/facebookresearch/gcm/tree/main/gcm/health_checks/checks) folder.
The [gcm/health_checks/](https://github.com/facebookresearch/gcm/tree/main/gcm/health_checks) folder also contains other helper files such as [`gcm/health_checks/click.py`](https://github.com/facebookresearch/gcm/blob/main/gcm/health_checks/click.py) that defines our click related parameters and decorators.

Let's take the example of a single check to analyze. We'll analyze [check_storage.py](https://github.com/facebookresearch/gcm/blob/main/gcm/health_checks/checks/check_storage.py), and its `disk_usage()` command since it is also part of a subcommand group, but any check follows similar concepts.

### Health-Check boiler plate code
In this code we see the following snippet:
```python
@click.group() # <-- This defines a new group of commands that we add in health_checks. If a new group() is not needed one can directly create a new command to add to health checks as: @click.command() instead of @click.group()
def check_storage() -> None:
    """storage based checks. i.e. disk space, mounted folders"""
```
Then later in the code we see the following code snippet for the check:
```python
@check_storage.command() # <-- Says that this is a command of the check_storage group()
@common_arguments # <-- common arguments that we use in all checks
@timeout_argument # <-- another argument decorator if the check needs a timeout argument. This argument is used when the check calls a system command through the subprocess.py functions, so that it won't hang indefinitely.
@telemetry_argument # <-- Common argument that is used for the telemetry of the checks
@click.option( # <-- This is an example of a check specific argument
    "--volume",
    "-v",
    type=click.Path(file_okay=False, readable=False),
    help="Volumes to check for free space",
    multiple=True,
    required=True,
)
... # <-- Other check specific arguments can be defined here
@click.pass_obj # <-- Passes a context object to the check. This is used for object injection during unit testing.
@typechecked
def disk_usage(
    obj: Optional[StorageCheck], # <-- obj from @click.pass_obj
    cluster: str, # <-- parameter from @common_arguments
    type: CHECK_TYPE, # <-- parameter from @common_arguments
    log_level: LOG_LEVEL, # <-- parameter from @common_arguments
    log_folder: str, # <-- parameter from @common_arguments
    timeout: int, # <-- parameter from @timeout_argument
    sink: str, # <-- parameter from @telemetry_argument
    sink_opts: Collection[str], # <-- parameter from @telemetry_argument
    volume: Tuple[str, ...], # <-- check specific parameter
    ... # <-- Other check specific parameters can be included here. These should match the decorators of the method

) -> None:
    """Check the free space on the specified volumes"""
```
The `@common_arguments, @telemetry_argument` decorators that we see here are common across all the checks.
Similarly, `@timeout_argument` is used from many checks that invoke system commands.
There are two options for system commands in [subprocess.py](https://github.com/facebookresearch/gcm/blob/main/gcm/health_checks/subprocess.py). `shell_command()` that executes a single command, and `piped_shell_command()` that executes piped commands.


This is how the boiler plate of the check is defined. Let's check the implementation of the same check.
The next code snippet shows the beginning of the check. This boiler plate code is also similar across all the different checks.
```python
    node: str = socket.gethostname() # <-- get the node's name
    logger, _ = init_logger( # <-- initialize the logger
        logger_name=type,
        log_dir=log_folder,
        log_name=node,
        log_level=getattr(logging, log_level),
    )
    logger.info(
        f"check-storage disk-usage: cluster: {cluster}, node: {node}, type: {type}, volumes: {volume}, critical threshold: {usage_critical_threshold}, warning threshold: {usage_warning_threshold}, inode-check: {inode_check}."
    )
    if obj is None: # <-- during normal invocation this is None. It is not None when called from our unit tests.
        obj = StorageCheckImpl(cluster, type, log_level, log_folder)

    overall_exit_code = ExitCode.UNKNOW # <-- initialize the exit code and messages to be returned
    overall_msg = ""
```

After that the implementation of the check starts. We wrap the implementation inside two context managers as:
```python
    with ExitStack() as s:
        s.enter_context(
            TelemetryContext( # <-- This context is for writing the result of the check to Scuba tables
                sink,
                sink_opts,
                logger,
                cluster,
                type,
                HealthCheckName.DISK_USAGE.value, # <-- Specify the check name here. Changes per check.
                node,
                lambda: (overall_exit_code, overall_msg),
            )
        )
        s.enter_context( # <-- This context is for printing to stdout the result of the check
            OutputContext(
                type,
                HealthCheckName.DISK_USAGE,
                lambda: (overall_exit_code, overall_msg),
            )
        )
        ff = FeatureValueHealthChecksFeatures() # <-- Add a killswitch
        if ff.get_healthchecksfeatures_disable_disk_usage():
            exit_code = ExitCode.OK
            msg = f"{HealthCheckName.DISK_USAGE.value} is disabled by killswitch."
            logger.info(msg)
            sys.exit(exit_code.value)
        ...
        ... # Execute the check specific operations here!!!
        ...
        sys.exit(overall_exit_code.value) # Finally exit with the result of the check.
```

Every check implementation has similar steps as outlined above. To test the functionality of each check we execute 2 steps:
1. Run the check on the cluster to make sure it works as expected. Check log files for its execution.
2. Implement unit tests to capture its behavior. Unit tests for the killswitches are in [gcm/tests/health_checks_tests/test_killswitches.py](https://github.com/facebookresearch/gcm/blob/main/gcm/tests/health_checks_tests/test_killswitches.py)

Using the same check as an example for the unit test, we can check file [gcm/tests/health_checks_tests/test_check_storage.py](https://github.com/facebookresearch/gcm/blob/main/gcm/tests/health_checks_tests/test_check_storage.py).
This file contains the unit tests for this specific check.

Our tests are invoked through pytest. Their implementation doesn't have anything out of the ordinary.
Two things to note here are:
1. Invocation of the click command
2. Injecting an object for mimicking the behavior of different check commands

For instance:
```python
@dataclass
class FakeCheckDiskStorageImpl: # <-- Define a fake object that implements the StorageCheck protocol like the check
    disk_usage: ShellCommandOut

    cluster = "test cluster" # <-- parameter needed by the protocol
    type = "prolog" # <-- parameter needed by the protocol
    log_level = "INFO" # <-- parameter needed by the protocol
    log_folder = "/tmp" # <-- parameter needed by the protocol

    def get_disk_usage( # <-- function needed by the protocol
        self, timeout_secs: int, volume: str, logger: logging.Logger
    ) -> ShellCommandOut:
        return self.disk_usage

    def get_mount_status( # <-- function needed by the protocol
        self, timeout_secs: int, dir: str, logger: logging.Logger
    ) -> PipedShellCommandOut:
        return PipedShellCommandOut([0, 0], "dummy output")
```

Next, when the check is invoked we use this object to inject it in the check:
```python
def test_disk_usage(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    disk_usage_tester: FakeCheckDiskStorageImpl, # <-- The fake object we created
    expected: Tuple[ExitCode, str],
) -> None:
    runner = CliRunner(mix_stderr=False) # <-- Used to call our click CLI
    caplog.at_level(logging.INFO)

    result = runner.invoke( # <-- Invoke the click command and pass the object
        check_storage,
        f"disk-usage fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing -v /randomFolder --usage-critical-threshold=85 --usage-warning-threshold=80",
        obj=disk_usage_tester,
    )
```
