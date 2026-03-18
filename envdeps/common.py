import argparse
from importlib.metadata import Distribution
from pathlib import Path
from typing import Callable, Iterator, Literal
from warnings import deprecated

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from envdeps.pkgs import PkgInfo, normalize, resolve_active_env_prefix
from envdeps.utils import resolve_paths

type PathOrStr = Path | str

OutputFormat = Literal["requirements.txt", "pyproject.toml"]

DEFAULT_IGNORES = {
    "__pycache__",
    ".venv",
    "venv",
    "env",
    "ENV",
    "build",
    "dist",
    ".eggs",
    "pip-wheel-metadata",
    ".pytest_cache",
    ".tox",
    ".nox",
    ".mypy_cache",
    ".pytype",
    ".ruff_cache",
    ".ipynb_checkpoints",
    ".git",
    ".hg",
    ".svn",
    ".idea",
    ".vscode",
    ".cache",
    "htmlcov",
}


class BaseCommand(argparse.Namespace):
    # NOTE: 'target', 'ignore', and 'root' may be None initially.
    # However, they should be `Path` after '_resolve_base_args()'
    # otherwise there is a problem (shouldn't happen).
    # Not doing 'Path|None' for type reasons.
    command: Literal["show", "export"]
    target: Path
    ignore: list[str]
    root: Path
    prefix: Path
    func: Callable[[argparse.Namespace], None]

    def _resolve_base_args(self):
        """Resolve and validate the base args.

        This provides the fallback/default values if they are not
        provided and validates path arguments.
        """
        resolved_root, resolved_target = resolve_paths(self.root, self.target)
        self.root, self.target = resolved_root, resolved_target
        if self.prefix is None:
            prefix = resolve_active_env_prefix()
            if not prefix:
                raise ValueError("Python Environment Prefix could not be resolved")
            self.prefix = prefix
        if not self.prefix.exists():
            raise ValueError(
                f"Environment prefix does not exist: {self.prefix}",
                "Check current environment prefix.",
            )
        self.ignore = list(DEFAULT_IGNORES.union(self.ignore))
        return self

    # func: Callable[[Self]] | None

    # def __repr__(self) -> str:
    #     rep = super().__repr__()
    #     rep = rep.replace("(", "(\n\t ", 1).replace(",", ",\n\t")
    #     return rep
    def __repr__(self) -> str:
        type_name = type(self).__name__
        args = vars(self)
        arg_strs = []
        for name, value in args.items():
            if isinstance(value, list):
                value = f"list[{len(value)}]"
            arg_strs.append("%s=%r" % (name, value))
        attrs_str = ",\n\t".join(arg_strs)
        return f"{type_name}(\n\t{attrs_str}\n)"
        # inner = "\n\t".join(i for i in arg_strs)


class ShowCommand(BaseCommand):
    format: Literal["text", "json", "table"]
    verbose: bool

    @classmethod
    def from_base(cls, args: BaseCommand):
        return cls(**vars(args))


class ExportCommand(BaseCommand):
    format: Literal["pyproject", "requirements"]
    merge: bool
    remove_unknown: bool
    remove_unused: bool
    update_existing: bool
    specifier: str | None = None

    @classmethod
    def from_base(cls, args: BaseCommand):
        return cls(**vars(args))


@deprecated("MOVING TO 'PackageRequirement'", category=Warning)
class Dependency(Requirement):
    @classmethod
    def from_dist(cls, dist: Distribution, mode: str):
        """Create a `Dependency` from a package distribution object and mode.

        Args:
            dist: Distribution package to format as dependency.
            mode: Operator used in version specifier. If empty string (""), no
            version specifier is used.

        Returns:
            Dependency: Dependency/Requirement object.
        """
        req_str = f"{dist.name}"
        if mode != "":
            req_str = f"{dist.name}{mode}{dist.version}"
        return cls(req_str)

    # @classmethod
    # def from_req(cls, req: Requirement):
    #     return cls(str(req))

    def verify_spec(self, dist: Distribution, check_version: bool = True):
        """Verify that this requirement spec is compatible with the actual
        distribution version.

        If `check_version == False`, only verify names match.
        """
        names_eq = self.name == dist.name
        if self.specifier and check_version:
            return names_eq and self.specifier.contains(dist.version)
        return names_eq

    @property
    def normalized_name(self):
        return normalize(self.name)

    def compare(self, req: Requirement):
        """Check if dependency and a requirement object represent the same
        dependency/package.

        This compares their normalized names.
        """
        norm_req = normalize(req.name)
        return norm_req == self.normalized_name

    def __eq__(self, other: object) -> bool:
        # NOTE: Modified version only checks that names are equal.
        # Original __eq__ checks for all attrs of 'Requirement'.
        # This applies to 'in' operator as well, allowing:
        # `Dependency('pandas>=1.2.0') in [Dependency('pandas)] == True`
        if isinstance(other, Requirement):
            return self.compare(other)
        elif isinstance(other, str):
            try:
                dep = Dependency(other)
                return self.__eq__(dep)
            except:
                return NotImplemented
        elif isinstance(other, Dependency):
            return self.normalized_name == other.normalized_name
        else:
            return super().__eq__(other)

    def _iter_skip_version(self, name: str) -> Iterator:
        """Copied from: [Packaging Requirements: _iter_parts](https://github.com/pypa/packaging/blob/e839d73030b410d4156e6a496249fbdb1e498fab/src/packaging/requirements.py#L58).
        This version is modified to skip yielding the specifier.
        """
        yield name

        if self.extras:
            formatted_extras = ",".join(sorted(self.extras))
            yield f"[{formatted_extras}]"

        # if self.specifier:
        #     yield str(self.specifier)

        if self.url:
            yield f" @ {self.url}"
            if self.marker:
                yield " "

        if self.marker:
            yield f"; {self.marker}"

    # TODO: Newly added, make sure this works as intended
    def __hash__(self) -> int:
        return hash(tuple(self._iter_skip_version(canonicalize_name(self.name))))

    def deep_compare(self, other: "Dependency"):
        """This performs the original __eq__ behavior of 'Requirement'. This
        considers specifier (version) along with all other original attributes.

        To compare just by name, use `==` or `verify_spec(..., check_version=False)`
        """
        return (
            canonicalize_name(self.name) == canonicalize_name(other.name)
            and self.extras == other.extras
            and self.specifier == other.specifier
            and self.url == other.url
            and self.marker == other.marker
        )


def get_dependencies(used_packages: dict[str, PkgInfo], mode: str):
    deps = []
    for name, pkg in used_packages.items():
        d = Dependency.from_dist(pkg.dist, mode)
        deps.append(d)
    return deps
