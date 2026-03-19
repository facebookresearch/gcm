# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Tests for the create_new_health_check scaffold tool."""

import importlib.util
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Load the scaffold module from bin/ via importlib so we can test its
# individual functions without making it a package.
# ---------------------------------------------------------------------------

_BIN_SCRIPT = (
    Path(__file__).resolve().parent.parent.parent / "bin" / "create_new_health_check.py"
)

spec = importlib.util.spec_from_file_location(
    "create_new_health_check", str(_BIN_SCRIPT)
)
assert spec is not None, f"Could not load spec from {_BIN_SCRIPT}"
assert spec.loader is not None, "spec.loader is None"
scaffold: Any = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scaffold)

# ---------------------------------------------------------------------------
# Fixture: replicate the relevant project directories under tmp_path and
# redirect scaffold.PROJECT_ROOT there so no real files are touched.
# ---------------------------------------------------------------------------

_REAL_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.fixture
def scaffold_env(tmp_path: Path) -> Iterator[Path]:
    """Set up temp directory with copies of files the scaffold modifies."""
    # Mirror required directory structure
    checks_dir = tmp_path / "gcm" / "health_checks" / "checks"
    checks_dir.mkdir(parents=True)
    cli_dir = tmp_path / "gcm" / "health_checks" / "cli"
    cli_dir.mkdir(parents=True)
    schema_dir = tmp_path / "gcm" / "schemas" / "health_check"
    schema_dir.mkdir(parents=True)
    features_dir = tmp_path / "gcm" / "monitoring" / "features" / "feature_definitions"
    features_dir.mkdir(parents=True)
    tests_dir = tmp_path / "gcm" / "tests" / "health_checks_tests"
    tests_dir.mkdir(parents=True)
    docs_dir = tmp_path / "website" / "docs" / "GCM_Health_Checks" / "health_checks"
    docs_dir.mkdir(parents=True)

    # Copy real source files that the scaffold modifies
    shutil.copy(_REAL_ROOT / "gcm/health_checks/checks/__init__.py", checks_dir)
    shutil.copy(_REAL_ROOT / "gcm/health_checks/cli/health_checks.py", cli_dir)
    shutil.copy(
        _REAL_ROOT / "gcm/schemas/health_check/health_check_name.py", schema_dir
    )
    shutil.copy(
        _REAL_ROOT
        / "gcm/monitoring/features/feature_definitions/health_checks_features.py",
        features_dir,
    )

    # Redirect scaffold to temp root
    original_root = scaffold.PROJECT_ROOT
    scaffold.PROJECT_ROOT = tmp_path
    yield tmp_path
    scaffold.PROJECT_ROOT = original_root


# ---------------------------------------------------------------------------
# Name validation
# ---------------------------------------------------------------------------


def test_validate_name_valid() -> None:
    """A correctly prefixed lowercase name is accepted and returned as-is."""
    assert scaffold.validate_name("check_ntp_sync") == "check_ntp_sync"


@pytest.mark.parametrize(
    "bad_name",
    [
        "Check_ntp_sync",  # uppercase first letter
        "CHECK_NTP_SYNC",  # all uppercase
        "ntp_sync",  # missing check_ prefix
        "check_Ntp_Sync",  # mixed case after prefix
        "check ntp sync",  # spaces
        "check_",  # nothing after prefix
        "",  # empty string
    ],
)
def test_validate_name_invalid(bad_name: str) -> None:
    """Invalid names raise ValueError."""
    with pytest.raises(ValueError, match="is not a valid check name"):
        scaffold.validate_name(bad_name)


# ---------------------------------------------------------------------------
# PascalCase conversion
# ---------------------------------------------------------------------------


def test_to_pascal_case_multi_word() -> None:
    """Multi-word snake_case is converted to PascalCase."""
    assert scaffold.to_pascal_case("ntp_sync") == "NtpSync"


def test_to_pascal_case_single_word() -> None:
    """A single word is capitalised."""
    assert scaffold.to_pascal_case("sensors") == "Sensors"


# ---------------------------------------------------------------------------
# create_check_file — simple (command) variant
# ---------------------------------------------------------------------------


def test_create_check_file(scaffold_env: Path) -> None:
    """Scaffold creates the check file with expected content."""
    scaffold.create_check_file("check_ntp_sync", group=False, dry_run=False)

    dest = scaffold_env / "gcm" / "health_checks" / "checks" / "check_ntp_sync.py"
    assert dest.exists(), "Check file was not created"

    content = dest.read_text()
    assert "HealthCheckRuntime" in content
    assert "@click.command()" in content
    assert "check_ntp_sync" in content
    assert "NtpSync" in content
    # Verify HealthCheckRuntime kwargs match the dataclass fields
    assert "check_type=type," in content
    assert "health_check_name=HealthCheckName.CHECK_NTP_SYNC," in content
    assert "killswitch_getter=lambda:" in content
    assert ".get_healthchecksfeatures_disable_check_ntp_sync()" in content
    # Generated file must be valid Python
    compile(content, str(dest), "exec")


# ---------------------------------------------------------------------------
# create_check_file — group variant
# ---------------------------------------------------------------------------


def test_create_check_file_group(scaffold_env: Path) -> None:
    """With group=True the scaffold emits a @click.group() instead."""
    scaffold.create_check_file("check_ntp_sync", group=True, dry_run=False)

    dest = scaffold_env / "gcm" / "health_checks" / "checks" / "check_ntp_sync.py"
    content = dest.read_text()
    assert "@click.group()" in content
    assert "@click.command()" not in content
    assert "@check_ntp_sync.command()" in content
    # Verify HealthCheckRuntime kwargs in the subcommand use subcommand-level entries
    assert "check_type=type," in content
    assert (
        "health_check_name=HealthCheckName.CHECK_NTP_SYNC_EXAMPLE_SUBCOMMAND,"
        in content
    )
    assert (
        ".get_healthchecksfeatures_disable_check_ntp_sync_example_subcommand()"
        in content
    )
    compile(content, str(dest), "exec")


# ---------------------------------------------------------------------------
# create_test_file
# ---------------------------------------------------------------------------


def test_create_test_file(scaffold_env: Path) -> None:
    """Scaffold creates the test file with expected content."""
    scaffold.create_test_file("check_ntp_sync", group=False, dry_run=False)

    dest = (
        scaffold_env
        / "gcm"
        / "tests"
        / "health_checks_tests"
        / "test_check_ntp_sync.py"
    )
    assert dest.exists(), "Test file was not created"

    content = dest.read_text()
    assert "FakeNtpSyncCheckImpl" in content
    assert "def test_check_ntp_sync(" in content
    # Verify f-string interpolation: should be {tmp_path}, not {{tmp_path}}
    assert "{tmp_path}" in content
    assert "{{tmp_path}}" not in content
    # Generated file must be valid Python
    compile(content, str(dest), "exec")


def test_create_test_file_group(scaffold_env: Path) -> None:
    """Group mode generates a test that invokes the subcommand, not the group."""
    scaffold.create_test_file("check_ntp_sync", group=True, dry_run=False)

    dest = (
        scaffold_env
        / "gcm"
        / "tests"
        / "health_checks_tests"
        / "test_check_ntp_sync.py"
    )
    assert dest.exists(), "Test file was not created"

    content = dest.read_text()
    assert "FakeNtpSyncCheckImpl" in content
    # Must import and test the subcommand, not the group
    assert "import example_subcommand" in content
    assert "def test_example_subcommand(" in content
    assert "{{tmp_path}}" not in content
    compile(content, str(dest), "exec")


# ---------------------------------------------------------------------------
# create_doc_file
# ---------------------------------------------------------------------------


def test_create_doc_file(scaffold_env: Path) -> None:
    """Scaffold creates the doc file with expected content."""
    scaffold.create_doc_file("check_ntp_sync", group=False, dry_run=False)

    dest = (
        scaffold_env
        / "website"
        / "docs"
        / "GCM_Health_Checks"
        / "health_checks"
        / "check-ntp-sync.md"
    )
    assert dest.exists(), "Doc file was not created"

    content = dest.read_text()
    assert "check-ntp-sync" in content


def test_create_doc_file_group(scaffold_env: Path) -> None:
    """Group mode creates a directory with README.md and subcommand doc."""
    scaffold.create_doc_file("check_ntp_sync", group=True, dry_run=False)

    doc_dir = (
        scaffold_env
        / "website"
        / "docs"
        / "GCM_Health_Checks"
        / "health_checks"
        / "check-ntp-sync"
    )
    assert doc_dir.is_dir(), "Doc directory was not created"

    readme = doc_dir / "README.md"
    assert readme.exists(), "README.md was not created"
    readme_content = readme.read_text()
    assert "## Subcommands" in readme_content
    assert "example-subcommand" in readme_content

    subcmd_doc = doc_dir / "example-subcommand.md"
    assert subcmd_doc.exists(), "Subcommand doc was not created"
    subcmd_content = subcmd_doc.read_text()
    assert "## Command-Line Options" in subcmd_content
    assert "check-ntp-sync" in subcmd_content


# ---------------------------------------------------------------------------
# Idempotency — calling create helpers twice skips gracefully
# ---------------------------------------------------------------------------


def test_create_files_idempotent(
    scaffold_env: Path, capsys: pytest.CaptureFixture
) -> None:
    """Running the file-creation helpers twice does not raise and prints skip."""
    scaffold.create_check_file("check_ntp_sync", group=False, dry_run=False)
    scaffold.create_test_file("check_ntp_sync", group=False, dry_run=False)
    scaffold.create_doc_file("check_ntp_sync", group=False, dry_run=False)

    # Second call — must not raise
    scaffold.create_check_file("check_ntp_sync", group=False, dry_run=False)
    scaffold.create_test_file("check_ntp_sync", group=False, dry_run=False)
    scaffold.create_doc_file("check_ntp_sync", group=False, dry_run=False)

    captured = capsys.readouterr()
    assert "Skipping" in captured.out


# ---------------------------------------------------------------------------
# Dry-run — no files must be created or modified
# ---------------------------------------------------------------------------


def test_dry_run_no_changes(scaffold_env: Path, capsys: pytest.CaptureFixture) -> None:
    """dry_run=True must not create or modify any files."""
    check_dest = scaffold_env / "gcm" / "health_checks" / "checks" / "check_ntp_sync.py"
    test_dest = (
        scaffold_env
        / "gcm"
        / "tests"
        / "health_checks_tests"
        / "test_check_ntp_sync.py"
    )
    doc_dest = (
        scaffold_env
        / "website"
        / "docs"
        / "GCM_Health_Checks"
        / "health_checks"
        / "check-ntp-sync.md"
    )

    init_before = (
        scaffold_env / "gcm" / "health_checks" / "checks" / "__init__.py"
    ).read_text()
    cli_before = (
        scaffold_env / "gcm" / "health_checks" / "cli" / "health_checks.py"
    ).read_text()
    enum_before = (
        scaffold_env / "gcm" / "schemas" / "health_check" / "health_check_name.py"
    ).read_text()
    features_before = (
        scaffold_env
        / "gcm"
        / "monitoring"
        / "features"
        / "feature_definitions"
        / "health_checks_features.py"
    ).read_text()

    scaffold.create_check_file("check_ntp_sync", group=False, dry_run=True)
    scaffold.create_test_file("check_ntp_sync", group=False, dry_run=True)
    scaffold.create_doc_file("check_ntp_sync", group=False, dry_run=True)
    scaffold.update_init("check_ntp_sync", dry_run=True)
    scaffold.update_cli("check_ntp_sync", dry_run=True)
    scaffold.update_enum("check_ntp_sync", dry_run=True)
    scaffold.update_features("check_ntp_sync", dry_run=True)

    # No new files
    assert not check_dest.exists()
    assert not test_dest.exists()
    assert not doc_dest.exists()

    # Existing files unchanged
    assert (
        scaffold_env / "gcm" / "health_checks" / "checks" / "__init__.py"
    ).read_text() == init_before
    assert (
        scaffold_env / "gcm" / "health_checks" / "cli" / "health_checks.py"
    ).read_text() == cli_before
    assert (
        scaffold_env / "gcm" / "schemas" / "health_check" / "health_check_name.py"
    ).read_text() == enum_before
    assert (
        scaffold_env
        / "gcm"
        / "monitoring"
        / "features"
        / "feature_definitions"
        / "health_checks_features.py"
    ).read_text() == features_before

    captured = capsys.readouterr()
    assert "[dry-run]" in captured.out


# ---------------------------------------------------------------------------
# update_init
# ---------------------------------------------------------------------------


def test_update_init(scaffold_env: Path) -> None:
    """update_init adds the import line and __all__ entry in alphabetical order."""
    scaffold.update_init("check_ntp_sync", dry_run=False)

    init_path = scaffold_env / "gcm" / "health_checks" / "checks" / "__init__.py"
    content = init_path.read_text()

    assert (
        "from gcm.health_checks.checks.check_ntp_sync import check_ntp_sync" in content
    )
    assert '"check_ntp_sync"' in content

    # Verify import is in alphabetical position: check_ntp_sync should come
    # after check_node and before check_nvidia_smi.
    node_pos = content.find("from gcm.health_checks.checks.check_node")
    ntp_pos = content.find("from gcm.health_checks.checks.check_ntp_sync")
    nvidia_pos = content.find("from gcm.health_checks.checks.check_nvidia_smi")
    assert node_pos < ntp_pos < nvidia_pos


def test_update_init_first_position(scaffold_env: Path) -> None:
    """update_init inserts alphabetically before the first existing import."""
    scaffold.update_init("check_aaa", dry_run=False)

    init_path = scaffold_env / "gcm" / "health_checks" / "checks" / "__init__.py"
    content = init_path.read_text()

    aaa_pos = content.find("from gcm.health_checks.checks.check_aaa")
    airstore_pos = content.find("from gcm.health_checks.checks.check_airstore")
    assert aaa_pos < airstore_pos


def test_update_init_last_position(scaffold_env: Path) -> None:
    """update_init inserts alphabetically after the last existing import."""
    scaffold.update_init("check_zzz", dry_run=False)

    init_path = scaffold_env / "gcm" / "health_checks" / "checks" / "__init__.py"
    content = init_path.read_text()

    telemetry_pos = content.find("from gcm.health_checks.checks.check_telemetry")
    zzz_pos = content.find("from gcm.health_checks.checks.check_zzz")
    assert telemetry_pos < zzz_pos


def test_update_init_idempotent(scaffold_env: Path) -> None:
    """Running update_init twice does not duplicate entries."""
    scaffold.update_init("check_ntp_sync", dry_run=False)
    scaffold.update_init("check_ntp_sync", dry_run=False)

    init_path = scaffold_env / "gcm" / "health_checks" / "checks" / "__init__.py"
    content = init_path.read_text()

    # Both import line and __all__ entry must appear exactly once.
    assert (
        content.count(
            "from gcm.health_checks.checks.check_ntp_sync import check_ntp_sync"
        )
        == 1
    )
    assert content.count('"check_ntp_sync"') == 1


# ---------------------------------------------------------------------------
# update_enum
# ---------------------------------------------------------------------------


def test_update_enum(scaffold_env: Path) -> None:
    """update_enum adds the CHECK_NTP_SYNC entry in alphabetical order."""
    scaffold.update_enum("check_ntp_sync", dry_run=False)

    enum_path = (
        scaffold_env / "gcm" / "schemas" / "health_check" / "health_check_name.py"
    )
    content = enum_path.read_text()

    assert 'CHECK_NTP_SYNC = "check ntp sync"' in content

    # Should appear after CHECK_NODE (alphabetically CHECK_NODE < CHECK_NTP_SYNC)
    # but there is no CHECK_NODE in the enum; verify it sorts before CHECK_PCI.
    ntp_pos = content.find("CHECK_NTP_SYNC")
    pci_pos = content.find("CHECK_PCI")
    assert ntp_pos < pci_pos


def test_update_enum_idempotent(scaffold_env: Path) -> None:
    """Running update_enum twice does not duplicate the entry."""
    scaffold.update_enum("check_ntp_sync", dry_run=False)
    scaffold.update_enum("check_ntp_sync", dry_run=False)

    enum_path = (
        scaffold_env / "gcm" / "schemas" / "health_check" / "health_check_name.py"
    )
    content = enum_path.read_text()

    assert content.count("CHECK_NTP_SYNC") == 1


# ---------------------------------------------------------------------------
# update_features
# ---------------------------------------------------------------------------


def test_update_features(scaffold_env: Path) -> None:
    """update_features adds the disable_ field in alphabetical order."""
    scaffold.update_features("check_ntp_sync", dry_run=False)

    features_path = (
        scaffold_env
        / "gcm"
        / "monitoring"
        / "features"
        / "feature_definitions"
        / "health_checks_features.py"
    )
    content = features_path.read_text()

    assert "disable_check_ntp_sync: bool" in content

    # Alphabetically, disable_check_ntp_sync should come after
    # disable_check_nccl (if present) or be in correct relative position.
    # It must appear before disable_check_pci.
    ntp_pos = content.find("disable_check_ntp_sync")
    pci_pos = content.find("disable_check_pci")
    assert ntp_pos < pci_pos


def test_update_features_idempotent(scaffold_env: Path) -> None:
    """Running update_features twice does not duplicate the field."""
    scaffold.update_features("check_ntp_sync", dry_run=False)
    scaffold.update_features("check_ntp_sync", dry_run=False)

    features_path = (
        scaffold_env
        / "gcm"
        / "monitoring"
        / "features"
        / "feature_definitions"
        / "health_checks_features.py"
    )
    content = features_path.read_text()

    assert content.count("disable_check_ntp_sync") == 1


# ---------------------------------------------------------------------------
# update_cli
# ---------------------------------------------------------------------------


def test_update_cli(scaffold_env: Path) -> None:
    """update_cli appends the check entry to list_of_checks."""
    scaffold.update_cli("check_ntp_sync", dry_run=False)

    cli_path = scaffold_env / "gcm" / "health_checks" / "cli" / "health_checks.py"
    content = cli_path.read_text()

    assert "checks.check_ntp_sync," in content


def test_update_cli_idempotent(scaffold_env: Path) -> None:
    """Running update_cli twice does not duplicate the entry."""
    scaffold.update_cli("check_ntp_sync", dry_run=False)
    scaffold.update_cli("check_ntp_sync", dry_run=False)

    cli_path = scaffold_env / "gcm" / "health_checks" / "cli" / "health_checks.py"
    content = cli_path.read_text()

    assert content.count("checks.check_ntp_sync") == 1


def test_update_cli_warns_on_missing_anchor(
    scaffold_env: Path, capsys: pytest.CaptureFixture
) -> None:
    """update_cli warns when the expected anchor string is absent."""
    cli_path = scaffold_env / "gcm" / "health_checks" / "cli" / "health_checks.py"
    # Remove the anchor that update_cli relies on.
    cli_path.write_text("# empty file with no anchor\n")

    scaffold.update_cli("check_ntp_sync", dry_run=False)

    captured = capsys.readouterr()
    assert "Warning" in captured.err
    assert "checks.check_ntp_sync" not in cli_path.read_text()
