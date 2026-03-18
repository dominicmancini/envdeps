from dataclasses import dataclass
from importlib.metadata import Distribution
from pathlib import Path
from typing import Literal

from rich.syntax import Syntax

from envdeps.environment import DependencyResolver
from envdeps.formatters.base import BaseFormatter
from envdeps.formatters.pyproject import PyProjectFormatter
from envdeps.formatters.requirements import RequirementsFormatter
from envdeps.output import RequirementsLexer, console
from envdeps.scanner import ImportSet, ProjectScanner

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
        # self.env = Environment(self.prefix, self.root, self.ignore_dirs)

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
            console.print_json(json_str)
            # print(json_str)
        elif format == "table":
            tbl = resolver.to_table(verbose)
            console.print(tbl)
            # tbl = resolver.to_table_data(verbose)
            # format_table(*tbl.values(), header=list(tbl.keys()))
        else:
            reqset = resolver.to_requirement_set(mode="==")
            reqstr = reqset.to_string()
            reqs_syn = Syntax(reqstr, RequirementsLexer())
            console.print(reqs_syn)
            # print(reqstr)

    def _get_formatter(self, path: Path, format: ExportFormats) -> BaseFormatter:
        if format == "pyproject":
            if path.exists():
                return PyProjectFormatter.from_file(path)
            else:
                return PyProjectFormatter()
        else:
            if path.exists():
                return RequirementsFormatter.from_file(path)
            else:
                return RequirementsFormatter()

    def _display_text_syntax(self, text: str, lang: ExportFormats):
        lexer = RequirementsLexer() if lang == "requirements" else "toml"
        hl_text = Syntax(text, lexer)
        console.print(hl_text)

    def export(
        self,
        path: Path,
        format: ExportFormats,
        specifier: str,
        merge: bool,
        remove_unknown: bool,
        remove_unused: bool,
        update_existing: bool,
        _write: bool = False,
    ):
        all_imports, file_imports = self.scanner.scan()
        resolver = DependencyResolver(self.prefix, self.root, self.ignore_dirs)
        for file, imports in file_imports.items():
            for i in imports:
                resolver.add_import(i, file)
        scanned_deps = resolver.to_requirement_set(mode=specifier)
        if not scanned_deps:
            raise ValueError("No Scanned dependencies to write.")
        fmt = self._get_formatter(path, format)
        if merge and fmt.dependencies:
            merged = fmt.dependencies.update_merge(
                scanned_deps,
                remove_unused=remove_unused,
                update_existing=update_existing,
                remove_unknown=remove_unknown,
            )
        else:
            # Even tho its called merged, when 'merge=True', we are just
            # replacing all the dependencies (if any) with the scanned ones
            merged = scanned_deps
        if not merged:
            print("No merged dependencies to write. Aborting.")
            return
        fmt.dependencies = merged
        # print("Final Dependencies:\n")
        # print(fmt.dependencies.to_string())
        if not _write:
            print("\nExiting without writing to file")
            # print(fmt.dependencies.to_string())
            final_text = fmt._as_text()
            self._display_text_syntax(final_text, format)
            return
        print(f"\nWriting to file: {path}")
        fmt.dump(path)
