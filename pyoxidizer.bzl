# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
PYTHON_VERSION = "3.10"
# Keep in sync with download_pyoxidizer_wheels.sh.
PYTHON_DISTRIBUTION_SHA256 = "ddf27f962f0a13a4ff94d9dd51b55a33e82b97320fddfe42ce4ca74a6af1e70a"

def make_python_distribution():
    python_distribution = VARS.get("PYTHON_DISTRIBUTION")
    if python_distribution:
        return PythonDistribution(
            sha256 = PYTHON_DISTRIBUTION_SHA256,
            local_path = python_distribution,
            flavor = "standalone",
        )

    return default_python_distribution(python_version = PYTHON_VERSION)

def make_gcm():
    dist = make_python_distribution()
    version = VARS.get("VERSION")
    export_vars = "import os; os.environ['GCM_VERSION'] = '" + version + "';"

    policy = dist.make_python_packaging_policy()
    policy.resources_location_fallback = "filesystem-relative:gcm_lib"

    python_config = dist.make_python_interpreter_config()
    # Avoid PyOxidizer's jemalloc Cargo feature so the offline vendor set stays minimal.
    python_config.allocator_backend = "default"
    python_config.run_command = export_vars + "from gcm.monitoring.cli.gcm import main; main()"

    # Set initial value for `sys.path`. If the string `$ORIGIN` exists in
    # a value, it will be expanded to the directory of the built executable.
    python_config.module_search_paths = ["$ORIGIN/gcm_lib"]
    exe = dist.to_python_executable(
        name = "gcm",
        packaging_policy = policy,
        config = python_config,
    )

    exe.add_python_resources(exe.pip_install(["-r", "requirements.txt"]))
    exe.add_python_resources(exe.pip_install(["--no-deps", CWD]))

    return exe

def make_health_checks():
    dist = make_python_distribution()
    version = VARS.get("VERSION")
    export_vars = "import os; os.environ['GCM_VERSION'] = '" + version + "';"

    policy = dist.make_python_packaging_policy()

    # Attempt to add resources relative to the built binary when
    # `resources_location` fails.
    policy.resources_location_fallback = "filesystem-relative:hc_lib"

    python_config = dist.make_python_interpreter_config()
    # Avoid PyOxidizer's jemalloc Cargo feature so the offline vendor set stays minimal.
    python_config.allocator_backend = "default"
    python_config.run_command = export_vars + "from gcm.health_checks.cli.health_checks import health_checks; health_checks()"

    # Set initial value for `sys.path`. If the string `$ORIGIN` exists in
    # a value, it will be expanded to the directory of the built executable.
    python_config.module_search_paths = ["$ORIGIN/hc_lib"]
    exe = dist.to_python_executable(
        name = "health_checks",
        packaging_policy = policy,
        config = python_config,
    )

    exe.add_python_resources(exe.pip_install(["-r", "requirements.txt"]))
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
