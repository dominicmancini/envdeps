import site
import sys
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path

from loguru import logger

from envdeps.pkgs import get_top_level_imports
from envdeps.scanner import ImportSet
from envdeps.utils import import_is_local


# @dataclass
# class UsedProjectDeps:
#     name: str
#     dist: metadata.Distribution
#     imports: ImportSet
@dataclass
class TLPackageImport:
    dist: metadata.Distribution
    imports: set[str]


type TLImports = dict[str, TLPackageImport]


class Environment:
    def __init__(self, prefix: Path, root: Path, ignore_dirs: list[str]) -> None:
        if not prefix.is_absolute():
            prefix = prefix.expanduser().resolve()
        if not prefix.exists():
            raise FileNotFoundError("Prefix path doesn't exist.")
        self.prefix = prefix
        self.root = root
        self.ignore_dirs = ignore_dirs
        self.site_dirs = site.getsitepackages([str(self.prefix)])
        if not self.site_dirs:
            raise FileNotFoundError(
                f"Could not find site directories for prefix: {self.prefix}"
            )
        self.dists = self._get_installed_packages()
        self.package_imports = []
        # self.dists = list(metadata.distributions(path=self.site_dirs))
        # if not dists:
        #     raise ValueError(f"Could not find distributions from site_dirs: {site_dirs}")

    def _get_installed_packages(self):
        dists = list(metadata.distributions(path=self.site_dirs))
        if not dists:
            raise ValueError(
                f"Could not find distributions from site_dirs: {self.site_dirs}"
            )
        return dists

    def _filter_local_imports(self, leftover_imports: ImportSet):
        imports = leftover_imports.copy()
        for import_name in leftover_imports:
            if import_is_local(self.root, import_name, self.ignore_dirs):
                imports.remove(import_name)
        _found_local_imports = leftover_imports.difference(imports)
        if _found_local_imports:
            logger.debug(f"Found local imports: {_found_local_imports}")
        return imports

    def resolve(self, raw_imports: set[str]) -> dict[metadata.Distribution, ImportSet]:
        if not self.dists:
            raise RuntimeError(
                "`self.dists` is empty. Must call `get_installed_packages` first."
            )
        imports = set(filter(lambda i: i not in sys.stdlib_module_names, raw_imports))
        package_imports: dict[metadata.Distribution, ImportSet] = {}
        # top_level_imports: TLImports = {}
        for dist in self.dists:
            dist_imports = set(get_top_level_imports(dist))
            used_dist_imports = imports & dist_imports
            imports -= dist_imports
            if used_dist_imports:
                # top_level_imports[dist.name] = TLPackageImport(dist, imports)
                package_imports[dist] = used_dist_imports
        if imports:
            logger.debug(f"Leftover imports: {imports}")
            imports = self._filter_local_imports(imports)
            if imports:
                print(
                    f"Could not resolve these imports from packages or locally:\n{imports}"
                )
        return package_imports
