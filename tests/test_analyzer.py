from typing import Sequence, TypedDict

from packaging.requirements import InvalidRequirement, Requirement

from envdeps.common import Dependency
from envdeps.formats import Pyproj, Requirements
from envdeps.new import OutputFormat
from envdeps.utils import format_table

type DepList = Sequence[Dependency]
type MixedList = Sequence[Dependency | Requirement | str]
import pytest

# TODO: FIX

DEFAULT_OPTS = {
    "remove_unknown": False,
    "remove_unused": True,
    "update_existing": False,
}


class FormatOpts(TypedDict):
    remove_unknown: bool
    remove_unused: bool
    update_existing: bool


def make_kwargs(**kwargs):
    return kwargs


def to_deps(*deps):
    dlist = []
    for dep in deps:
        if isinstance(dep, Dependency):
            dlist.append(dep)
        else:
            try:
                dlist.append(Dependency(str(dep)))
            except InvalidRequirement:
                dlist.append(dep)
    return dlist


options_testcase = {
    "old": ["pandas", "numpy>=1.0.0", "typer", "matplotlib"],
    "scanned": [
        "pandas>=2.0.0",
        "matplotlib>=2.0.0",
        "numpy",
        "seaborn>=10.1",
    ],
    "unused": ["typer"],
    "unknown": [],
    "updated_versions": ["pandas>=2.0.0", "numpy", "matplotlib>=2.0.0"],
    "preserved_versions": ["pandas", "numpy>=1.0.0", "matplotlib"],
}


def convert_deps(dep_lines: list[str]) -> set[Dependency]:
    """Convert dep strings to a set of Dependencies.

    This will raise exception if an object can't be converted.
    """
    dep_deps: set[Dependency] = set()
    for dep in dep_lines:
        dep_deps.add(Dependency(str(dep)))
    return dep_deps


#
class TestOptionsFixed:
    # NOTE: This does not account for 'unknown' deps and does not consider the
    # 'remove_unknown' option. Implement Later.
    text: str = "\n".join(options_testcase["old"])
    old: set[Dependency] = convert_deps(Requirements(text).dependencies)
    _scanned_list = [Dependency(i) for i in options_testcase["scanned"]]
    scanned: set[Dependency] = convert_deps(options_testcase["scanned"])
    unused: set[Dependency] = convert_deps(options_testcase["unused"])
    unknown: set[Dependency] = convert_deps(options_testcase["unknown"])
    updated_deps: set[Dependency] = convert_deps(options_testcase["updated_versions"])
    preserved_deps: set[Dependency] = convert_deps(
        options_testcase["preserved_versions"]
    )

    def _get_merged_deps(
        self, remove_unused=True, update_existing=False
    ) -> set[Dependency]:
        opts = FormatOpts(
            remove_unknown=False,
            remove_unused=remove_unused,
            update_existing=update_existing,
        )
        r = Requirements(self.text)
        r.update_dependencies(self._scanned_list, **opts)
        return convert_deps(r.dependencies)
        return Requirements(self.text)

    def test_defaults(self):
        merged = self._get_merged_deps(
            remove_unused=True, update_existing=False
        )  # Default values
        print(merged)
        unused = self.old.difference(self.scanned)
        unused_in_merged = self.unused.intersection(merged)
        assert not unused_in_merged, (
            f"Found unused dependencies in merged: {unused_in_merged}"
        )
        # Checking preserved
        for dep in merged:
            for prsv_dep in self.preserved_deps:
                if dep == prsv_dep:
                    assert dep.deep_compare(prsv_dep), (
                        f"Existing dependency does not preserve specifier. Old Dep: {str(prsv_dep)} != Merged Dep: {str(dep)}"
                    )
        return

    # def remove_unused_and_update(self):
    #     merged = self._get_merged_deps(remove_unused=True, update_existing=True)
    #     unused_in_merged


# @pytest.mark.skip(reason="Testing 'TestOptionsFixed'")
@pytest.mark.parametrize(
    "text,scanned_deps,format,kwargs",
    [
        (
            ["pandas>=0.1.2", "numpy==1.0.0", "matplotlib"],
            ["pandas", "polars>=10.2", "matplotlib>=12.0"],
            "requirements.txt",
            {"update_existing": True, "remove_unused": True},
        )
    ],
)
class TestDependencyFormat:
    @pytest.fixture(autouse=True)
    def setup(
        self,
        text: str | list[str],
        scanned_deps: list[str],
        format: OutputFormat,
        kwargs: dict,
    ):
        if isinstance(text, list):
            text = "\n".join(text)
        self.scanned: Sequence[Dependency | str] = to_deps(*scanned_deps)
        self.merge_opts = kwargs
        self.opts = FormatOpts(**DEFAULT_OPTS | kwargs)

        if format == "pyproject.toml":
            self.fmt = Pyproj(text)
        else:
            self.fmt = Requirements(text)

        self.old = to_deps(*self.fmt.dependencies)
        self.fmt.update_dependencies(self.scanned, **kwargs)
        self.merged = to_deps(*self.fmt.dependencies)

    def test_removed_unknown(self):
        """Test that unknown dependencies are/are not removed based in
        `self.opts`"""
        # ALL unknown deps (strs) should be kept
        # ALL unused dependencies should be removed
        # Existing dependencies should be updated
        unknown_deps: Sequence[str] = [i for i in self.old if isinstance(i, str)]
        # everything in 'old_strs' should be self.merged
        unaccounted_for = []
        for dep in unknown_deps:
            if dep not in self.merged:
                unaccounted_for.append(dep)
        if self.opts["remove_unknown"] == False:
            assert not unaccounted_for, (
                f"Unknown deps were not found: {unaccounted_for}"
            )
        else:
            if unknown_deps:
                assert unaccounted_for, f"Unknown deps not removed: {unaccounted_for}"

    def test_removed_unused(self):
        """Test that unused dependencies are/are not removed based in
        `self.opts`. If `self.opts["remove_unused"] == True`, dependencies from
        `self.old` which are not scanned (not in `self.scanned`) should not be
        included in `self.merged`.

        If `self.opts["remove_unused"] == False`, the `self.old` dependencies not found
        in `self.scanned` should still be kept.
        """
        old_valid_deps = [dep for dep in self.old if isinstance(dep, Dependency)]
        unused_deps = [dep for dep in old_valid_deps if dep not in self.scanned]
        merged_deps_unused = []
        for dep in self.merged:
            if dep in unused_deps:
                merged_deps_unused.append(dep)
        if self.opts["remove_unused"]:
            assert not merged_deps_unused, (
                f"Found unused deps in merged deps: {merged_deps_unused}"
            )
        else:
            if unused_deps:
                assert merged_deps_unused, (
                    f"Removed unused deps that should have been kept: {merged_deps_unused}"
                )

    def test_update_existing(self):
        """Test whether existing dependencies from `self.old` have their
        original version specifier (if `self.opts["update_existing"] == False`)
        or whether they have used the one from `self.scanned`
        (`self.opts["update_existing"] == True`)"""
        old_deps = [dep for dep in self.old if isinstance(dep, Dependency)]
        # We want to check whether existing dependencies had version updated or
        # kept original
        # get dependencies that were both in 'self.old' and 'self.new' (by name
        # only)
        scanned_deps = [dep for dep in self.scanned if isinstance(dep, Dependency)]
        merged_deps = [dep for dep in self.merged if isinstance(dep, Dependency)]
        updated_versions = []
        preserved_versions = []
        for mdep in merged_deps:
            for sdep in scanned_deps:
                for odep in old_deps:
                    if mdep == sdep == odep:
                        if mdep.deep_compare(sdep) and not mdep.deep_compare(odep):
                            # if merged version same as scanned version and not
                            # same as old version, append to 'updated_versions'
                            updated_versions.append(mdep)
                        else:
                            # Else, the version from old deps was kept
                            preserved_versions.append(mdep)
        if self.opts["update_existing"]:
            assert not preserved_versions, (
                f"Dependencies did not use updated spec: {preserved_versions}"
            )
        else:
            assert not updated_versions, (
                f"Dependencies were updated to scanned spec: {updated_versions}"
            )

    def test_output(self):
        """This is not a test, but just prints the old, new, and merged
        dependencies."""
        format_table(
            self.old,
            self.scanned,
            self.merged,
            header=["Original Deps.", "Scanned Deps.", "Merged Deps."],
        )


# tests = [
#     AnalyzerTest(
#         to_deps("polars>=3.2", "matplotlib", "numpy==1.2.3"),
#         "requirements.txt",
#         "\n".join(["pandas>=3.15", "matplot==0.15.2", "typer>=1.0"]),
#         make_kwargs(remove_unused=True, update_existing=False),
#     ),
# ]


# def set_dependencies_thing(test: AnalyzerTest):
#     fmt = (
#         test.format == "pyproject.toml"
#         and Pyproj(test.deps_txt)
#         or Requirements(test.deps_txt)
#     )
#     old_deps = fmt.dependencies
#     new_deps = test.new_deps
#     fmt.update_dependencies(test.new_deps, **test.opts)
#     merged_deps = fmt.dependencies
#     format_table(
#         old_deps,
#         new_deps,
#         merged_deps,
#         header=["Existing Deps.", "Scanned Deps.", "Merged Deps."],
#     )


if __name__ == "__main__":
    d = Dependency("typer")
    # print(f"{d.normalized_name=}")
    # print(f"{canonicalize_name(d.name)=}")
    # print(f"{d == Dependency("typer>=1.2.3")=}")
    r = Requirements("\n".join(options_testcase["old"]))
    old = convert_deps(r.dependencies)
    old.issuperset({d})
    # new = [Dependency(i) for i in options_testcase["scanned"]]
    # r.update_dependencies(new, remove_unused=True)
    # merged = r.dependencies
    # format_table(old, new, merged, header=["Old", "New", "Merged"])
