import pytest

from envdeps.common import Dependency
from envdeps.formats import (
    Pyproj,
)
from envdeps.utils import format_table

old_reqs = ["typer>=1.0.2", "matplotlib==1.0.0", "seaborn"]
old_pyproj = """
[project]
dependencies = [
    "typer>=1.0.2",
    "matplotlib==1.0.0",
    "seaborn"
]
"""
scanned = [Dependency(i) for i in ["matplotlib", "polars", "seaborn>=2.0.0"]]
testcase = {
    "unused": {Dependency("typer>=1.0.2")},
    "updated": {Dependency("matplotlib"), Dependency("seabron>=2.0.0")},
    "preserved": {Dependency("seaborn"), Dependency("matplotlib==1.0.0")},
}


@pytest.mark.parametrize("remove_unused", [True, False])
@pytest.mark.parametrize("update_existing", [True, False])
@pytest.mark.parametrize("remove_unknown", [True, False])
def test_merge(remove_unused: bool, update_existing: bool, remove_unknown: bool):
    p = Pyproj(old_pyproj)
    old = p.dependencies
    p.update_dependencies(
        scanned,
        remove_unused=remove_unused,
        update_existing=update_existing,
        remove_unknown=remove_unknown,
    )
    merged_deps = p.dependencies

    merged = set([i for i in merged_deps if isinstance(i, Dependency)])

    print(f"{remove_unused=}, {update_existing=}")
    format_table(old, scanned, list(merged), header=["Old", "Scanned", "Merged"])

    unused_in_merged = merged.intersection(testcase["unused"])

    updated_deps = set()
    preserved_deps = set()
    for prsv_dep in testcase["preserved"]:
        matching_dep = next(
            iter(
                [
                    dep
                    for dep in merged
                    if dep.normalized_name == prsv_dep.normalized_name
                ]
            ),
            None,
        )
        if matching_dep:
            if matching_dep.deep_compare(prsv_dep):
                preserved_deps.add(matching_dep)
    for up_dep in testcase["updated"]:
        matching_dep = next(
            iter(
                [dep for dep in merged if dep.normalized_name == up_dep.normalized_name]
            ),
            None,
        )
        if matching_dep:
            updated_deps.add(matching_dep)

    if remove_unused:
        assert not unused_in_merged, f"Found unused deps in merged: {unused_in_merged}"
    else:
        assert unused_in_merged, "Unused deps not found in merged"

    if update_existing:
        assert not preserved_deps, (
            f"Found preserved existing dependencies: {preserved_deps}"
        )
        if testcase["updated"]:
            assert updated_deps, "Did not find updated Dependencies"
    else:
        assert not update_existing, (
            f"Found updated existing dependencies: {update_existing}"
        )
        if testcase["preserved"]:
            assert preserved_deps, "Did not find preserved dependencies"
