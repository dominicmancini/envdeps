from pathlib import Path

import pytest

from envdeps import utils
from envdeps.dependencies import Dependency, RequirementSet
from envdeps.formatters.base import BaseFormatter
from envdeps.formatters.pyproject import PyProjectFormatter
from envdeps.formatters.requirements import RequirementsFormatter

test_req_path = Path("~/projects/submeddits/requirements.txt").expanduser()

data = [
    "# Some comment",
    "pytest==1.2.3",
    "attrs>=1.2.3",
    "requests",
    "-e .",
]
new_data = RequirementSet(["pytest", "attrs", "polars"])


def test_write_new_reqs_file(tmp_path: Path):
    test_file = tmp_path / "new_requirements.txt"
    r = RequirementsFormatter("\n".join(data))
    r.load()
    r.dump(test_file)
    new_lines = test_file.read_text().splitlines()
    print("File Lines:", *new_lines)
    new_reqs = RequirementSet(new_lines)
    assert new_reqs == RequirementSet(data)


@pytest.fixture
def lines():
    return data


def _fmt_test(fmt: BaseFormatter):
    reqs = fmt.dependencies
    merged = reqs.update_merge(new_data, True, False, False)
    fmt.dependencies = merged
    result = RequirementSet(["pytest==1.2.3", "attrs>=1.2.3", "polars"])
    assert fmt.dependencies == result, "Not equal"
    utils.format_table(
        *[[str(dep) for dep in sublist] for sublist in [reqs, new_data, merged]],
        header=["old", "new", "merged"],
    )
    # print(f"{fmt.dependencies == result=}")
    # utils.format_table(
    #     *[str(i) for i in [i for i in [reqs, new_data, merged]]],
    #     header=["old", "new", "merged"],
    # )


def test_reqs(lines: list[str]):
    txt = "\n".join(lines)
    r = RequirementsFormatter(txt)
    r.load()
    _fmt_test(r)
    # reqs = r.dependencies
    # merged = reqs.update_merge(new_data, True, False, False)
    # r.dependencies = merged
    # result = RequirementSet(["pytest==1.2.3", "attrs>=1.2.3", "polars"])
    # print(f"{r.dependencies == result=}")


def test_pyproj(lines: list[str]):
    txt = utils.dep_list_to_pyproject(lines)
    p = PyProjectFormatter(txt)
    p.load()
    _fmt_test(p)


def test_load(fmt: BaseFormatter):
    print("Before loading")
    print(fmt.dependencies)
    fmt.load()
    print("After loading")
    print(fmt.dependencies)


def test_overwrite_deps(fmt: BaseFormatter, new_deps: RequirementSet):
    print("Original Dependencies")
    fmt.dependencies._view()
    fmt.dependencies = new_deps
    print("New Dependencies:")
    fmt.dependencies._view()


test = """
# This is a comment
pynvim>=12.1.4
attrs==2.3.4
pytest
-e .
pandas>=0.12
"""

# TODO: Fix or remove the '.load()' mechanism of the Formatters


if __name__ == "__main__":
    pyfmt = PyProjectFormatter.from_file(
        Path("/home/domancini/projects/submeddits/pyproject.toml")
    )
    reqfmt = RequirementsFormatter.from_file(test_req_path)
    new_deps = RequirementSet(
        [
            Dependency("purple>=10.2.3"),
            Dependency("pink==0.12"),
            Dependency("green"),
        ]
    )
    print("Pyproject.toml:\n")
    test_overwrite_deps(pyfmt, new_deps)
    print("\nRequirements:\n")
    test_overwrite_deps(reqfmt, new_deps)
# reqs = Requirements.from_file(test_req_path)
# reqs.load()
# deps = RequirementSet(reqs.dependencies)
#
# merged = deps.update_merge(RequirementSet([
#     "some-pkg", "pynvim>=2.0.0"
# ]), remove_unused=True)
# print(merged.dependencies.to_string())
