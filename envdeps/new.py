import sys
from collections import defaultdict
from importlib.metadata import Distribution
from pathlib import Path

from loguru import logger

from envdeps.common import Dependency, OutputFormat, PathOrStr
from envdeps.formats import Pyproj, Requirements
from envdeps.main import SpecifierMode
from envdeps.parse import collect_target_dir_imports
from envdeps.pkgs import (
    get_env_site_dir,
    get_installed_dists,
    get_top_level_imports,
    resolve_active_env_prefix,
)
from envdeps.reqs import _parse_requirement
from envdeps.utils import EnvDepsException, format_table, import_is_local

DEFAULT_IGNORES = ["__pycache__", "resources"]


def topath(p: PathOrStr, resolve: bool = True):
    if isinstance(p, str):
        p = Path(p)
    if resolve:
        p = p.expanduser().resolve()
    return p


class DependencyAnalyzer:
    """Scan used dependencies in a given python project, optionally writing to
    or merging with an existing dependency file (requirements.txt or
    pyproject.toml)

    Before accessing the scanned `dependencies` property, you must first call the following (in order)::

        da = DependencyAnalyzer(...)
        da.get_environment_packages()
        da.scan_project_imports()
        da.get_used_dependencies()
        print(da.dependencies)

    Attributes:
        prefix: Python environment prefix for the given project.
        target_dir: Directory containing source files
        root: Root of the project directory (defaults to CWD)
        ignore_dirs: List of directories to ignore (defaults: [__pycache__, resources])
        mode: Version specifier operator to use for writing deps. (default to '>=')
    """

    def __init__(
        self,
        prefix: PathOrStr | None,
        target_dir: PathOrStr,
        root: PathOrStr,
        ignore_dirs: list[str] = DEFAULT_IGNORES,
        mode: SpecifierMode = ">=",
    ) -> None:
        if prefix is None:
            prefix = resolve_active_env_prefix()
        if prefix is None:
            raise ValueError("Prefix cannot be None")
        # Public attrs
        self.prefix = prefix
        self.target_dir = topath(target_dir)
        self.root = topath(root)
        self.ignore_dirs = ignore_dirs
        self.mode = mode

        # Private attributes
        self._dists: list[Distribution] = []
        self._imports: set[str] = set()
        # A mapping of distribution name to a set of the package imports found
        # from scanning project.
        self._package_imports: dict[Distribution, set[str]]
        # Used to check if requisite methods have been called.
        # Cant check 'self._imports/_dists' because might be empty after still
        # having been scanned
        self._called_state = defaultdict(bool)

    def _missing_steps(self):
        not_called = []
        for meth in [
            "get_environment_packages",
            "scan_project_imports",
            "get_used_dependencies",
        ]:
            if self._called_state[meth] is False:
                not_called.append(meth)
        return not_called
        # if not not_called:
        #     return
        #
        # if not_called:
        #     caller_frame = inspect.stack()[1]
        #     caller_func = caller_frame.function
        #     methods_not_called = ' & '.join([f"'{i}()'" for i in not_called])
        #     raise EnvDepsException(f"Must call: {methods_not_called} before calling {caller_func}.")

    #
    # def _not_ready_exception(self):

    def get_environment_packages(self):
        site_dirs = get_env_site_dir(self.prefix)
        dists = get_installed_dists(site_dirs)
        self._dists = dists
        self._called_state["get_environment_packages"] = True

    def scan_project_imports(
        self,
    ):
        imports = collect_target_dir_imports(self.target_dir, self.ignore_dirs)
        # Filtering stdlib module names from imports
        imports = set(filter(lambda i: i not in sys.stdlib_module_names, imports))

        self._imports = imports
        self._called_state["scan_project_imports"] = True

    def get_used_dependencies(self):
        if (
            self._called_state["scan_project_imports"] is False
            or self._called_state["get_environment_packages"] is False
        ):
            raise EnvDepsException(
                "Must call both 'get_environment_packages()' and 'scan_project_imports()' first before 'get_used_dependencies()'"
            )
        if not all([self._imports, self._dists]):
            culprits = []
            if not self._imports:
                culprits.append("self._imports")
            if not self._dists:
                culprits.append("self._dists")
            raise EnvDepsException(
                f"Error: '{' & '.join(culprits)}' empty. Cannot get used dependencies."
            )
        dists_used = []
        package_imports = {}
        imports = self._imports.copy()
        for dist in self._dists:
            dist_imports = set(get_top_level_imports(dist))
            # Get package imports that are in project imports
            same = imports & dist_imports
            # remove those 'same' imports from the project imports list.
            imports -= dist_imports
            if same:
                # package_imports[dist.name] = same
                dists_used.append(dist)
                package_imports[dist] = same
        if imports:
            # If any imports leftover
            logger.debug(f"Leftover imports: {imports}")
            imports = self._remove_local_imports(imports)
            if imports:
                print(
                    f"Could not resolve these imports from packages or locally:\n{imports}"
                )
        # print("Package imports:")
        # for d, imps in package_imports.items():
        #     print(d.name, imps)
        self._package_imports = package_imports
        # for dist in self._dists:
        #     pass
        self._called_state["get_used_dependencies"] = True

    def _remove_local_imports(self, leftover_imports: set[str]):
        """Remove import names from local modules in the project.

        Args:
            leftover_imports: Leftover imports after filtering out 1. stdlib module names, and 2. installed package modules.

        Returns:
            Ghost imports: Unknown import names not attributed to an installed package or a local module. (Hopefully, this is empty.)
        """
        imports = leftover_imports.copy()
        for import_name in leftover_imports:
            if import_is_local(self.root, import_name, self.ignore_dirs):
                imports.remove(import_name)
        _found_local_imports = leftover_imports.difference(imports)
        if _found_local_imports:
            logger.debug(f"Found local imports: {_found_local_imports}")
        return imports

    @property
    def dependencies(self) -> list[Dependency]:
        if not self._package_imports:
            if not self._called_state["get_used_dependencies"]:
                raise EnvDepsException(
                    "Must call 'get_environment_packages()', 'scan_project_imports()', then 'get_used_dependencies()' before accessing dependencies."
                )
            else:
                raise EnvDepsException(
                    "Error collecting packages of project imports ('self._package_imports' is None)"
                )
        deps = []
        for dist in self._package_imports:
            deps.append(Dependency.from_dist(dist, self.mode))
        return deps

    def _get_output_format_object(
        self, format: OutputFormat, fpath: Path | None = None, text: str | None = None
    ):
        """Get the given output format object based on the specified 'format'.
        There is NO default `fpath` used here, so a default must be created
        beforehand (if desired) and passed to this. Otherwise, a new output
        format will be made with no existing dependencies.

        Instead of a `fpath` with dependencies, a `str` contaning dependencies (formatted according to `format`) can be provided instead.

        Args:
            format: Format type
            fpath: Filepath of existing file to read dependencies from (either a 'requirements.txt' or 'pyproject.toml') (default None)
            text: String containing dependencies in the format of `format`. Cannot be used along with `fpath`.

        Returns:
            Pyproj | Requirements: Format object specified.
        """
        if format == "pyproject.toml":
            format_typ = Pyproj
        else:
            format_typ = Requirements
        if fpath is None or not fpath.exists():
            return format_typ("")
        return format_typ.from_file(fpath)

    def write_to_file(
        self,
        format: OutputFormat,
        merge: bool,
        fpath: Path | None = None,
        remove_unknown: bool = False,
        remove_unused: bool = True,
        update_existing: bool = False,
        _write: bool = True,
    ):
        """Write the scanned dependencies to a dependency file (either
        'requirements.txt' or 'pyproject.toml'), specifying options to control
        how they are merged with existing dependencies in the file. If file
        doesn't exist or is empty, it will be written accordingly.

        Args:
            format: Type of output file (requirements.txt or pyproject.toml)
            merge: Whether to merge scanned deps with existing deps from `fpath`
            fpath: Path to output file.
            remove_unknown: Remove 'unknown' dependencies (those that are not the typical)
            remove_unused: [TODO:description]
            update_existing: [TODO:description]
            _write: [TODO:description]
        """
        if not self.dependencies:
            print("No Scanned dependencies. Nothing to write.")
            return
        if fpath is None:
            fpath = self.root.joinpath(format)
        if format == "pyproject.toml":
            reqs = Pyproj.from_file(fpath)
        else:
            reqs = Requirements.from_file(fpath)
        # if not fpath.exists() or not reqs.text.strip() or not reqs.dependencies:
        #     logger.info(
        #         "Either path does not exist, reqs.text is None, or reqs.dependencies is None. Write the dependencies without needing to merge."
        #     )
        #     pass
        if not merge:
            reqs.dependencies = self.dependencies
        else:
            reqs.update_dependencies(
                self.dependencies,
                remove_unused=remove_unused,
                update_existing=update_existing,
                remove_unknown=remove_unknown,
            )
        if not _write:
            print("\nNot writing file. Merged dependencies:")
            print(*reqs.dependencies, sep="\n")
            return
        write_path = reqs.write_file(fpath)
        print(f"\nNew Requirements successfully writen to: {write_path}")

    # def write_requirements(
    #     self,
    #     fpath: Path | None,
    #     remove_unused: bool = True,
    #     remove_unknown: bool = False,
    # ):
    #     if fpath is None:
    #         fpath = self.root.joinpath("requirements.txt")
    #     if not fpath.exists():
    #         deps = [str(dep) for dep in self.dependencies]
    #         write_lines(fpath, deps)
    #         return fpath
    #     with open(fpath, "r") as f:
    #         text = f.read()
    #     if not text.strip():
    #         write_lines(fpath, [str(dep) for dep in self.dependencies])
    #         return fpath
    #     req_lines = text.splitlines()
    #     final_reqs = []
    #     for req in req_lines:
    #         new_req = compare_req(req, self.dependencies, remove_unknown, remove_unused)
    #         if new_req:
    #             final_reqs.append(str(new_req))
    #     write_lines(fpath, final_reqs)
    #     print(f"Dependencies written to: {fpath}")
    #     return fpath

    def view_imports(self):
        missing_calls = self._missing_steps()
        if missing_calls:
            methods_not_called = " & ".join([f"'{i}()'" for i in missing_calls])
            raise EnvDepsException(
                f"Must call {methods_not_called} before calling 'view_imports'."
            )
        if not self._package_imports:
            raise ValueError("'self._package_imports' is empty.")
        pkg_names, import_sets = [], []
        for dist, imports in self._package_imports.items():
            pkg_names.append(dist.name)
            import_sets.append(", ".join(imports))
        format_table(pkg_names, import_sets, header=["Package", "Used imports"])


def compare_req(
    line: str, deps: list[Dependency], remove_unknown: bool, remove_unused: bool
):
    req = _parse_requirement(line)
    if isinstance(req, str):
        # If str, it is either comment or non-standard format
        if remove_unknown:
            # if we remove unknown, return None to final list
            return None
        # else, keep and return unknown to final list
        return req
    # Check that this 'Requirement' is in our scanned dependencies
    for dep in deps:
        if dep.compare(req):
            return dep
    if not remove_unused:
        return req
    return None

    # If we are here, the requirement IS a standard requirement, but
    # is NOT found in the scanned dependencies.
    # If `remove_unused==True`, return it anyways. Otherwise ignore it.
    # return


def write_lines(file, lines: list[str]):
    with open(file, "w") as f:
        f.write("\n".join(lines))
    return file


# def analyze_project_dependencies(
#     prefix: PathOrStr | None,
#     target_dir: PathOrStr,
#     project_root: PathOrStr,
#     ignore_dirs: list[str],
# ):
#     pass
