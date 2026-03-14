from argparse import Namespace
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, TypedDict

from envdeps.common import Dependency, OutputFormat
from envdeps.formats import DependencyList, Pyproj, Requirements
from envdeps.utils import dep_list_to_pyproject


def abspath(path: str):
    return Path(path)


class FormatOpts(TypedDict):
    remove_unknown: bool
    remove_unused: bool
    update_existing: bool


@dataclass
class TestCaseAnalyzer:
    id: str
    target: str
    root: str
    prefix: str
    ignore: list[str] = field(default_factory=lambda: ["__pycache__"])
    mode: str = ">="

    def to_cli(self, cmd: Literal["imports", "reqs", "pyproject"], **opts):
        args = deque([f"--root={self.root}", f"--env-prefix={self.prefix}"])
        if self.ignore:
            args.appendleft(f"--ignore={','.join(self.ignore)}")
        args.appendleft(cmd)
        if opts:
            for k, v in opts.items():
                args.append(f"{k}={v}")
        args.append(self.target)
        return list(args)

    def to_ns(self, cmd: str):
        return Namespace(
            command=cmd,
            ignore=self.ignore,
            env_prefix=Path(self.prefix),
            root=Path(self.root),
            target=Path(self.target),
            mode=self.mode,
            print=False,
            output=False,
        )


class VerifyDeps(TypedDict):
    parsed: list[str]
    unknown: list[str]


@dataclass
class TestCaseDependencies:
    id: str
    _raw_deps: str | list[str]
    verify_deps: VerifyDeps
    format: OutputFormat = "requirements.txt"

    @property
    def txt(self):
        if isinstance(self._raw_deps, list):
            txt = (
                self.format == "pyproject.toml"
                and dep_list_to_pyproject(self._raw_deps)
                or "\n".join(self._raw_deps)
            )
        else:
            txt = self._raw_deps
        return txt

    @property
    def formatter(self) -> Requirements | Pyproj:
        return (
            self.format == "requirements.txt"
            and Requirements(self.txt)
            or Pyproj(self.txt)
        )


@dataclass
class TestMergeOpts:
    id: str
    old_reqs: list[str]
    scanned: DependencyList
    unused: set[Dependency]
    updated: set[Dependency]
    preserved: set[Dependency]
