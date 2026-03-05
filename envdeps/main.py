from pathlib import Path
from typing import Literal

import envdeps.parse as parse
import envdeps.pkgs as pkgs

# class SpecifierMode(StrEnum):
#     GT = ">="
#     EQ = "=="
#     COMPAT = "~="
#     _ = ""
type SpecifierMode = Literal[">=", "==", "~=", ""] | str


def _resolve_pyproject_path(target_dir: Path) -> Path | None:
    """Resolve pyproject.toml file by first looking in `target_dir`, falling back to looking in `Path.cwd()`. If neither found, return `None`."""
    pyproj = target_dir.joinpath("pyproject.toml")
    if pyproj.exists():
        return pyproj
    pyproj = Path.cwd().joinpath("pyproject.toml")
    if pyproj.exists():
        return pyproj
    return None


# type SpecifierMode = LiteralString[">=", "~=", "=="]


class ProjectDependencies:
    def __init__(
        self, prefix: Path | str | None, target_dir: Path, ignore_dirs: list[str]
    ) -> None:
        if not prefix:
            prefix = pkgs.resolve_active_env_prefix()
        assert prefix is not None, "Could not determing env prefix."
        self.env_prefix = prefix
        self.target_dir = target_dir
        self.ignore_dirs = ignore_dirs
        self.pkg_info = pkgs.get_env_package_info(self.env_prefix)
        self._project_imports: set[str] = self.find_used_imports()

    def find_used_imports(self) -> set[str]:
        """Find imports in all source files (respecting `self.ignore_dirs`) from 3rd party libraries (filtering out stdlib modules)"""
        all_imports = parse.collect_file_imports(self.target_dir, self.ignore_dirs)
        imports_3rd_party = parse.filter_stdlib_imports(all_imports)
        return imports_3rd_party

    def update_pyproject(
        self,
        fpath: Path | None,
        mode: SpecifierMode = ">=",
        overwrite: bool = True,
        create: bool = True,
    ):
        """If `create=True` and no `fpath` is provided, this will default to creating pyproject.toml in CWD (as `self.target_dir` might not be project root.)"""
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


def analyze_dependencies(target_dir: Path, env_prefix: Path, ignore_dirs: list[str]):
    pass
