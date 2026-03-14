# ruff: noqa: F401
import re

from loguru import logger
from packaging.requirements import InvalidRequirement, Requirement

import envdeps.parse as parse
import envdeps.pkgs as pkgs


def _parse_requirement(line: str) -> Requirement | str:
    """Parse the given line from a `requirements.txt` or pyproject.toml file.

    If line is in a standard format, convert to a `Requirement` object, otherwise keep as a string.
    """
    try:
        req = Requirement(line)
        return req
    except InvalidRequirement:
        logger.debug(f"Found invalid requirement for line: {line}")
        return line


def parse_requirements(requirements_txt: str) -> list[Requirement | str]:
    """Parse lines from a 'requirements.txt' into a list of `Requirement`
    objects or `str` if the requirement is not a normal requirement."""
    lines = requirements_txt.strip().splitlines()
    reqs: list[Requirement | str] = []
    for line in lines:
        line = line.strip()
        if line == "":
            reqs.append(line)
            continue
        # if re.match(r"^#\s*\b.*$", line, re.M):
        #
        #     reqs.append(line)
        #     continue

        req = _parse_requirement(line)
        reqs.append(req)
    return reqs


def merge_old_requirements(
    old_reqs: list[Requirement | str],
    scanned_deps: dict[str, pkgs.PkgInfo],
    mode: str = ">=",
    remove_unused: bool = True,
    keep_unknown: bool = True,
):
    """Merge scanned dependencies with a parsed 'requirements.txt' file. The
    following logic is used to merge old & new requirements:

    - If `keep_unknown == True` and old req is str, keep the line.
    - If old_req is not found in dependencies and `remove_unused == True`, skip it.
    - if old_req is found in scanned dependencies, keep and use `mode` specifier.

    Args:
        old_reqs: The list of parsed requirement lines (from `parse_requirements`)
        scanned_deps: The scanned project dependencies.
        mode: Operator string for version specifier (default '>=')
        remove_unused: Remove old requirements not found in scan? (default True)
        keep_unknown: Keep unknown lines from requirements? (default True)

    Returns:
        new_reqs: List of the merged requirements.
    """
    unused = set()
    new_reqs = []
    # loop through the existing requirements
    for req in old_reqs:
        if isinstance(req, str):
            # req is not a 'normal' (or a comment/pip option), keep it.
            if keep_unknown:
                new_reqs.append(req)
            continue
        norm_name = pkgs.normalize(req.name)
        if norm_name not in scanned_deps:
            # req IS normal, but not in the scanned dependencies.
            # Lets remove it and print to console.
            unused.add(req)
            if remove_unused:
                new_reqs.append(req)
        else:
            # Normal req IS in scanned deps, we keep it (ensuring version specifier)
            dep = scanned_deps[norm_name]
            new_reqs.append(dep.to_req(mode))
    return new_reqs
