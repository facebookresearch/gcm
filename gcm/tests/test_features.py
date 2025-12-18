# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from pathlib import Path
from typing import Generator

import click
import pytest
from click.testing import CliRunner

from gcm.monitoring.click import feature_flags_config
from gcm.monitoring.features.gen.generated_features_healthchecksfeatures import (
    FeatureValueHealthChecksFeatures,
)
from gcm.monitoring.features.gen.generated_features_testingfeatures import (
    FeatureValueTestingFeatures,
)
from typeguard import typechecked


@pytest.fixture(scope="module", autouse=True)
def cleanup_config_path() -> Generator[None, None, None]:
    yield
    FeatureValueHealthChecksFeatures.config_path = None


def _write_to_file(path: Path, data: str) -> Path:
    with path.open("w") as f:
        f.write(data)
    return path


@typechecked
def test_read_existing_features(tmp_path: Path) -> None:
    runner = CliRunner(mix_stderr=False)
    config_path = _write_to_file(
        tmp_path / "features.toml",
        """
        [TestingFeatures]
        flag1 = true
        flag2 = false
        constant1 = 1
        constant2 = 5
        """,
    )

    @click.command()
    @feature_flags_config(FeatureValueTestingFeatures)
    def main() -> None:
        ff = FeatureValueTestingFeatures()
        print(ff.get_testingfeatures_flag1())
        print(ff.get_testingfeatures_flag2())
        print(ff.get_testingfeatures_constant1())
        print(ff.get_testingfeatures_constant2())

    result = runner.invoke(
        main, f"--features-config={config_path}", catch_exceptions=False
    )
    assert result.exit_code == 0
    assert result.stdout == "True\nFalse\n1\n5\n"


@typechecked
def test_read_feature_flags_when_category_not_in_toml(tmp_path: Path) -> None:
    runner = CliRunner(mix_stderr=False)
    # If the feature flags category is not present return default values
    config_path = _write_to_file(
        tmp_path / "features.toml",
        """
        [RandomTestingCategogy]
        randomFlag1 = True
        randomConstant1 = 1
        """,
    )

    @click.command()
    @feature_flags_config(FeatureValueTestingFeatures)
    def main() -> None:
        ff = FeatureValueTestingFeatures()
        # It should print the default values for bool (False) and int (-1)
        print(ff.get_testingfeatures_flag1())
        print(ff.get_testingfeatures_constant1())

    result = runner.invoke(
        main, f"--features-config={config_path}", catch_exceptions=False
    )
    assert result.exit_code == 0
    assert result.stdout == "False\n-1\n"


@typechecked
def test_wrong_file_path_throws() -> None:
    config_path = "wrongPath"
    runner = CliRunner(mix_stderr=False)

    @click.command()
    @feature_flags_config(FeatureValueTestingFeatures)
    def main() -> None:
        ff = FeatureValueTestingFeatures()
        print(ff.get_testingfeatures_flag1())

    with pytest.raises(FileNotFoundError):
        runner.invoke(main, f"--features-config={config_path}", catch_exceptions=False)


@typechecked
def test_no_file_path_returns_default() -> None:
    runner = CliRunner(mix_stderr=False)

    @click.command()
    @feature_flags_config(FeatureValueTestingFeatures)
    def main() -> None:
        ff = FeatureValueTestingFeatures()
        print(ff.get_testingfeatures_flag1())

    result = runner.invoke(main, catch_exceptions=False)
    assert result.exit_code == 0
    assert result.stdout == "False\n"


@typechecked
def test_wrong_toml_format_throws(tmp_path: Path) -> None:
    runner = CliRunner(mix_stderr=False)
    config_path = _write_to_file(
        tmp_path / "features.toml",
        """
        [TestingFeatures]
        flag1 = "NotABool"
        flag2 = false
        """,
    )

    @click.command()
    @feature_flags_config(FeatureValueTestingFeatures)
    def main() -> None:
        ff = FeatureValueTestingFeatures()
        print(ff.get_testingfeatures_flag1())

    with pytest.raises(TypeError):
        runner.invoke(main, f"--features-config={config_path}", catch_exceptions=False)
