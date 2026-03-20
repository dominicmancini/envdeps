from itertools import zip_longest
from pathlib import Path
from typing import Sequence

import tomlkit
from loguru import logger


class EnvDepsException(Exception):
    pass


# Source - https://stackoverflow.com/a/287944
class bcolors:
    """Ansi escape codes for displaying colored text.

    Prefix text string with color, end each colored section by
    using `bcolors.ENDC`

    Usage::
        print(bcolors.WARNING + "ERROR: YOU DIED" + bcolors.ENDC)
    """

    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


ROOT_MARKERS = {
    ".git",
    ".gitignore",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "requirements.txt",
    "Pipfile",
    "poetry.lock",
    "manage.py",  # Django
    "tox.ini",
    "pytest.ini",
    ".pre-commit-config.yaml",
    "Cargo.toml",  # Sometimes Python projects are mixed with Rust
    ".venv",
    "venv",
    ".python-version",
}


def _obj_iterable(obj: object):
    return (
        hasattr(obj, "__iter__")
        and hasattr(obj, "__len__")
        and not isinstance(obj, str)
    )


def _fmt_obj_repr(obj: object, shorten: bool = True):
    type_name = type(obj).__name__
    args = vars(obj)
    attrs = []
    for name, value in args.items():
        if _obj_iterable(value) and shorten:
            value = f"{type(value).__name__}[{len(value)}]"
        attrs.append("%s=%r" % (name, value))
    attrs_str = ",\n\t".join(attrs)
    return f"{type_name}(\n\t{attrs_str}\n)"


def _validate_path(abs_path: Path, name: str, is_directory: bool = True) -> None:
    if not abs_path.exists():
        raise ValueError(f"{name} does not exist: {abs_path}.")

    if is_directory:
        if not abs_path.is_dir():
            raise ValueError(f"{name} is not a directory: {abs_path}")
    else:
        if not abs_path.is_file():
            raise ValueError(f"{name} is not a file: {abs_path}")


# NOTE: Basic aliases so that it is clear
# which path is which for `resolve_paths`
type RootPath = Path
type TargetPath = Path


def resolve_paths(
    root: Path | None, target: Path | None
) -> tuple[RootPath, TargetPath]:
    """Resolve the root and target path (as given from the cmdline arguments '
    --root' & '--target'), returning validated, absolute paths for both.

    - `target` and `root` default to `Path.cwd()` if not provided.
    - if `target` is relative, it is joined with `root` and validated
    - Once both made absolute, target is checked to be a child/inside of `root`.


    Args:
        root: Root directory of project to scan (default to CWD)
        target: Target directory containing source files to project to scan (default CWD)

    Returns:
        root, target: Resolved (absolute) and validated root and target paths.

    Raises:
        ValueError: If resolved path does not exist, is not a directory, or target is not a 'descendent'/child of root.
    """
    cwd = Path.cwd()

    # first, resolve root
    root = root if root else cwd
    root = root.expanduser().resolve()

    # Raise exception if not valid
    _validate_path(root, "--root", True)
    # if not root.exists():
    #     raise ValueError(f"--root does not exist: {root}")
    # if not root.is_dir():
    #     raise ValueError(f"--root is not a directory: {root}")

    # 2nd, resolve target
    if target:
        target = target.expanduser()
        if target.is_absolute():
            target = target.resolve()
        else:
            # NOTE: relative to root, not cwd
            target = (root / target).resolve()
    else:
        target = root  # Fallback to root

    # 3rd, validate
    _validate_path(target, "--target", True)

    # ensure target is child of root
    try:
        target.relative_to(root)
    except ValueError:
        raise ValueError(
            "--target must be the same or inside --root\n",
            f"root: {root}",
            f"target: {target}",
        )
    return root, target


def dep_list_to_pyproject(deps: list[str]) -> str:
    """Get a 'pyprojects.toml' formatted string from a list of string
    dependencies."""
    doc = tomlkit.document()
    project = tomlkit.table()
    project.add("dependencies", deps)

    doc["project"] = project
    return doc.as_string()


def format_table(*columns: Sequence, header: list = []):
    rows = list(zip_longest(*columns, fillvalue="-"))
    ncols = len(columns)
    if not header:
        header = [f"Col {i + 1}" for i in range(ncols)]
    elif len(header) < ncols:
        header.extend([f"Col {i + 1}" for i in range(len(header), ncols)])
    # dynamic col widths
    col_widths = []
    for i in range(ncols):
        col_data = [str(row[i]) for row in rows]
        max_w = max(len(str(header[i])), max((len(s) for s in col_data), default=0))
        col_widths.append(max_w + 2)
    output = []
    head_str = "".join(f"{str(h):<{col_widths[i]}}" for i, h in enumerate(header))
    output.append(head_str)
    output.append("-" * len(head_str))

    for row in rows:
        row_str = "".join(f"{str(item):<{col_widths[i]}}" for i, item in enumerate(row))
        output.append(row_str)
    print("\n".join(output))


def find_project_root(
    path: Path, markers: set[str] = ROOT_MARKERS, max_depth: int = 10
) -> Path | None:
    current = path.resolve()  # ensure absolute
    if current.is_file():
        current = current.parent

    for i in range(max_depth):
        for marker in markers:
            if (current / marker).exists():
                return current

        parent = current.parent

        if parent == current:
            break

        current = parent
    return None


def path_in_ignored_dir(path: Path, ignore_dirs: list[str]):
    """Checks if the given `path` is in an ignored directory. This checks all
    Path 'parts' for the dir names, and can be nested within the ignored dir.

    Works best with relative paths, as to not raise false positive for directories outside of the project 'scope'.
    E.g., if `ignore_dirs=['dev', 'resources']` and `path=~/dev/projects/my_project_root`, it would ignore all files because of parent directory `dev`.
    """
    return any(part for part in path.parts if part in ignore_dirs)


def import_is_local(root: Path, import_name: str, ignore_dirs: list[str]):
    """Check if the given import name is a local import from a module in the
    projects directory.

    Args:
        root: Project directory root path.
        import_name: import name as string
        ignore_dirs: list of directory names to ignore.
    """
    for file in root.rglob("**/*.py"):
        relfile = file.relative_to(root)

        is_ignored = any(part for part in relfile.parts if part in ignore_dirs)
        if is_ignored:
            continue
        # if path_in_ignored_dir(relfile, ignore_dirs):
        #     continue

        # loop through relative path parts, checking for import name in
        # directories and files (with '.py' removed).
        contains_import_name = any(
            part for part in relfile.parts if part.removesuffix(".py") == import_name
        )
        if contains_import_name:
            logger.debug(
                f"Found import '{import_name}' module in project at: {relfile}"
            )
            return True
    return False


def timer_decorator(func):
    """Utility decorator to time functions.

    Not used by any modules. Just for testing and stuff
    """
    import time
    from functools import wraps

    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        elapsed_time = end_time - start_time
        print(f"Function '{func.__name__}' executed in {elapsed_time:.4f} seconds")
        return result

    return wrapper
