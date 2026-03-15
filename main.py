from dataclasses import dataclass, field
from pathlib import Path

from envdeps.dependencies import PackageRequirement, RequirementSet
from envdeps.environment import Environment, TLImports
from envdeps.new import DEFAULT_IGNORES
from envdeps.scanner import FileImports, ProjectScanner

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


def file_imported_packages(fimports: FileImports, tl_imports: TLImports):
    file_to_pkg_imports = {}
    for file, imps in fimports.items():
        for dist, pkg in tl_imports.items():
            if imps.isdisjoint(pkg.imports):
                file_to_pkg_imports[file] = pkg
    return file_to_pkg_imports


def main():
    # NOTE: Source of truth for method calling order
    scanner = ProjectScanner(data.target, data.ignore_dirs)
    all_imports, file_imports = scanner.scan()
    env = Environment(data.prefix, data.root, data.ignore_dirs)
    pkg_imports = env.resolve(all_imports)
    for pkg, imps in pkg_imports.items():
        print(f"{pkg.name}: {imps}")


reqs_1 = RequirementSet(
    [
        PackageRequirement("typer>=0.12.1"),
        PackageRequirement("pandas"),
        PackageRequirement("numpy==0.1.2"),
    ]
)

reqs_2 = RequirementSet(
    [
        PackageRequirement("typer"),
        PackageRequirement("pandas>=0.12.1"),
        PackageRequirement("matplotlib<=0.12"),
    ]
)


# if __name__ == "__main__":
#     print(f"{reqs_1.merge(reqs_2, update=True)=}")
#     print(f"{reqs_1.merge(reqs_2, False)=}")
#     print(f"{reqs_1.intersection(reqs_2)=}")
