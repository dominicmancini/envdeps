import ast
import sys
from pathlib import Path
from typing import TypeVar, cast

import tomllib
from packaging.requirements import Requirement

T = TypeVar("T")


def safeget(d: dict, *keys, typ: type[T]) -> T | None:
    for key in keys:
        try:
            d = d[key]
            # if not isinstance(d, dict):
            #     return d
        except (KeyError, TypeError):
            return None
    return cast(T, d)


def filter_stdlib_imports(imports: set[str]) -> set[str]:
    imports_3rd_party = set()
    for i in imports:
        if i not in sys.stdlib_module_names:
            imports_3rd_party.add(i)
    return imports_3rd_party


def get_imports_in_file(filepath):
    imports = set()
    with open(filepath, "r") as f:
        tree = ast.parse(f.read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module.split(".")[0])
    return imports


def collect_file_imports(target: Path, ignore_dirs: list[str]) -> set[str]:
    all_imports = set()
    for file in target.rglob("*.py"):
        if all(part in file.parts for part in ignore_dirs):
            continue
        all_imports.update(get_imports_in_file(file))
    return all_imports


def parse_pyproject_dependencies(fpath: Path):
    with open(fpath, "rb") as f:
        data = tomllib.load(f)
    deps = safeget(data, "project", "dependencies", typ=list[str])
    if not deps:
        return []
    reqs = [Requirement(d) for d in deps]
    return reqs


if __name__ == "__main__":
    p = Path.cwd().joinpath("envdeps")
