"""First iteration as script, before moving to module layout.
Just for reference, will be removed later.
"""

import ast
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List
from warnings import deprecated


@dataclass
class PkgInfo:
    name: str
    version: str | None = field(default=None)
    modules: list = field(default_factory=list)


def detect_active_venv() -> Path | None:
    venv_path = os.environ.get("VIRTUAL_ENV")
    if venv_path:
        return Path(venv_path)

    conda_path = os.environ.get("CONDA_PREFIX")
    if conda_path:
        return Path(conda_path)

    # NOTE: Pyenv env will also show as '$VIRTUAL_ENV',
    # but to check pyenv explicitly, do:
    # pyenv_env = os.environ.get("PYENV_VIRTUAL_ENV")
    # if pyenv_env:
    #     return Path(pyenv_env)
    return None


def new_get_site_package_dir(venv_path: Path):
    # patterns = [
    #     "lib/python*/site-packages"  # unix/linux,
    #     "Lib/site-packages",  # windows
    #     "lib/site-packages",  # some setups
    # ]
    site_dirs = list(venv_path.glob("lib/python*/site-packages", recurse_symlinks=True))
    if len(site_dirs) > 0:
        return site_dirs[0]
    return None
    # for pattern in patterns:
    #     matches = list(venv_path.glob(pattern, recurse_symlinks=True))
    #     print(f"{pattern=}, {matches=}")
    #     if matches:
    #         return matches[0]
    # return None


@deprecated("Use `new_get_site_package_dir`.")
def find_site_packages(venv_path: Path) -> Path | None:
    patterns = [
        "lib/python*/site-packages"  # unix/linux,
        "Lib/site-packages",  # windows
        "lib/site-packages",  # some setups
    ]
    for pattern in patterns:
        matches = list(venv_path.glob(pattern, recurse_symlinks=True))
        if matches:
            return matches[0]
    return None


def get_installed_packages(venv_path: Path) -> Dict[str, Dict[str, Any]]:
    """
    Get installed packages by reading .dist-info directories directly
    No need to import or execute anything from the target environment
    """
    site_packages = new_get_site_package_dir(venv_path)
    if not site_packages or not site_packages.exists():
        return {}

    packages = {}

    # Look for .dist-info and .egg-info directories
    for dist_info in site_packages.glob("*.dist-info"):
        package_name = dist_info.name.rsplit("-", 1)[0]
        version = None
        top_level_modules = []

        # Read METADATA file for version
        metadata_file = dist_info / "METADATA"
        if metadata_file.exists():
            with open(metadata_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("Version:"):
                        version = line.split(":", 1)[1].strip()
                        break

        # Read top_level.txt for module names
        top_level_file = dist_info / "top_level.txt"
        if top_level_file.exists():
            with open(top_level_file, "r", encoding="utf-8") as f:
                top_level_modules = [line.strip() for line in f if line.strip()]

        packages[package_name.lower()] = {
            "name": package_name,
            "version": version,
            "modules": top_level_modules,
        }

    # Also check .egg-info directories (older format)
    for egg_info in site_packages.glob("*.egg-info"):
        if egg_info.is_dir():
            parts = egg_info.name.rsplit("-", 1)
            package_name = parts[0]
            version = parts[1].replace(".egg-info", "") if len(parts) > 1 else None

            top_level_modules = []
            top_level_file = egg_info / "top_level.txt"
            if top_level_file.exists():
                with open(top_level_file, "r", encoding="utf-8") as f:
                    top_level_modules = [line.strip() for line in f if line.strip()]

            packages[package_name.lower()] = {
                "name": package_name,
                "version": version,
                "modules": top_level_modules,
            }

    return packages


def find_imports_in_file(file_path: Path) -> set:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split(".")[0])

        return imports
    except Exception as e:
        print(f"Error parsing {file_path}: {e}", file=sys.stderr)
        return set()


def find_imports_in_project(project_path: Path) -> set:
    all_imports = set()
    for py_file in project_path.rglob("*.py"):
        if any(
            part in py_file.parts
            for part in ["venv", ".venv", "env", "__pycache__", ".git"]
        ):
            continue
        all_imports.update(find_imports_in_file(py_file))
    return all_imports


def match_imports_to_packages(imports: set, packages: Dict) -> List[Dict]:
    """Match imported modules to installed packages"""
    results = []
    matched_imports = set()

    for import_name in imports:
        import_lower = import_name.lower()

        # Try direct package name match
        if import_lower in packages:
            results.append(packages[import_lower])
            matched_imports.add(import_name)
            continue

        # Try matching against top-level modules
        for pkg_name, pkg_info in packages.items():
            if import_name in pkg_info["modules"]:
                results.append(pkg_info)
                matched_imports.add(import_name)
                break

    # Report unmatched imports
    unmatched = imports - matched_imports
    if unmatched:
        print(
            f"\nWarning: Could not match these imports to packages: {', '.join(sorted(unmatched))}"
        )

    return results


def main():
    # Detect active virtual environment
    venv_path = detect_active_venv()

    if not venv_path:
        print("No virtual environment detected!")
        print("Activate a virtual environment or specify one with --venv")
        sys.exit(1)

    print(f"Detected virtual environment: {venv_path}")
    if not venv_path.is_absolute():
        venv_path = venv_path.expanduser().resolve()

    # Get installed packages from the venv
    installed_packages = get_installed_packages(venv_path)
    print(f"Found {len(installed_packages)} installed packages")

    # Find imports in current project
    project_path = Path.cwd()
    print(f"\nScanning project: {project_path}")
    imports = find_imports_in_project(project_path)
    print(f"Found {len(imports)} unique imports")

    # Match imports to packages
    used_packages = match_imports_to_packages(imports, installed_packages)

    # Output results
    print("\n=== Used Packages ===")
    for pkg in sorted(used_packages, key=lambda x: x["name"].lower()):
        version = pkg["version"] or "unknown"
        print(f"{pkg['name']}=={version}")


if __name__ == "__main__":
    main()
