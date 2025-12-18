# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import subprocess
from dataclasses import dataclass
from typing import Dict, List, Optional, Protocol


class ShellCommandOut(Protocol):
    args: List[str]
    returncode: int
    stdout: str
    stderr: str

    def check_returncode(self) -> None: ...


@dataclass
class PipedShellCommandOut:
    returncode: List[int]
    stdout: str


def handle_subprocess_exception(exc: Exception) -> ShellCommandOut:
    if isinstance(exc, subprocess.TimeoutExpired):
        return subprocess.CompletedProcess(
            args=[exc.cmd],
            returncode=128,
            stdout="Error command timeout because of timeout setting.\n",
        )
    else:
        return subprocess.CompletedProcess(
            args=[],
            returncode=2,
            stdout="Error: Unknown subprocess exception was raised.\n",
        )


def piped_shell_command(cmd: List[str], timeout_secs: int) -> PipedShellCommandOut:
    """
    Run multiple commands in shell piping the output of one command as input to the next.
    Return the output of the last command as a string and the exit codes of all commands.
    """
    returncode: List[int] = []
    out = ""
    if len(cmd) > 0:
        process: Dict[int, subprocess.Popen] = {}
        for index, command in enumerate(cmd):
            if index == 0:
                process[index] = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    shell=True,
                    encoding="utf-8",
                )
            else:
                process[index] = subprocess.Popen(
                    command,
                    stdin=process[index - 1].stdout,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    shell=True,
                    encoding="utf-8",
                )

        out = process[len(process) - 1].communicate(timeout=timeout_secs)[0]
        for index in range(len(process)):
            returncode.append(process[index].wait())

    return PipedShellCommandOut(returncode, out)


def shell_command(
    cmd: str,
    timeout_secs: Optional[int] = None,
    input: Optional[str] = None,
) -> subprocess.CompletedProcess:
    """
    Run a command in shell and return the output as a string.

    Optionally pass an input string to the command's stdin pipe.
    """
    try:
        return subprocess.run(
            cmd,
            shell=True,
            encoding="utf-8",
            input=input,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout_secs,
        )
    except subprocess.TimeoutExpired as e:
        raise subprocess.TimeoutExpired(e.cmd, e.timeout, e.output, e.stderr)
