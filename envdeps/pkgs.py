import os
import re
import site
import sys
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Annotated

from packaging.version import Version


def normalize(name: str):
    return re.sub(r"[-_.]+", "-", name).lower()


@dataclass
class PkgInfo:
    name: Annotated[str, "Normalized Package name (for comparison)"]
    dist: Annotated[metadata.Distribution, "The Distribution object."]
    imports: Annotated[list[str], "Top Level Import names for package."]
    version: Version

    # def cmp(self, req: Requirement, ver: bool=True):
    #     if ver:
    #         for spec in req.specifier:
    #             if spec.contains(self.version):
    #         return (self.name == normalize(req.name))
    #     if not ver:
    #         return self.name == normalize(self.name)


def resolve_active_env_prefix() -> Path | None:
    venv_path = os.environ.get("VIRTUAL_ENV")
    if venv_path:
        return Path(venv_path)
    conda_path = os.environ.get("CONDA_PREFIX")
    if conda_path:
        return Path(conda_path)
    # NOTE: Pyenv env will also show as '$VIRTUAL_ENV',
    # but to check pyenv explicitly, do:
    pyenv_env = os.environ.get("PYENV_VIRTUAL_ENV")
    if pyenv_env:
        return Path(pyenv_env)

    # If all else fails, return sys.prefix
    if sys.prefix:
        return Path(sys.prefix)
    return None


def get_env_site_dir(env_prefix: Path | str) -> list[str]:
    if isinstance(env_prefix, str):
        env_prefix = Path(env_prefix)
    if not env_prefix.is_absolute():
        env_prefix = env_prefix.expanduser().resolve()
    if not env_prefix.exists():
        raise FileNotFoundError(f"Env Prefix does not exist: {env_prefix}")

    site_dirs = site.getsitepackages([str(env_prefix)])
    return site_dirs


def get_installed_dists(site_dirs: list[str]):
    if not site_dirs:
        raise ValueError("Site dirs empty")
    dists = list(metadata.distributions(path=site_dirs))
    if not dists:
        raise ValueError(f"Could not find distributions from site_dirs: {site_dirs}")
    return dists


def get_top_level_imports(dist: metadata.Distribution) -> list[str]:
    """Given a distribution, find the top-level imports for the package.
    This first checks if `top_level.txt` is available for dist, falling
    back to extracting names from module names in package.
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
            p.parts[0]
            for p in files
            if p.suffix == ".py" or (len(p.parts) > 1 and p.parts[1] == "__init__.py")
        }
        return list(roots)
    return []


def get_env_package_info(prefix: str | Path | None):
    if prefix is None:
        prefix = resolve_active_env_prefix()
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
        pkgs[norm_name] = PkgInfo(
            name=norm_name, dist=dist, version=version, imports=imports
        )
    return pkgs
