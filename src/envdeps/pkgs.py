import os
import re
import site
import sys
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from warnings import deprecated

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.version import Version

from envdeps.detection import detect_active_env


def normalize(name: str):
    return re.sub(r"[-_.]+", "-", name).lower()


@dataclass
class PkgInfo:
    """Class for convenient access to a package distribution object.

    Attributes:
        name (str): Normalized package name. (access `dist.name` for 'Project Name')
        dist (Distribution): Distribution object with information about package.
        imports (list[str]): List of the top-level package import names.
        version (Version): Version object which can be compared and etc.
    """

    name: str
    dist: metadata.Distribution
    imports: list[str]
    version: Version

    def __repr__(self) -> str:
        s = f"{self.name}"
        if self.version:
            s = f"{s}=={self.version}"
        return s

    def __eq__(self, other: object) -> bool:
        if isinstance(other, PkgInfo):
            names_eq = self.name == other.name
            version_eq = self.version == other.version
            return names_eq and version_eq
        elif isinstance(other, Requirement):
            return self.name == normalize(other.name)
        else:
            return NotImplemented

    def to_req(self, spec: str | SpecifierSet, validate: bool = False) -> Requirement:
        """Convert this `PkgInfo` into a `Requirement` object with the
        specified `SpecifierSet` or `str`. If spec is `str`, it should only be
        an operator (e.g., `>=`, `=`, etc.) and version will be taken from
        `PkgInfo.version`.

        Args:
            spec: str 'Operator' or `SpecifierSet` object.
            validate: When `True`, check that the `SpecifierSet` specifier contains the
            actual package version. If not, replace the Specifier version with real version.
            Does not apply when `type(spec) == str`.

        Returns:
            Requirement: The package and specifier in requirement form.
        """
        name = self.dist.name
        if isinstance(spec, str):
            if spec != "":
                spec = SpecifierSet(f"{spec}{self.version}")
        # TODO: Implement `validate` check for `spec` version contains `self.version`
        return Requirement(f"{name}{str(spec)}")

    def cmp(self, req: Requirement, version: bool = True):
        """Check if this package == a given `Requirement` entry.

        Args:
            req: Requirement entry, such as from a parsed 'pyproject.toml' dependencies.
            version: Check if versions are compatible (if requirement has Version) in
            addition to name?

        Returns:
            bool: True if these represent the same dependency specification. False if otherwise.
        """
        # first check normalized names are equal
        names_eq = self.name == normalize(req.name)
        if req.specifier and version:
            # if req has a specifier and we should compare version, return whether both
            # names and versions are equal
            return names_eq and req.specifier.contains(self.version)
        # otherwise, just check names are equal
        return names_eq


@deprecated("Use `envdeps.detection.detect_active_env`.")
def resolve_active_env_prefix(root: Path | None = None) -> Path | None:
    """Resolve the active python environment prefix.

    If `root` is provided, it will be used to resolve a virtual environment directory in the root of the project after first checking the environment variables.

    In order, the following are checked and returned if present:
    - `$VIRTUAL_ENV`: Used for when std `venv` is active.
    - `$PYENV_VIRTUAL_ENV`: Used when a `pyenv` version/virtualenv is activated
    - `$CONDA_PREFIX`: Used for the active conda.

    If none are found, we will search for a venv directory in the root of the project

    If all else fails, fallback to `sys.prefix`

    Returns:
        Path|None: Path to active venv prefix. (eg. `/home/user/.pyenv/versions/my_venv`)
    """
    # venv_path = os.environ.get("VIRTUAL_ENV")
    # if venv_path:
    #     return Path(venv_path)
    # # NOTE: Pyenv env will also show same as '$VIRTUAL_ENV',
    # # but to check pyenv explicitly, do:
    # pyenv_env = os.environ.get("PYENV_VIRTUAL_ENV")
    # if pyenv_env:
    #     return Path(pyenv_env)
    #
    # conda_path = os.environ.get("CONDA_PREFIX")
    # if conda_path:
    #     return Path(conda_path)

    for var in ["VIRTUAL_ENV", "CONDA_PREFIX", "PYENV_VIRTUAL_ENV"]:
        value = os.environ.get(var, None)
        if value is not None:
            return Path(value)

    if root:
        pyvenv_cfg = next(root.rglob("pyvenv.cfg"), None)
        if pyvenv_cfg is not None:
            return pyvenv_cfg.parent

    # Next, try to find a venv folder in the root of the project.
    # Because there may be different names, we will search for the 'pyvenv.cfg' file
    # that should be in venvs

    # If all else fails, return sys.prefix
    return Path(sys.prefix)


def get_env_site_dir(env_prefix: Path | str) -> list[str]:
    """Get the list of site directory paths for the current python prefix."""
    if isinstance(env_prefix, str):
        env_prefix = Path(env_prefix)
    if not env_prefix.is_absolute():
        env_prefix = env_prefix.expanduser().resolve()
    if not env_prefix.exists():
        raise FileNotFoundError(f"Env Prefix does not exist: {env_prefix}")

    site_dirs = site.getsitepackages([str(env_prefix)])
    return site_dirs


def get_installed_dists(site_dirs: list[str]) -> list[metadata.Distribution]:
    """Get the list of distributions installed in `site_dirs`."""
    if not site_dirs:
        raise ValueError("Site dirs empty")
    dists = list(metadata.distributions(path=site_dirs))
    if not dists:
        raise ValueError(f"Could not find distributions from site_dirs: {site_dirs}")
    return dists


def get_top_level_imports(dist: metadata.Distribution) -> list[str]:
    """Given a distribution, find the top-level imports for the package.

    This first checks if `top_level.txt` is available for dist, falling
    back to extracting module names from files in package.
    """
    top_level = dist.read_text("top_level.txt")
    if top_level:
        return top_level.strip().splitlines()

    # fallback to scanning 'RECORD' file
    files = dist.files
    if files:
        # get unique top-level directories/files that end in .py
        # or are dirs containing an __init__.py
        roots = {
            p.parts[0].removesuffix(".py")
            for p in files
            if p.suffix == ".py" or (len(p.parts) > 1 and p.parts[1] == "__init__.py")
        }
        return list(roots)
    return []


def get_env_package_info(prefix: str | Path | None):
    """Get information for packages installed in the given python environment
    as specified by `prefix`.

    Args:
        prefix: Path of the given python environment 'prefix'. Attempts to resolve
        if not provided (see :py:func:`resolve_active_env_prefix`)

    Returns:
        Mapping of normalized package names to :py:class:`PkgInfo` objects.

    Raises:
        ValueError: [TODO:throw]
    """
    if prefix is None:
        prefix = detect_active_env()
    assert prefix is not None, "Env Prefix is None"
    site_dirs = get_env_site_dir(prefix)
    if not site_dirs:
        raise ValueError(f"Could not find 'site_dirs' for env prefix: {prefix}")
    dists = get_installed_dists(site_dirs)
    pkgs: dict[str, PkgInfo] = {}
    for dist in dists:
        norm_name = normalize(dist.name)
        version = Version(dist.version)
        imports = get_top_level_imports(dist)
        pkgs[dist.name] = PkgInfo(
            name=dist.name, dist=dist, version=version, imports=imports
        )
        # pkgs[norm_name] = PkgInfo(
        #     name=norm_name, dist=dist, version=version, imports=imports
        # )
    return pkgs
