import pytest

from envdeps.dependencies import PackageRequirement, RequirementSet
from envdeps.utils import format_table

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


def toreqs(reqs: list[str]):
    return RequirementSet(reqs)


def alt_merge(
    old: RequirementSet, new: RequirementSet, keep_existing: bool, keep_unused: bool
):
    merged = RequirementSet(new)
    for old_dep in old:
        if old_dep in merged:
            if keep_existing:
                merged.add(old_dep)
            else:
                continue
        else:
            if keep_unused:
                merged.add(old_dep)
    return merged


@pytest.mark.parametrize("remove_unused", [True, False])
@pytest.mark.parametrize("update_existing", [True, False])
@pytest.mark.parametrize("remove_unknown", [True, False])
def test_reqset(remove_unused, update_existing, remove_unknown):
    opts_dict = locals()
    print(opts_dict)
    old = RequirementSet(options_testcase["old"])
    scanned = RequirementSet(options_testcase["scanned"])
    merged = old.update_merge(scanned, remove_unused, update_existing, remove_unknown)

    format_table(
        *[list(i) for i in [old, scanned, merged]],
        header=["Old", "New", "Update Merge"],
    )
    print("\n")
    unused = toreqs(options_testcase["unused"])
    unused_found = []
    for req in unused:
        if req in merged:
            unused_found.append(req)

    if remove_unused:
        assert not unused_found, f"Found unused reqs: {unused_found}"
        print("Passed: No unused in merged.")
    else:
        assert unused_found, f"Did not find unused reqs: {unused_found}"
        print(f"Passed: Kept unused in merged: {unused_found}")
    # print("\n")
    update_preserve_list = (
        update_existing
        and options_testcase["updated_versions"]
        or options_testcase["preserved_versions"]
    )
    update_preserve = [PackageRequirement(i) for i in update_preserve_list]
    failed_reqs = []
    for req in update_preserve:
        res = merged.get(req.name)
        if res and res.deep_equal(req):
            continue
        else:
            failed_reqs.append(res)
    if update_existing:
        assert not failed_reqs, f"Some reqs did not update versions: {failed_reqs}"
        print("Passed: Existing reqs updated to new versions.")
    else:
        assert not failed_reqs, f"Some reqs did not preserve versions: {failed_reqs}"
        print("Passed: Existing reqs versions were preserved.")
    return
    if update_existing:
        failed_reqs = []
        updated = [PackageRequirement(i) for i in options_testcase["updated_versions"]]
        for req in updated:
            res = merged.get(req.name)
            if res and res.deep_equal(req):
                continue
            else:
                failed_reqs.append(res)
        if failed_reqs:
            print(f"The following reqs did not update versions: {failed_reqs}")
        else:
            print("Passed update.")
    else:
        failed_reqs = []
        preserved = [
            PackageRequirement(i) for i in options_testcase["preserved_versions"]
        ]
        for req in preserved:
            res = merged.get(req.name)
            if res and res.deep_equal(req):
                continue
            else:
                failed_reqs.append(req)
        if failed_reqs:
            print(f"The following reqs did not preserve versions: {failed_reqs}")
        else:
            print("Passed Preserve.")

    # has_all_scanned = all(dep for dep in merged if dep in scanned)

    # if remove_unused:
    #     print(f"{PackageRequirement(options_testcase["unused"]) not in merged=}")


lines = [
    "# Production dependencies",
    "requests>=2.28",
    "flask==3.0.0",
    "",
    "# This line is intentionally unparseable",
    "git+https://github.com/org/private-package.git@main#egg=private",
    "--index-url https://pypi.org/simple",
    "totally invalid ???",
]
raw_lines = [
    "# Production dependencies",
    "",
    "# This line is intentionally unparseable",
    "git+https://github.com/org/private-package.git@main#egg=private",
    "--index-url https://pypi.org/simple",
    "totally invalid ???",
]


def test_update_merge(remove_unused: bool, remove_unknown: bool, update_existing: bool):
    opts = {
        "remove_unused": remove_unused,
        "remove_unknown": remove_unknown,
        "update_existing": update_existing,
    }
    rs = RequirementSet(lines)
    og_list = [str(i) for i in rs]
    new_rs = RequirementSet(
        [
            "requests>=3.0.5",
            # "flask>=3.0.5",
            "typer",
            "pandas==3.0.5",
        ]
    )
    new_list = [str(i) for i in new_rs]
    merged = rs.update_merge(new_rs, **opts)
    merged_list = [str(i) for i in merged]
    print(f"{opts=}\n")
    for l, label in zip([og_list, new_list, merged_list], ["Old", "New", "Merged"]):
        print(f"{label}{'-' * 70}")
        print(*l, sep="\n")
        print()


class TestRequirementSet:
    rs = RequirementSet(lines)

    def test_parsed(self):
        raw_reqs = list(str(i) for i in self.rs.iter_raw())
        assert raw_reqs == raw_lines, "Raw requirements not == to raw lines"
        print("Passed 'test_parsed'")

    def test_subset(self):
        subset = toreqs(["requests==1.0.0", "flask"])
        assert subset.is_subset_of(self.rs), (
            f"Subset: {subset} should be subset of Reqs"
        )
        print("Passed 'test_subset'")

    def test_membership(self):
        assert "flask" in self.rs, (
            "Failed string membership: 'flask' is in RequirementSet"
        )
        assert PackageRequirement("flask") in self.rs, (
            "Failed PackageRequirement membership: PackageRequirement('flask') is in RequirementSet"
        )
        assert "fastapi" not in self.rs, (
            "Failed negative string membership: 'fastapi' not in rs"
        )
        print("passed 'test_membership'")

    def test_get(self):
        assert self.rs["requests"] is not None, (
            "Failed __getitem__ for 'requests' (str)"
        )
        assert self.rs.get("flask") is not None, "Failed '.get' for 'flask' (str)"
        print("passed 'test_get'")

    def test_add(self):
        rscopy = RequirementSet(self.rs.iter_parsed())
        rscopy.add("fastapi==0.12.1")
        rscopy.add("typer>=12.1")
        assert rscopy.get("typer>=1.0"), (
            f"Could not get added requirement 'typer' from {rscopy}"
        )
        print("passed 'test_add'")


def mixed_requirement_set_check():
    rs = RequirementSet(lines)

    # Testing correctly parsed, kept reqs order
    raw_reqs = list(str(i) for i in rs.iter_raw())
    assert raw_reqs == raw_lines, "Raw requirements a"

    test_subset = toreqs(["requests==1.0.0", "flask"])
    assert test_subset.is_subset_of(rs), (
        f"Subset: {test_subset} should be subset of Reqs"
    )
    # Testing 'in' and 'add'
    rs.add("typer>=12.0")
    rs.add("flask")
    assert "typer" in rs, "Failed 'typer'(string) is in RequirementSet"
    assert PackageRequirement("typer") in rs, (
        "Failed 'typer'(PackageRequirement) is in RequirementSet"
    )

    # Test 'get' and '__getitem__'
    assert rs["typer"] is not None, "Failed __getitem__ for 'typer' (str)"
    assert rs.get("flask") is not None, "Failed '.get' for 'flask' (str)"

    parsed_reqs = RequirementSet(rs.iter_parsed())

    # assert "typer" in rs

    # print(raw_reqs)
    # for og, t in zip(
    #     raw_reqs,
    # ):
    # assert og == t
    # for line in rs.iter_raw():
    #     print(line)


if __name__ == "__main__":
    test_update_merge(True, True, True)
    # t = TestRequirementSet()
    # t.test_add()
    # mixed_requirement_set_check()
    # test_reqset(True, True, True)
