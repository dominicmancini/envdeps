import ast
import re
import sys
import tomllib
from pathlib import Path
from typing import TypeVar, cast
from warnings import deprecated

from loguru import logger
from packaging.requirements import Requirement

T = TypeVar("T")

# SECTION: Parsing broken files Incrementally --------------


def _parse_file_incrementally(fpath):
    with open(fpath, "r") as f:
        text = f.read()
    return try_parse_incrementally(text, fpath)


def try_parse_incrementally(text: str, fpath) -> set[str]:
    """Parse the given file text incrementally, for files that encountered `SyntaxError` during ast parsing.

    This parses one line at a time, collecting the imports
    until it is assumed the import section is over.
    """
    lines = text.strip().splitlines()
    # imports = set()
    accumulated_lines = []
    last_successful_imports = set()

    for i, line in enumerate(lines):
        accumulated_lines.append(line)
        if _line_past_imports(line):
            break
        try:
            partial_content = "".join(accumulated_lines)
            tree = ast.parse(partial_content, filename=str(fpath))
            last_successful_imports = _get_imports_from_tree(tree)
        except SyntaxError:
            # keep going, might be incomplete statement
            continue
    return last_successful_imports


def _line_past_imports(line: str) -> bool:
    """Check if the import section is over.
    This heuristic assumes import section is over before the first func or class definition.
    """
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return False
    if stripped.startswith("def ") or stripped.startswith("class "):
        return True
    return False


def _get_imports_from_tree(tree: ast.Module):
    """Collect the top-level module imports from this syntax tree."""
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module.split(".")[0])
    return imports


# SECTION: Parsing broken files with regex ------------


@deprecated(
    "Better to use incremental parsing for broken trees. This uses a regex method."
)
def parse_broken_file_imports(filepath):
    with open(filepath) as f:
        text = f.read()
    new_lines = []
    lines = text.strip().splitlines()
    for line in lines:
        if re.match(r"^(import|from)\s.*$", line):
            new_lines.append(line)
    if not new_lines:
        raise ValueError("Failed to get lines from broken syntax file")
    new_text = "\n".join(new_lines)
    try:
        tree = ast.parse(new_text)
        return tree
    except SyntaxError:
        print(
            f"Failed to re-parse the broken syntax tree. Fix or ignore error in: {filepath}"
        )
        print("Exiting!")
        sys.exit(0)


@deprecated("Old regex method of parsing broken trees.")
def safe_parse_tree(fpath):
    with open(fpath, "r") as f:
        text = f.read()
    try:
        tree = ast.parse(text, filename=fpath)
        return tree
    except SyntaxError as e:
        logger.warning(f"Failed to parse full file: {e.filename}, lineno: {e.lineno}")
        logger.info("Attempting to re-parse imports from broken tree")
        pass
    mod = parse_broken_file_imports(fpath)
    return mod
    # print(
    #     f"Encountered Syntax error when parsing file: {e.filename} at line: {e.lineno}: {e.msg, e}"
    # )
    #
    # sys.exit(1)


# Original Implementation -----------------------------------


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
    """Filter out the stdlib module names from this set of import names."""
    imports_3rd_party = set()
    for i in imports:
        if i not in sys.stdlib_module_names:
            imports_3rd_party.add(i)
    return imports_3rd_party


@deprecated("old")
def get_imports_in_file(filepath):
    """Parse this file, collecting all imports and returning.
    NOTE: This now uses 'safe_parse_tree' which is different from
    original implementation and from new implementation (`collect_target_dir_imports`)
    """
    imports = set()
    tree = safe_parse_tree(filepath)
    # with open(filepath, "r") as f:
    #     tree = ast.parse(f.read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module.split(".")[0])
    return imports


@deprecated(
    "This uses regex fallback for broken trees. Use `collect_target_dir_imports`."
)
def collect_file_imports(target: Path, ignore_dirs: list[str]) -> set[str]:
    all_imports = set()
    for file in target.rglob("*.py"):
        # if all(part in file.parts for part in ignore_dirs):
        #     continue
        if any(dir in file.parts for dir in ignore_dirs):
            continue
        all_imports.update(get_imports_in_file(file))
    return all_imports


def parse_pyproject_dependencies(fpath: Path) -> list[Requirement]:
    with open(fpath, "rb") as f:
        data = tomllib.load(f)
    deps = safeget(data, "project", "dependencies", typ=list[str])
    if not deps:
        return []
    reqs = [Requirement(d) for d in deps]
    return reqs


def collect_target_dir_imports(target: Path, ignore_dirs: list[str]) -> set[str]:
    """Collect imported modules in the python source files.

    This parses the file's Abstract Syntax Tree, selecting the `ast.Import` and `ast.ImportFrom` nodes and extracting the top-level modules of the import.

    For example, a file with the following statements::

        from pandas import DataFrame, Series
        from nested.utils import my_function
        import cool.thing

    Would result in: `['pandas', 'nested', 'cool']`

    Args:
        target: Target directory to scan for imports.
        ignore_dirs: List of names to ignore when present.

    Returns:
        set: Set of the used imports.
    """
    all_imports = set()
    for file in target.rglob("*.py"):
        should_ignore = any(dir in file.parts for dir in ignore_dirs)
        if should_ignore:
            continue
        with open(file, "r") as f:
            text = f.read()
        try:
            tree = ast.parse(text, file)
            # all_imports.add(_get_imports_from_tree(tree))
            all_imports.update(_get_imports_from_tree(tree))
            continue
        except SyntaxError as e:
            logger.debug(
                f"Got SyntaxError parsing: {e.filename}, line: {e.lineno}. Attempting to parse Incremementally."
            )
            pass
        all_imports.update(try_parse_incrementally(text, file))
        # all_imports.add(try_parse_incrementally(text, file))
    return all_imports


if __name__ == "__main__":
    f = Path("/home/domancini/projects/markformat/src/markformat/markformat.py")
    imports = _parse_file_incrementally(f)
    print(f"Incrememntal results: {imports}")
    mod = safe_parse_tree(f)
    if mod:
        imports2 = _get_imports_from_tree(mod)
        print(f"safe_parse_tree: {imports2}")
    print("\n\nACTUAL FILE:\n")
    print(f.read_text())
