# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
PYTHON_VERSION = "3.10"

def make_gcm():
    dist = default_python_distribution(python_version = PYTHON_VERSION)
    version = VARS.get("VERSION")
    export_vars = "import os; os.environ['GCM_VERSION'] = '" + version + "';"

    policy = dist.make_python_packaging_policy()
    policy.resources_location_fallback = "filesystem-relative:gcm_lib"

    python_config = dist.make_python_interpreter_config()
    python_config.run_command = export_vars + "from gcm.monitoring.cli.gcm import main; main()"

    # Set initial value for `sys.path`. If the string `$ORIGIN` exists in
    # a value, it will be expanded to the directory of the built executable.
    python_config.module_search_paths = ["$ORIGIN/gcm_lib"]
    exe = dist.to_python_executable(
        name = "gcm",
        packaging_policy = policy,
        config = python_config,
    )

    # NOTE: `--no-binary pydantic` because pyoxidizer has trouble with Cython modules
    # https://pyoxidizer.readthedocs.io/en/stable/pyoxidizer_packaging_extension_modules.html#known-incompatibility-with-cython
    # and Pydantic uses Cython https://github.com/pydantic/pydantic/blob/585ec35bd74ff81f0e482c6d484670bca11f7829/docs/install.md#performance-vs-package-size-trade-off
    # We don't care *that* much about performance so avoiding compiled modules is the easiest workaround.
    # TODO (T139437042): It seems like Pydantic v2 won't be using Cython anymore so when it's released we should revisit whether
    # this flag is still necessary
    exe.add_python_resources(exe.pip_install(["--no-binary", "pydantic", "-r", "requirements.txt"]))
    exe.add_python_resources(exe.pip_install(["--no-deps", CWD]))

    return exe

def make_health_checks():
    dist = default_python_distribution(python_version = PYTHON_VERSION)
    version = VARS.get("VERSION")
    export_vars = "import os; os.environ['GCM_VERSION'] = '" + version + "';"

    policy = dist.make_python_packaging_policy()

    # Attempt to add resources relative to the built binary when
    # `resources_location` fails.
    policy.resources_location_fallback = "filesystem-relative:hc_lib"

    python_config = dist.make_python_interpreter_config()
    python_config.run_command = export_vars + "from gcm.health_checks.cli.health_checks import health_checks; health_checks()"

    # Set initial value for `sys.path`. If the string `$ORIGIN` exists in
    # a value, it will be expanded to the directory of the built executable.
    python_config.module_search_paths = ["$ORIGIN/hc_lib"]
    exe = dist.to_python_executable(
        name = "health_checks",
        packaging_policy = policy,
        config = python_config,
    )

    # NOTE: `--no-binary pydantic` because pyoxidizer has trouble with Cython modules
    # https://pyoxidizer.readthedocs.io/en/stable/pyoxidizer_packaging_extension_modules.html#known-incompatibility-with-cython
    # and Pydantic uses Cython https://github.com/pydantic/pydantic/blob/585ec35bd74ff81f0e482c6d484670bca11f7829/docs/install.md#performance-vs-package-size-trade-off
    # We don't care *that* much about performance so avoiding compiled modules is the easiest workaround.
    # TODO (T139437042): It seems like Pydantic v2 won't be using Cython anymore so when it's released we should revisit whether
    # this flag is still necessary
    exe.add_python_resources(exe.pip_install(["--no-binary", "pydantic", "-r", "requirements.txt"]))
    exe.add_python_resources(exe.pip_install(["--no-deps", CWD]))

    return exe

def make_embedded_resources(exe):
    return exe.to_embedded_resources()

def make_install(exe):
    files = FileManifest()
    files.add_python_resource(".", exe)
    return files

register_target("gcm", make_gcm)
register_target("resources_gcm", make_embedded_resources, depends = ["gcm"], default_build_script = True)
register_target("install_gcm", make_install, depends = ["gcm"], default = True)

register_target("health_checks", make_health_checks)
register_target("resources_hc", make_embedded_resources, depends = ["health_checks"], default_build_script = True)
register_target("install_hc", make_install, depends = ["health_checks"], default = True)

resolve_targets()
