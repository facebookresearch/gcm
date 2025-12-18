# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import os
import subprocess

from typing import IO, Iterable, List, Optional


def _popen(cmd: List[str], stdin: Optional[IO[str]] = None) -> "subprocess.Popen[str]":
    try:
        return subprocess.Popen(
            cmd, text=True, stdin=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
    except FileNotFoundError as e:
        path = os.environ["PATH"]
        raise RuntimeError(
            f"Could not find executable '{cmd[0]}'. Current PATH: {path}"
        ) from e


def _gen_lines(p: subprocess.Popen) -> Iterable[str]:
    with p:
        stdout = p.stdout
        assert stdout is not None, "Stdout should be piped"
        for line in stdout:
            yield line.rstrip("\n")
        try:
            rc = p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill()
            raise
        if rc != 0:
            raise subprocess.CalledProcessError(rc, p.args)


def get_command_output(command: List[str]) -> str:
    """Return the UTF-8 string output from running `command` on the console.

    Raises:
        subprocess.CalledProcessError if the command exited with a non-zero exit code.
    """
    return subprocess.check_output(command, encoding="utf-8")


def run_shell(command: List[str], timeout_secs: int) -> subprocess.CompletedProcess:
    """Return the UTF-8 string output from running `command` on the console."""
    return subprocess.run(
        command,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout_secs,
    )
