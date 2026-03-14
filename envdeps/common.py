from importlib.metadata import Distribution
from pathlib import Path
from typing import Iterator, Literal

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from envdeps.pkgs import PkgInfo, normalize

type PathOrStr = Path | str

OutputFormat = Literal["requirements.txt", "pyproject.toml"]


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
