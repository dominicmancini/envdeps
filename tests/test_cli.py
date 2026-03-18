import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pytest

from envdeps.cli import make_parser
from envdeps.common import BaseCommand, ShowCommand

prefix = os.getenv("VIRTUAL_ENV")
assert prefix is not None
if not prefix:
    raise ValueError("No venv prefix.")


@dataclass
class CliCase:
    cmd: Literal["show", "export"]
    argv: list[str]


data = [CliCase("show", ["show", "--target=envdeps", "--format=json", "--verbose"])]


@pytest.fixture
def args():
    test = data[0]
    parser = make_parser()
    ns = BaseCommand()
    args = parser.parse_args(test.argv, ns)
    return args


def test_show(args: BaseCommand):
    cwd = Path.cwd()
    if args.prefix is not None:
        env_prefix = args.prefix
    else:
        env_prefix = Path(prefix)
    cmd = ShowCommand.from_base(args)
    assert cmd.root == cwd, f"Root not resolved to CWD: {cmd.root}"
    assert cmd.prefix.samefile(env_prefix), "Args.prefix not same as current prefix"
    assert cmd.prefix == env_prefix, "Env. Prefix does not match"


def check_args():
    from rich import print

    parser = make_parser()
    ns = BaseCommand()
    args = parser.parse_args(data[0].argv, ns)
    print("Initial Args:", args)
    cmd = ShowCommand.from_base(args)
    print("Resolved args:", cmd)
    print(prefix)


if __name__ == "__main__":
    check_args()
