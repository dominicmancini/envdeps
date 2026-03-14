import re
import textwrap

from envdeps.common import Dependency
from tests.test_cases import TestCaseDependencies, VerifyDeps

DEPENDENCIES_TEST_CASES = [
    #     TestCaseDependencies(
    #         "reqs_mixed",
    #         textwrap.dedent("""\
    # # This is a comment, to show how #-prefixed lines are ignored.
    # # It is possible to specify requirements as plain names.
    # pytest
    # pytest-cov
    # beautifulsoup4
    #
    # # The syntax supported here is the same as that of requirement specifiers.
    # docopt == 0.6.1
    # requests [security] >= 2.8.1, == 2.8.* ; python_version < "2.7"
    # urllib3 @ https://github.com/urllib3/urllib3/archive/refs/tags/1.26.8.zip
    #
    # # It is possible to refer to other requirement files or constraints files.
    # -r other-requirements.txt
    # -c constraints.txt
    #
    # # It is possible to refer to specific local distribution paths.
    # ./downloads/numpy-1.9.2-cp34-none-win32.whl
    #
    # # It is possible to refer to URLs.
    # http://wxpython.org/Phoenix/snapshot-builds/wxPython_Phoenix-3.0.3.dev1820+49a8884-cp34-none-win_amd64.whl
    #         """),
    #         "requirements.txt"
    #     ),
    TestCaseDependencies(
        "reqs_mixed_2",
        textwrap.dedent("""\
    flask==3.0.0
    # A comment
    -e .
    requests @ git+https://github.com/psf/requests.git@main
    --extra-index-url https://my-private-repo.com/simple
        """),
        VerifyDeps(
            parsed=[
                "flask==3.0.0",
                "requests @ git+https://github.com/psf/requests.git@main",
            ],
            unknown=[
                "# A comment",
                "-e .",
                "--extra-index-url https://my-private-repo.com/simple",
            ],
        ),
        "requirements.txt",
    ),
    TestCaseDependencies(
        "reqs_mixed_3",
        textwrap.dedent("""\
    # This is a comment and will be ignored by pip
    pandas
    lxml==3.2.3
    numpy>=1.7.1
    requests[security]==2.8.1
    urllib3 @ https://github.com
    -r other-requirements.txt
        """),
        VerifyDeps(
            parsed=[
                "pandas",
                "lxml==3.2.3",
                "numpy>=1.7.1",
                "requests[security]==2.8.1",
                "urllib3 @ https://github.com",
            ],
            unknown=[
                "# This is a comment and will be ignored by pip",
                "-r other-requirements.txt",
            ],
        ),
        "requirements.txt",
    ),
    TestCaseDependencies(
        "pyproj_mixed",
        textwrap.dedent("""\
      httpx
      gidgethub[httpx]>4.0.0
      django>2.1; os_name != 'nt'
      django>2.0; os_name == 'nt'
        """),
        VerifyDeps(
            parsed=[
                "httpx",
                "gidgethub[httpx]>4.0.0",
                "django>2.1; os_name != 'nt'",
                "django>2.0; os_name == 'nt'",
            ],
            unknown=[],
        ),
        "pyproject.toml",
    ),
]


VCS = re.compile(r"^(.*)\s@\s((git|hg|svn|bzr)\+([\w\-]+))://.*$", flags=re.M)
EXTERNAL_REQ_FILE = re.compile(r"^\-[rc]\s+\S+\.txt", flags=re.M)
EDITABLE_INSTALL = re.compile(r"^(\-e|\-{2}editable)\s.+$", re.M)
# should come last
OPTION_FLAG = re.compile(r"(^\-[a-z]\s*?|\-{2}[\w\-]+\s*)$", re.M)
SPECIFIER_PATS = {
    "vcs": VCS,
    "requirements_file": EXTERNAL_REQ_FILE,
    "editable_install": EDITABLE_INSTALL,
    "option_flag": OPTION_FLAG,
}

# NOTE: 2 types of requirement specifiers
# 1. Name-based: has a package name and (optionaly) a extras (optional dependencies),
# constraints, environmental markers
# 2. URL-based: Package name, extras(optional) , a URL, environmental markers (optional)


def test_dep_formats(test_case: TestCaseDependencies):
    fmt = test_case.formatter
    deps = fmt.dependencies
    unknown, parsed = [], []
    for dep in deps:
        if isinstance(dep, str):
            unknown.append(dep)
        elif isinstance(dep, Dependency):
            parsed.append(dep)
    print(f"Valid Dependencies:\n {parsed}")
    print(f"\nUnknown Dependencies:\n {unknown}")

    print(f"{unknown == test_case.verify_deps["unknown"]=}")
    print(f"{parsed == test_case.verify_deps["parsed"]=}")


def parse_invalid_lines(line: str):
    for name, pat in SPECIFIER_PATS.items():
        m = pat.match(line)
        if m is not None:
            return name
    return None


if __name__ == "__main__":
    for testcase in DEPENDENCIES_TEST_CASES[:-1]:
        print(testcase.id)
        test_dep_formats(testcase)
        print("\n")
