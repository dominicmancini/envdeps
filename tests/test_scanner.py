import fnmatch
import itertools
import os
import posixpath
import re
from pathlib import Path
from typing import Callable

from envdeps.common import DEFAULT_IGNORES
from envdeps.scanner import ProjectScanner
from envdeps.utils import timer_decorator

ignore_names = DEFAULT_IGNORES


def matches(path: Path, patterns: set[str]):
    return any(fnmatch.fnmatch(path.name, pat) for pat in patterns)


def find_paths_matching(start: Path, pats: set[str]):
    paths = []
    for p in start.rglob("*"):
        if matches(p, pats):
            paths.append(p)
    return paths


def iter_ignore_names(target: Path, ignore: list[str]):
    for dirpath, dirnames, filenames in os.walk(target):
        dirnames[:] = [d for d in dirnames if d not in ignore]
        for file in filenames:
            if file.endswith(".py"):
                yield Path(dirpath) / file


def filterfalse(names, pat):
    pat = os.path.normcase(pat)
    match = re.compile(fnmatch.translate(pat)).match
    if os.path is posixpath:
        return list(itertools.filterfalse(match, names))
    result = []
    for name in names:
        if match(os.path.normcase(name)) is None:
            result.append(name)
    return result


def filter_dirnames(dirnames: list[str], pats: list[str]):
    for pat in pats:
        dirnames = filterfalse(dirnames, pat)
    return dirnames


def iter_ignore_globs(target: Path, ignore_pats: list[str]):
    for dirpath, dirnames, filenames in os.walk(target):
        # dirnames[:] = [
        #     d for d in dirnames for pat in ignore_pats if not fnmatch.fnmatch(d, pat)
        # ]
        dirnames[:] = filter_dirnames(dirnames, ignore_pats)
        for file in filenames:
            if file.endswith(".py"):
                yield Path(dirpath) / file


should_ignore_path: Callable[[Path, Path, list[str]], bool] = (
    lambda target, path, ignore: any(
        d in path.relative_to(target).parts for d in ignore
    )
)


def iter_path_walk(target: Path, ignore: list[str]):
    for path in target.rglob("*.py"):
        should_ignore = any(d in path.relative_to(target).parts for d in ignore)
        if not should_ignore:
            yield path


data = {
    "target": Path("~/projects/envdeps/envdeps").expanduser(),
    "ignore_dirs": ["__pycache__", ".git", ".pytest_cache", "dev", "tests"],
    "ignore_pats": ["__pycache__", ".*", "dev", "tests"],
}


@timer_decorator
def test_names():
    res = list(iter_ignore_names(data["target"], data["ignore_dirs"]))
    return res
    # print(len(res))


@timer_decorator
def test_pats():
    res = list(iter_ignore_globs(data["target"], data["ignore_dirs"]))
    return res
    # print(len(res))


@timer_decorator
def test_path_walk():
    res = list(iter_path_walk(data["target"], data["ignore_dirs"]))
    return res


@timer_decorator
def test_ps_scan(data=data):
    return ProjectScanner(data["target"], data["ignore_dirs"]).scan()


@timer_decorator
def test_ps_alt_scan(data=data):
    # return ProjectScanner(data["target"], data["ignore_dirs"])._alt_scan()
    return ProjectScanner(data["target"], data["ignore_dirs"]).iter_scan()


def compare_iters():
    names = test_names()
    pats = test_pats()
    # pp(names)
    # pp(pats)
    print(f"{names == pats=}")
    print(f"{set(names).symmetric_difference(pats)=}")
    # print(f"{set(pats).difference(names)=}")
    # print(f"{set(names).difference(pats)=}")


def compare_project_scanners(data=data):
    og_res = test_ps_scan(data)
    alt_res = test_ps_alt_scan(data)

    imports_same = og_res[0] == alt_res[0]
    print(f"Same imports: {imports_same}")

    file_imports_same = og_res[1] == alt_res[1]
    print(f"Same file imports: {file_imports_same}")


if __name__ == "__main__":
    # compare_iters()
    compare_project_scanners()
