from pathlib import Path
from typing import Literal
from warnings import deprecated

from loguru import logger

import envdeps.output as output
import envdeps.parse as parse
import envdeps.pkgs as pkgs
from envdeps import utils
from envdeps.formats import Pyproj

# class SpecifierMode(StrEnum):
#     GT = ">="
#     EQ = "=="
#     COMPAT = "~="
#     _ = ""
type SpecifierMode = Literal[">=", "==", "~=", ""] | str


@deprecated("Try: `utils.import_is_local`.")
def is_local_import(import_name: str, root: Path):
    # NOTE: Local resolution happens in 3 ways:
    # 1. 'utilities.py' Just a single file module
    # 2. 'utilities/__init__.py' Package (dir with an `__init__.py`)
    # 3. 'utilities/' Namespace package (dir WITHOUT `__init__.py`)
    if (root / f"{import_name}.py").exists():
        print(root / f"{import_name}.py")
        return True
    # 2. Check for package directory
    pkg_dir = root / import_name
    if pkg_dir.is_dir():
        print(pkg_dir)
        return True

    # Try again searching, but recursively.
    if any(root.rglob(f"{import_name}/*.py")):
        return True
    if any(root.rglob(f"{import_name}.py")):
        return True

    return False


def _resolve_pyproject_path(target_dir: Path) -> Path | None:
    """Resolve pyproject.toml file by first looking in `target_dir`, falling
    back to looking in `Path.cwd()`.

    If neither found, return `None`.
    """
    pyproj = target_dir.joinpath("pyproject.toml")
    if pyproj.exists():
        return pyproj
    pyproj = Path.cwd().joinpath("pyproject.toml")
    if pyproj.exists():
        return pyproj
    return None


# def remove_local_imports(leftover_imports: set[str], target_dir: Path):
#     imports = leftover_imports.copy()
#     for i in leftover_imports:
#         if is_local_import(i, target_dir):
#             imports.remove(i)
#     return imports


def cross_ref_imports(
    pkg_infos: dict[str, pkgs.PkgInfo], imports: set[str]
) -> set[str]:
    removed_elements = set()
    for name, info in pkg_infos.items():
        tl_imports = set(info.imports)
        if not tl_imports:
            tl_imports = {name}
        if tl_imports.isdisjoint(imports):
            removed_elements.add(name)
        imports -= tl_imports
    print(f"Found and removed imports for these packages: {removed_elements}")
    return imports  # returns the leftover ones, which should be checked to be local modules


# type SpecifierMode = LiteralString[">=", "~=", "=="]


class ProjectDependencies:
    def __init__(
        self,
        prefix: Path | str | None,
        target_dir: Path,
        ignore_dirs: list[str],
        root: Path | None = None,
    ) -> None:
        if not prefix:
            prefix = pkgs.resolve_active_env_prefix()
        assert prefix is not None, "Could not determing env prefix."
        self.env_prefix = prefix
        self.target_dir = target_dir
        self.ignore_dirs = ignore_dirs
        self.project_root = self._resolve_project_root(root)
        self.pkg_info = pkgs.get_env_package_info(self.env_prefix)
        self._project_imports: set[str] = self._find_used_imports()
        self._unknown_imports: set[str] = set()
        # self.dependencies: list[Dependency] = self._get_dependencies()

    # def _get_dependencies(self, mode: SpecifierMode = ">="):
    #     used_pkgs = self.select_used_packages()
    #     return get_dependencies(used_pkgs, mode)

    def select_used_packages(self) -> dict[str, pkgs.PkgInfo]:
        """Filter all the environment packages (`self.pkg_info`) to just the
        ones used in the project (based on `self._project_imports`)."""
        if not self._project_imports:
            return {}
        used_packages_info = {
            k: v for k, v in self.pkg_info.items() if k in self._project_imports
        }
        return used_packages_info

    def _resolve_project_root(self, cwd: Path | None):
        """Resolve the project root such that `root + target_dir` exists. If
        not manually provided, the CWD is used as default.

        Args:
            cwd: Path to project root, or none (default `Path.cwd()`)

        Returns:
            Path: Resolved and validated Project root

        Raises:
            FileNotFoundError: If the `root.joinpath(self.target_dir)` does not exist (Regardless if specified or default cwd.)
        """
        if cwd is not None:
            cwd = cwd.expanduser().resolve()
            logger.debug(f"Explicitly provided cwd: {cwd}")
            if not cwd.joinpath(self.target_dir).exists():
                raise FileNotFoundError(
                    f"Could not resolve target dir '{self.target_dir}' with the provided project root: {cwd}. '{cwd.joinpath(self.target_dir)} does not exist'"
                )
            return cwd
        # cwd was not provided, assume cwd. Check that cwd + self.target_dirs
        # exists and use that, otherwise error.
        cwd = Path.cwd()
        joined_path = cwd.joinpath(self.target_dir)
        if not joined_path.exists():
            raise FileNotFoundError(
                f"Could not resolve target dirs ({self.target_dir}) with the cwd: {cwd}. If not in project root, please manually specify the path to the project root."
            )
        logger.info(f"Using user CWD. Joins with target dir: {cwd}")
        return cwd

    def _remove_local_imports(self, leftover_imports: set[str]):
        imports = leftover_imports.copy()
        for i in leftover_imports:
            if utils.import_is_local(self.project_root, i, self.ignore_dirs):
                logger.debug(f"Leftover is local: '{i}'. Removing.")
                imports.remove(i)
        return imports

    def _find_used_imports(self) -> set[str]:
        """Find imports in all source files (respecting `self.ignore_dirs`)
        from 3rd party libraries (filtering out stdlib modules)"""
        # all_imports = parse.collect_file_imports(self.target_dir, self.ignore_dirs)
        all_imports = parse.collect_target_dir_imports(
            self.target_dir, self.ignore_dirs
        )
        imports_3rd_party = parse.filter_stdlib_imports(all_imports)
        return imports_3rd_party

    def resolve_imported_packages(self) -> dict[str, set[str]]:
        """Resolve all the import statements in the source files with installed
        packages and local modules from the project dir (`target_dirs`).

        Returns:
            dict: Mapping of normalized package names to the import statements used in the target files.
        """
        used_pkg_imports = {}
        imports = self._project_imports.copy()
        for name, info in self.pkg_info.items():
            pkg_imports = set(info.imports)
            same = imports & pkg_imports
            imports -= pkg_imports
            if same:
                used_pkg_imports[name] = same
        if imports:
            logger.debug(f"Leftover Imports: {imports}")
            # imports = remove_local_imports(imports, self.target_dir)
            imports = self._remove_local_imports(imports)
            if imports:
                print(
                    f"Could not resolve these imports from packages or locally: {imports}"
                )
                self._unknown_imports.update(imports)
        return used_pkg_imports

    def _get_requirements(self, mode: str = ">=") -> list[str]:
        """Get a formatted list of requirements for `self.target_dirs`.

        The result is ready to be written to a 'requirements.txt' or
        printed to the console.
        """
        pkg_imports = self.resolve_imported_packages()
        pkg_list = [self.pkg_info[i] for i in pkg_imports]
        lines = []
        for pkg in pkg_list:
            lines.append(output.format_line(pkg, mode))
        return lines

    def write_reqs(
        self, fpath: Path, overwrite: bool = True, mode: SpecifierMode = ">="
    ):
        req_list = self._get_requirements(mode)
        if not req_list:
            raise ValueError("List of requirements is empty.")
        if overwrite == False:
            print(
                "Overwrite == False not yet implemented! Printing instead.\n\nNew Requirements:\n"
            )
            print(req_list, sep="\n")
            return
        reqs_str = "\n".join(req_list)
        with open(fpath, "w") as f:
            f.write(reqs_str)
        logger.info(f"Sucessfully wrote to requirements to {fpath}")

    def export_to_pyproject(
        self,
        fpath: Path | None,
        mode: SpecifierMode = ">=",
        overwrite: bool = True,
        create: bool = True,
    ):
        if fpath is None:
            fpath = self.project_root.joinpath("pyproject.toml")
        cfg = Pyproj.from_file(fpath)

    def update_pyproject(
        self,
        fpath: Path | None,
        mode: SpecifierMode = ">=",
        overwrite: bool = True,
        create: bool = True,
    ):
        """If `create=True` and no `fpath` is provided, this will default to
        creating pyproject.toml in CWD (as `self.target_dir` might not be
        project root.)"""
        if fpath is None:
            fpath = _resolve_pyproject_path(self.target_dir)
        if fpath is None:
            if not create:
                raise FileNotFoundError(
                    "Could not resolve path to existing pyproject.toml and `create` == False."
                )
            else:
                fpath = Path.cwd().joinpath("pyproject.toml")
        assert fpath is not None, (
            "Should not have reached this point with `fpath` as `None`"
        )
        reqs = parse.parse_pyproject_dependencies(fpath)

        # assert fpath is not None, f"Could not find pyproject.toml in {self.target_dir} or cwd: {Path.cwd()}"
