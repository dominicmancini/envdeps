import argparse
import os
from pathlib import Path
from pprint import pp

import pytest

from envdeps.cli import make_parser
from tests.test_cases import TestCaseAnalyzer

tca = TestCaseAnalyzer

# Example Namespace
# Namespace(command='reqs', ignore=[], env_prefix=None, root=PosixPath('.'),
# target=PosixPath('envdeps'), print=False, o
# utput=None, mode='')
#


getprefix = lambda ver: os.path.join("/home/domancini/.pyenv/versions", ver)

prefix = os.getenv("VIRTUAL_ENV")
if not prefix:
    raise ValueError("No venv prefix.")

testdata = [
    tca("envdeps", "envdeps", "~/projects/envdeps", prefix),
    tca(
        "submeddits",
        "submeddits",
        "~/projects/envdeps/submeddits",
        getprefix("datascience"),
    ),
    tca("resume", "src/resume", "~/projects/resume", getprefix("resume_venv")),
]

# Example Namespace
# Namespace(command='reqs', ignore=[], env_prefix=None, root=PosixPath('.'),
# target=PosixPath('envdeps'), print=False, o
# utput=None, mode='')
#


class TestCliParser:
    @pytest.fixture(autouse=True)
    def setup(self, data: TestCaseAnalyzer):
        parser = make_parser()
        self.data = data
        self.parser = make_parser()

    def test_base_args(self):
        argv = self.data.to_cli("reqs")
        args = self.parser.parse_args(argv)
        assert args.env_prefix == Path(self.data.prefix)
        assert args.target == Path(self.data.target)
        assert args.root == Path(self.data.root)

    # def test_reqs(self):
    #     argv = self.data.to_cli("reqs")
    #     args = self.parser.parse_args(argv)


def test_cli_parser(test: TestCaseAnalyzer, ns: argparse.Namespace):
    argv = test.to_cli("reqs")
    parser = make_parser()
    args = parser.parse_args(argv)
    pp(test)
    pp(args)
    # print(f"{args._get_args()=}")
    # print(f"{args._get_kwargs()=}")
    # test_ns = test.to_ns("reqs")
    # print(f"{args == test_ns=}")


t = TestCaseAnalyzer("default_opts", "envdeps", "~/projects/envdeps", prefix)
test_cli_parser(t, argparse.Namespace())

# print(t.to_cli("reqs"))
