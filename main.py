from dataclasses import dataclass, field
from importlib.metadata import Distribution
from pathlib import Path

from envdeps.environment import Environment
from envdeps.main import EnvDeps
from envdeps.new import DEFAULT_IGNORES
from envdeps.scanner import ImportSet, ProjectScanner

abspath = lambda path: Path(path).expanduser().resolve()


@dataclass
class Tester:
    root: Path
    target: Path
    prefix: Path
    ignore_dirs: list[str] = field(default_factory=lambda: DEFAULT_IGNORES)


data = Tester(
    abspath("~/projects/submeddits"),
    abspath("~/projects/submeddits/submeddits"),
    abspath("~/.pyenv/versions/datascience"),
)


def verbose_imports(imports_by_file: dict[str, dict[Distribution, ImportSet]]):
    for file, dist_imports in imports_by_file.items():
        print(file)
        for dist, imports in dist_imports.items():
            print(f"\t{dist.name}: {imports}")


def main():
    # NOTE: Source of truth for method calling order
    scanner = ProjectScanner(data.target, data.ignore_dirs)
    all_imports, file_imports = scanner.scan()
    env = Environment(data.prefix, data.root, data.ignore_dirs)
    pkg_imports = env.resolve(all_imports)
    # NOTE: to check verbose imports, use:
    imports_by_file = env.get_package_imports_by_file(pkg_imports, file_imports)
    verbose_imports(imports_by_file)


def new_main():
    ed = EnvDeps(data.target, data.root, data.prefix, DEFAULT_IGNORES)
    ed.show("text", False)


if __name__ == "__main__":
    new_main()
