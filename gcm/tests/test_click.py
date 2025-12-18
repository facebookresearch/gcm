# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Final, Optional, Sequence, Tuple, Union

import click
import pytest
from click.testing import CliRunner

from gcm.monitoring.click import toml_config_option
from gcm.monitoring.passwd import Passwd
from typeguard import typechecked


def _write_contents(path: Path, contents: str) -> Path:
    with path.open("w") as f:
        f.write(contents)
    return path


FnGetArgs = Callable[[Path, str], Sequence[str]]


def _case_different_config() -> Tuple[FnGetArgs, str]:
    return (
        lambda p, name: [
            "--config",
            str(
                _write_contents(
                    p / "other_config",
                    f"""
                    [{name}]
                    foo = "baz"
                    """,
                )
            ),
        ],
        "baz\nNone\n",
    )


def _case_different_config_with_command_line() -> Tuple[FnGetArgs, str]:
    return (
        lambda p, name: [
            "--config",
            str(
                _write_contents(
                    p / "other_config",
                    f"""
                    [{name}]
                    foo = "baz"
                    """,
                )
            ),
            "--foo",
            "bar",
        ],
        "bar\nNone\n",
    )


def _case_nonexistent_config() -> Tuple[FnGetArgs, str]:
    return (
        lambda p, name: ["--config", str(p / "does_not_exist")],
        "foo default\nNone\n",
    )


class TestTomlConfigOption:
    @staticmethod
    @pytest.mark.parametrize(
        "get_args, expected_stdout",
        [
            # passing no args should use the value in the default config
            ([], "hello, world!\nNone\n"),
            # setting the option at the command line should override the default config
            # value
            (["--foo", "bar"], "bar\nNone\n"),
            # setting a different config path should ignore the default config
            _case_different_config(),
            # setting a different config but setting the option at the command line
            # should still prefer the value passed at the command line
            _case_different_config_with_command_line(),
            # nonexistent config should be ignored and treated as an empty table
            _case_nonexistent_config(),
            # /dev/null is the same as a nonexistent config
            (["--config", "/dev/null"], "foo default\nNone\n"),
        ],
    )
    @typechecked
    def test_uses_correct_value(
        tmp_path: Path,
        get_args: Union[Sequence[str], FnGetArgs],
        expected_stdout: str,
    ) -> None:
        name = "main"
        config_path = _write_contents(
            tmp_path / "config.toml",
            f"""
            [{name}]
            foo = "hello, world!"
            not_an_option = 42

            [not-{name}]
            foo = "oops"
            """,
        )
        runner = CliRunner(mix_stderr=False)
        args = get_args(tmp_path, name) if callable(get_args) else get_args

        @click.command()
        @toml_config_option(name, default_config_path=config_path)
        @click.option("--foo", default="foo default")
        @click.option("--missing-in-config", type=int)
        def main(foo: Optional[str], missing_in_config: Optional[int]) -> None:
            print(foo)
            print(missing_in_config)

        r = runner.invoke(main, args, catch_exceptions=False)

        assert r.exit_code == 0
        assert r.stdout == expected_stdout

    @staticmethod
    @pytest.mark.parametrize(
        "args, expected_stdout",
        [
            ([], "a\nb\nc\n"),
            (["-o", "d", "-o", "e"], "d\ne\n"),
        ],
    )
    @typechecked
    def test_repeated_options_overwrite(
        tmp_path: Path, args: Sequence[str], expected_stdout: str
    ) -> None:
        name = "main"
        config_path = _write_contents(
            tmp_path / "config.toml",
            f"""
            [{name}]
            opts = ["a", "b", "c"]
            """,
        )
        runner = CliRunner(mix_stderr=False)

        @click.command()
        @toml_config_option(name, default_config_path=config_path)
        @click.option("-o", "opts", multiple=True)
        def main(opts: Sequence[str]) -> None:
            for o in opts:
                print(o)

        r = runner.invoke(main, args, catch_exceptions=False)

        assert r.exit_code == 0
        assert r.stdout == expected_stdout

    @staticmethod
    def test_invalid_toml_errors(tmp_path: Path) -> None:
        name = "main"
        config_path = _write_contents(tmp_path / "not_toml", "]] oops")
        runner = CliRunner(mix_stderr=False)
        expected_error_msg = f"{config_path} does not contain valid TOML."

        @click.command()
        @toml_config_option(name, default_config_path="/dev/null")
        @click.option("--foo")
        def main(foo: Optional[str]) -> None:
            print(foo)

        r = runner.invoke(main, ["--config", str(config_path)], catch_exceptions=False)

        assert r.exit_code != 0
        assert r.stdout == ""
        assert expected_error_msg in r.stderr

    @staticmethod
    def test_missing_table_errors(tmp_path: Path) -> None:
        name = "main"
        config_path = _write_contents(
            tmp_path / "config.toml",
            """
            [not-main]
            hello = "world"
            """,
        )
        runner = CliRunner(mix_stderr=False)
        expected_error_msg = f"'{name}' is not a top-level table name in {config_path}. Valid names: ['not-main']"

        @click.command()
        @toml_config_option(name, default_config_path=config_path)
        @click.option("--foo")
        def main(foo: Optional[str]) -> None:
            print(foo)

        r = runner.invoke(main, catch_exceptions=False)

        assert r.exit_code != 0
        assert r.stdout == ""
        assert expected_error_msg in r.stderr

    @staticmethod
    def test_defaults_are_merged(tmp_path: Path) -> None:
        name = "main"
        config_path = _write_contents(
            tmp_path / "config.toml",
            f"""
            [{name}]
            foo = 42
            """,
        )
        runner = CliRunner(mix_stderr=False)

        @click.command(context_settings={"default_map": {"bar": 100}})
        @toml_config_option(name, default_config_path=config_path)
        @click.option("--foo", type=int)
        @click.option("--bar", type=int)
        def main(foo: Optional[int], bar: Optional[int]) -> None:
            print(foo)
            print(bar)

        r = runner.invoke(main, catch_exceptions=False)

        assert r.exit_code == 0
        assert r.stdout == "42\n100\n"

    @staticmethod
    def test_config_propagates_to_subcommands(tmp_path: Path) -> None:
        name = "parent"
        config_path = _write_contents(
            tmp_path / "config.toml",
            f"""
            [{name}]
            foo = 42

            [{name}.child]
            bar = "hello"

            [{name}.child.grandchild]
            baz = false
            """,
        )
        runner = CliRunner(mix_stderr=False)

        @click.group()
        @toml_config_option(name, default_config_path=config_path)
        @click.option("--foo")
        def parent(foo: int) -> None:
            print(foo)

        @parent.group()
        @click.option("--bar", default="goodbye")
        def child(bar: Optional[str]) -> None:
            print(bar)

        @child.command()
        @click.option("--baz/--no-baz")
        def grandchild(baz: bool) -> None:
            print(baz)

        r = runner.invoke(parent, ["child", "grandchild"], catch_exceptions=False)

        assert r.exit_code == 0
        assert r.stdout == "42\nhello\nFalse\n"

    @staticmethod
    def test_subcommand_default_map_stops_propagation(tmp_path: Path) -> None:
        name = "parent"
        config_path = _write_contents(
            tmp_path / "config.toml",
            f"""
            [{name}]
            foo = 42

            [{name}.child]
            bar = "hello"

            [{name}.child.grandchild]
            baz = true
            """,
        )
        runner = CliRunner(mix_stderr=False)

        @click.group()
        @toml_config_option(name, default_config_path=config_path)
        @click.option("--foo")
        def parent(foo: int) -> None:
            print(foo)

        @parent.group(context_settings={"default_map": {"bar": "goodbye"}})
        @click.option("--bar")
        def child(bar: Optional[str]) -> None:
            print(bar)

        @child.command()
        @click.option("--baz/--no-baz")
        def grandchild(baz: bool) -> None:
            print(baz)

        r = runner.invoke(parent, ["child", "grandchild"], catch_exceptions=False)

        assert r.exit_code == 0
        assert r.stdout == "42\ngoodbye\nFalse\n"

    @staticmethod
    def test_positional_args_cannot_be_configured(tmp_path: Path) -> None:
        name = "main"
        config_path = _write_contents(
            tmp_path / "config.toml",
            f"""
            [{name}]
            arg = "foo"
            """,
        )
        runner = CliRunner(mix_stderr=False)

        @click.command()
        @toml_config_option(name, default_config_path=config_path)
        @click.argument("arg")
        def main(arg: str) -> None:
            print(arg)

        r1 = runner.invoke(main, [], catch_exceptions=False)
        r2 = runner.invoke(main, ["hello"], catch_exceptions=False)

        assert r1.exit_code != 0
        assert r1.stdout == ""
        assert r2.exit_code == 0
        assert r2.stdout == "hello\n"


_TEST_UID: Final = 42


@dataclass
class StubPasswd:
    pw_name: str = "test"
    pw_passwd: str = "password"
    pw_uid: int = _TEST_UID
    pw_gid: int = 1
    pw_gecos: str = ""
    pw_dir: str = ""
    pw_shell: str = ""


@pytest.fixture
def stub_from_uid() -> Callable[[int], Passwd]:
    def from_uid(uid: int) -> Passwd:
        return StubPasswd(pw_uid=uid)

    return from_uid


@pytest.fixture
def stub_from_name() -> Callable[[str], Passwd]:
    def from_name(name: str) -> Passwd:
        return StubPasswd(pw_name=name)

    return from_name
