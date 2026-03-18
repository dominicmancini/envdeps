import json
import os
import site
import sys
from dataclasses import dataclass, field
from importlib import metadata
from pathlib import Path
from pprint import pformat
from warnings import deprecated

from loguru import logger
from rich.pretty import pretty_repr
from rich.table import Table

from envdeps.common import DEFAULT_IGNORES
from envdeps.dependencies import Dependency, RequirementSet
from envdeps.pkgs import get_top_level_imports
from envdeps.scanner import FileImports, ImportSet
from envdeps.utils import import_is_local


def dist_repr(self):
    return self.name


@dataclass
class ResolvedDependency:
    dist: metadata.Distribution
    canonical_name: str
    version: str

    # maps top-level import name to files that use it
    import_usage: dict[str, set[str]] = field(default_factory=dict)

    def __repr__(self) -> str:
        name = self.canonical_name
        usage = pformat(self.import_usage, indent=2)
        s = f"ResolvedDependency(\n\tname={name},\n\tversion={self.version},\n\timport_usage={usage}\n)"
        #
        return s

    # def __repr__(self) -> str:
    #     obj = {"dist": self.dist.name, "import_usage": self.import_usage}
    #     return pformat(obj)

    @property
    def all_files(self) -> set[str]:
        return {file for files in self.import_usage.values() for file in files}

    @property
    def imported_modules(self) -> list[str]:
        return list(self.import_usage.keys())


type DistMap = dict[str, metadata.Distribution]


class DependencyResolver:
    def __init__(
        self, prefix: Path, root: Path, ignore_dirs: list[str] = list(DEFAULT_IGNORES)
    ) -> None:
        # root & ignore_dirs are needed when resolving local imports
        self._root = root
        self._ignore_dirs = ignore_dirs
        if not prefix.exists():
            raise ValueError(f"Prefix path does not exist: {prefix}")
        self._prefix = prefix
        self._site_dirs = self._get_site_dirs(prefix)
        self.dist_map: DistMap = self._build_dist_map()
        self.resolved: dict[str, ResolvedDependency] = {}

    def _get_site_dirs(self, prefix: Path) -> list[str]:
        site_dirs = site.getsitepackages([str(prefix)])
        if not site_dirs:
            raise ValueError(f"Could not find site directories for prefix: {prefix}")
        return site_dirs

    def _build_dist_map(self) -> dict[str, metadata.Distribution]:
        dists = list(metadata.distributions(path=self._site_dirs))
        if not dists:
            raise ValueError(
                f"Could not find distributions from site_dirs: {self._site_dirs}"
            )
        dist_map: dict[str, metadata.Distribution] = {}
        for dist in dists:
            dist_imports = set(get_top_level_imports(dist))
            for dist_import in dist_imports:
                dist_map[dist_import] = dist
        # returns: {"sklearn": <Dist>, "requests": <Dist requests>}
        return dist_map

    def _is_stdlib_or_local(self, module_name: str) -> bool:
        return module_name in sys.stdlib_module_names or import_is_local(
            self._root, module_name, self._ignore_dirs
        )

    def add_import(self, module_name: str, source_file: Path | str):
        # 1. TODO: skip if stdlib or local
        # if import_is_local(self._root, module_name, self._ignore_dirs):
        #     return
        if self._is_stdlib_or_local(module_name):
            return

        source_file = str(source_file)

        # 2. find the distribution
        # dist = self.dist_map.get(module_name)
        dist = self.dist_map[module_name]
        pkg_name = dist.name if dist else module_name

        # 3. Get or create the ResolvedDependency object
        if pkg_name not in self.resolved:
            self.resolved[pkg_name] = ResolvedDependency(
                dist=dist, canonical_name=pkg_name, version=dist.version if dist else ""
            )
        # 4. record the usage
        self.resolved[pkg_name].import_usage.setdefault(module_name, set()).add(
            source_file
        )

    def to_requirement_set(self, mode: str = "") -> RequirementSet:
        # reqs = RequirementSet()
        reqs = set()
        for name, dep in self.resolved.items():
            reqs.add(Dependency.from_dist(dep.dist, mode))
        return RequirementSet(reqs)

    def to_json(self) -> str:
        """Serialize the packages to json, for the 'show' json format."""
        data = []
        for name, dep in self.resolved.items():
            data.append(
                {
                    "package": dep.canonical_name,
                    "version": dep.version,
                    "files": list(dep.all_files),
                    "is_stdlib": False,
                    "is_local": False,
                }
            )
        return json.dumps(data, indent=2)

    def to_table_data(self, verbose: bool = False) -> dict:
        data = {
            "Package": [],
            "Version": [],
            # "location": []
        }
        if verbose:
            data["Used in"] = []
        for name, dep in self.resolved.items():
            data["Package"].append(dep.canonical_name)
            data["Version"].append(dep.version)
            if verbose:
                n_files = len(dep.all_files)
                firstpath = list(dep.all_files)[0]
                firstpath = os.path.relpath(firstpath, self._root)
                # first = Path(list(dep.all_files)[0])
                # r = reprlib.Repr(maxset=15)
                # loc_str = r.repr_set(dep.all_files, 1)
                # data["Used in"].append(loc_str)
                # data["Used in"].append(f"{n_files} files.")
                data["Used in"].append(f"{firstpath} (+{n_files - 1})")
        # format_table(*data.values(), header=list(data.keys()))
        return data

    def to_table(self, verbose: bool = False):
        title = f"Scanned Packages in '{self._root.name}'"
        caption = f"Env: '{self._prefix.name}'"
        headers = ["Package", "Version"]
        if verbose:
            headers.append("Used in")
        tbl = Table(title=title, caption=caption)
        for header in headers:
            tbl.add_column(header=header)
        for name, dep in self.resolved.items():
            row = [dep.canonical_name, dep.version]
            if verbose:
                if dep.all_files:
                    files = list(dep.all_files)
                    first = files.pop(0)
                    files.insert(0, os.path.relpath(first))
                    # fs = list(os.path.relpath(files[0])) + files[1:]
                    f = pretty_repr(files, max_length=1)
                else:
                    f = ""
                row.append(f)
            tbl.add_row(*row)
        return tbl


@deprecated("Use 'DependencyResolver' (see 'envdeps/main.py')")
class Environment:
    """Class representing the project's python environment. This is used to
    find all the installed packages in the environment. The class:

        - Finds all packages installed in the environment
        - Filters stdlib and local module imports from scanned project imports.
        - Resolves specified project imports to the installed packages,
          filtering out stdlib & local module imports.

    Usage::

        all_imports, file_imports = ProjectScanner(...).scan()
        env = Environment(...)
        used_dists = env.scan_and_collect_packages(all_imports)

    Attributes:
        prefix: Python environment prefix path.
        root: Project root.
        ignore_dirs: List of directory names ignored.
        site_dirs: Python environment site directories.
        dists: Package 'Distribution' objects.
    """

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
        # self.package_imports = []
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

    # def filter_stdlib_imports(self, raw_imports: ImportSet) -> ImportSet:
    #     return set(filter(lambda i: i not in sys.stdlib_module_names, raw_imports))

    def resolve(self, raw_imports: set[str]) -> dict[metadata.Distribution, ImportSet]:
        """Resolve the installed distributions and their top-level imports from
        the list of raw imports. This automatically filters out imports from
        stdlib modules & local module imports.

        The returned distributions are all the ones used in the project.

        Args:
            raw_imports: Set of imports scanned from a project.

        Returns:
            used_dist_imports: dict mapping package Distribution objects to the import names for the package used in the project.

        Raises:
            RuntimeError: If no distributions were found during initialization (check params).
        """
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

    def _match_file_imports_to_package(
        self,
        imports: ImportSet,
        package_imports: dict[metadata.Distribution, ImportSet],
    ) -> dict[metadata.Distribution, ImportSet]:
        result = {}
        for dist, dist_imports in package_imports.items():
            matches = imports & dist_imports
            if matches:
                result[dist] = matches
        return result

    def get_package_imports_by_file(
        self,
        package_imports: dict[metadata.Distribution, ImportSet],
        file_imports: FileImports,
    ) -> dict[str, dict[metadata.Distribution, ImportSet]]:
        """Get the 'verbose' import information for the scanned file imports.
        For each scanned file's imports, this identifies which package each
        import came from.

        This maps each scanned file to a dictionary contaning the Dist

        Args:
            package_imports: The packages used in the project mapped to the imports.
            file_imports: A mapping of each scanned file to their filtered import set

        Returns:
            Mapping of files to a dict containing each Distribution to the set of imports in the file for it.
        """
        verbose_file_imports: dict[str, dict[metadata.Distribution, ImportSet]] = {}
        for file, imports in file_imports.items():
            dist_to_file_imports = self._match_file_imports_to_package(
                imports, package_imports
            )
            if dist_to_file_imports:
                verbose_file_imports[str(file)] = dist_to_file_imports
        return verbose_file_imports

    def _dist_imports_to_import_set(
        self, pkg_imports: dict[metadata.Distribution, ImportSet]
    ) -> ImportSet:
        import_set: ImportSet = set()
        for pkg, imports in pkg_imports.items():
            import_set.add(pkg.name)
        return import_set

    def scan_and_collect_packages(
        self, all_imports: ImportSet
    ) -> set[metadata.Distribution]:
        """Utility function to get the list of installed packages from the list
        of all scanned project imports.

        Args:
            all_imports: Set of project imports

        Returns:
            Set of Distribution objects for installed project packages.
        """
        dist_imports = self.resolve(all_imports)
        used_packages = set(dist_imports.keys())
        return used_packages
