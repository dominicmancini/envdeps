from envdeps.dependencies import RequirementSet
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


def test_reqset(remove_unused: bool = True, update_existing=False):
    old = RequirementSet(options_testcase["old"])
    print(f"{old.get("numpy")=}")
    old.add("typer===0.13")
    print(old)
    return
    print(old)
    scanned = RequirementSet(options_testcase["scanned"])
    res = old.update_merge(scanned, remove_unused, update_existing)
    print("Merged:\n", res)
    print("Actual:\n", options_testcase["updated_versions"])

    # print(res)
    # return
    # unused = old.difference(scanned)
    # assert unused == RequirementSet(options_testcase["unused"]), (
    #     "Did not find unused deps."
    # )
    # merged_update = old.merge(scanned, update=True)
    #
    # print("Merged Update:", merged_update)
    # print("Test Updated:", options_testcase["updated_versions"])
    # merged_preserved = old.merge(scanned, False)
    # print("Merge Preserved:", merged_preserved)
    # print("Test preserved:", options_testcase["preserved_versions"])

    # assert merged_update == RequirementSet(options_testcase["updated_versions"])
    # assert merged_update == RequirementSet(options_testcase["preserved_versions"])


if __name__ == "__main__":
    # test_reqset(True, True)
    opts = dict(keep_existing=False, keep_unused=False)
    old = toreqs(["numpy", "pandas>=1.2.3", "typer", "poopy"])
    new = toreqs(["numpy>=2.3.4", "pandas==2.3.4", "typer"])
    res = alt_merge(old, new, **opts)
    merged = old.update_merge(new, True, True)
    print(f"{res == merged=}")
    format_table(
        *[list(i) for i in [old, new, res, merged]],
        header=["Old", "New", "Alt. Merged", "Update Merge"],
    )
    # print(opts)
    # dupe = RequirementSet(old)
