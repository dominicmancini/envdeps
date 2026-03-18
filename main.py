from dataclasses import dataclass, field
from importlib.metadata import Distribution
from pathlib import Path

from envdeps.common import DEFAULT_IGNORES
from envdeps.environment import DependencyResolver
from envdeps.main import EnvDeps
from envdeps.scanner import ImportSet, ProjectScanner

abspath = lambda path: Path(path).expanduser().resolve()


@dataclass
class Tester:
    root: Path
    target: Path
    prefix: Path
    ignore_dirs: list[str] = field(default_factory=lambda: list(DEFAULT_IGNORES))


data = {
    "envdeps": Tester(
        abspath("~/projects/envdeps"),
        abspath("~/projects/envdeps/envdeps"),
        abspath("~/.pyenv/versions/envdeps_venv"),
    ),
    "submeddits": Tester(
        abspath("~/projects/submeddits"),
        abspath("~/projects/submeddits/submeddits"),
        abspath("~/.pyenv/versions/datascience"),
    ),
    "markformat": Tester(
        abspath("~/projects/markformat"),
        abspath("~/projects/markformat/src/markformat"),
        abspath("~/.pyenv/versions/cli_venv"),
    ),
}


def verbose_imports(imports_by_file: dict[str, dict[Distribution, ImportSet]]):
    for file, dist_imports in imports_by_file.items():
        print(file)
        for dist, imports in dist_imports.items():
            print(f"\t{dist.name}: {imports}")


def main(data: Tester):
    # NOTE: Source of truth for method calling order
    scanner = ProjectScanner(data.target, data.ignore_dirs)
    all_imports, file_imports = scanner.scan()
    # env = Environment(data.prefix, data.root, data.ignore_dirs)
    # pkg_imports = env.resolve(all_imports)
    # # NOTE: to check verbose imports, use:
    # imports_by_file = env.get_package_imports_by_file(pkg_imports, file_imports)
    # verbose_imports(imports_by_file)
    depres = DependencyResolver(data.prefix, data.root)
    for file, imp in file_imports.items():
        for i in imp:
            depres.add_import(i, file)
    reqs = depres.to_requirement_set("==")
    print(reqs.to_string())


def new_main(data: Tester = data["envdeps"]):
    ed = EnvDeps(data.target, data.root, data.prefix, list(DEFAULT_IGNORES))
    ed.show("text", False)


if __name__ == "__main__":
    print(f"Envdeps {'-' * 60}")
    main(data["envdeps"])
    # print(f"Submeddits {'-' * 60}")
    # main(data["submeddits"])
    print(f"markformat {'-' * 60}")
    main(data["markformat"])
