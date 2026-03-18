from dataclasses import dataclass
from importlib.metadata import Distribution
from pathlib import Path
from typing import Literal

from envdeps.environment import DependencyResolver, Environment
from envdeps.scanner import ImportSet, ProjectScanner
from envdeps.utils import format_table

type FormatOpts = Literal["text", "json", "table"]

type ExportFormats = Literal["pyproject", "requirements"]


@dataclass
class DistImportFiles:
    name: str
    dist: Distribution
    imports: ImportSet
    files: list[Path]


class EnvDeps:
    def __init__(self, target: Path, root: Path, prefix: Path, ignore_dirs: list[str]):
        # NOTE: This class expects fully resolved arguments
        # TODO: handle resolving missing args after parsing CLI
        self.target = target
        self.root = root
        self.prefix = prefix
        self.ignore_dirs: list[str] = ignore_dirs
        self.scanner = ProjectScanner(self.target, self.ignore_dirs)
        self.env = Environment(self.prefix, self.root, self.ignore_dirs)

    def show(self, format: FormatOpts = "text", verbose: bool = False):
        all_imports, file_imports = self.scanner.scan()
        # dist_imports = self.env.resolve(all_imports)
        # file_to_dist_imports = self.env.get_package_imports_by_file(
        #     dist_imports, file_imports
        # )
        # # TODO: Implement other formats/verbose
        # print("Packages to project imports:\n")
        # for dist, imports in dist_imports.items():
        #     print(f"{dist.name}: {imports}")
        resolver = DependencyResolver(self.prefix, self.root, self.ignore_dirs)
        for file, imports in file_imports.items():
            for imp in imports:
                resolver.add_import(imp, file)
        if format == "json":
            json_str = resolver.to_json()
            print(json_str)
        elif format == "table":
            tbl = resolver.to_table_data(verbose)
            format_table(*tbl.values(), header=list(tbl.keys()))
        else:
            reqset = resolver.to_requirement_set(mode="==")
            reqstr = reqset.to_string()
            print(reqstr)
            # for name, dep in resolver.resolved.items():
            #     print(
            #         f"{name}:\n  Imported in: {dep.all_files}\n  Imports used: {dep.imported_modules}"
            #     )

    def export(self, format: ExportFormats = "requirements", specifier: str = ">="):
        pass
