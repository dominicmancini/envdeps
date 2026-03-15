# pyright: reportIncompatibleMethodOverride=hint
from __future__ import annotations

from collections.abc import MutableSet
from importlib.metadata import Distribution
from typing import Iterable, Iterator, Self

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name


class PackageRequirement(Requirement):
    """Subclass of 'Requirement' that provides shallow comparisons (name-only
    equality semantics).

    Two PackageRequirements are 'equal' if they refer to the same
    package, regardless of version specifier, URL, or markers. Use
    `deep_equal()` for a full field-by-field comparison.
    """

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Requirement):
            try:
                return self.__eq__(PackageRequirement(str(other)))
            except InvalidRequirement:
                return NotImplemented
        return canonicalize_name(self.name) == canonicalize_name(other.name)

    @classmethod
    def from_dist(cls, dist: Distribution, mode: str):
        req_str = f"{dist.name}"
        if mode != "":
            req_str = f"{dist.name}{mode}{dist.version}"
        return cls(req_str)

    def __hash__(self) -> int:
        return hash(canonicalize_name(self.name))

    def deep_equal(self, other: object):
        if not isinstance(other, Requirement):
            try:
                other = PackageRequirement(str(other))
            except InvalidRequirement:
                return NotImplemented
        return (
            canonicalize_name(self.name) == canonicalize_name(other.name)
            and self.extras == other.extras
            and self.specifier == other.specifier
            and self.url == other.url
            and self.marker == other.marker
        )


class RequirementSet(MutableSet[PackageRequirement]):
    """Ordered, deduplicated collection of requirements.

    Deduplication is by canonical package name. Provides basic set
    operations on RequirementSet objects.

    Use `.merge()` to merge RequirementSet's, choosing whether to keep
    or update version specifiers from existing dependencies.
    """

    def __init__(self, requirements: Iterable[PackageRequirement | str] = ()) -> None:
        self._reqs: dict[str, PackageRequirement] = {}
        for req in requirements:
            self.add(req)

    def __contains__(self, item: object) -> bool:
        if isinstance(item, str):
            return canonicalize_name(item) in self._reqs
        if isinstance(item, Requirement):
            return canonicalize_name(item.name) in self._reqs

        return False

    def __iter__(self) -> Iterator[PackageRequirement]:
        return iter(self._reqs.values())

    def __len__(self) -> int:
        return len(self._reqs)

    @classmethod
    def from_dists(cls, dists: list[Distribution], mode: str) -> Self:
        return cls([PackageRequirement.from_dist(dist, mode) for dist in dists])

    @classmethod
    def from_requirements(cls, path: str) -> tuple[Self, list[str]]:
        """Parse RequirementSet from a 'requirements.txt' file. This parses
        each line, adding it to the 'RequirementSet' if valid, or adding it to
        a list of unknown strings if could not parse.

        > NOTE: Despite being a class method, this returns 2 values.

        Args:
            path: 'requirements.txt' path

        Returns:
            RequirementSet and list[str] (Unknown entries)
        """
        reqs: list[PackageRequirement] = []
        unknown: list[str] = []
        with open(path, "r") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    dep = PackageRequirement(line)
                    reqs.append(dep)
                except InvalidRequirement:
                    unknown.append(line)
        return cls(reqs), unknown

    def add(self, value: PackageRequirement | str) -> None:
        """Add a requirement, replacing any existing entry for the same
        package."""
        if isinstance(value, str):
            value = PackageRequirement(value)
        elif not isinstance(value, PackageRequirement):
            # Transparently wrap a plain Requirement in our subclass
            value = PackageRequirement(str(value))
        self._reqs[canonicalize_name(value.name)] = value

    def discard(self, value: PackageRequirement | str) -> None:
        if isinstance(value, str):
            key = canonicalize_name(value)
        else:
            key = canonicalize_name(value.name)
        self._reqs.pop(key, None)

    # for lookup
    def get(self, name: str) -> PackageRequirement | None:
        return self._reqs.get(canonicalize_name(name))

    def __getitem__(self, name: str) -> PackageRequirement:
        try:
            return self._reqs[canonicalize_name(name)]
        except KeyError:
            raise KeyError(f"No requirement found for package: {name!r}")

    def merge(self, other: "RequirementSet", update: bool = True) -> "RequirementSet":
        """Return a new RequirementSet combining both sets.

        When `update == True`(default): When the same package appears in
        both, `other` takes precedence and gets updated.

        When `update == False`, the package from this set is kept.
        """
        merged = RequirementSet(self)
        for req in other:
            if req in merged and not update:
                continue
            merged.add(req)
        return merged

    def intersection(self, other: "RequirementSet") -> "RequirementSet":
        """Return requirements whose package names appear in _both_ sets.

        The specifier from `self` is kept for packages present in both.
        """
        return RequirementSet(req for req in self if req in other)

    def difference(self, other: "RequirementSet") -> "RequirementSet":
        """Return requirements in `self` whose package names are not in
        `other`.

        '*Whats in A but not in B at all?*'
        """
        return RequirementSet(req for req in self if req not in other)

    def conflicts(self, other: "RequirementSet") -> "RequirementSet":
        """Return requirements present in both sets but with differing
        specifiers. 'Whats in both A and B but disagrees on the version?'.

        A 'conflict' means the same package is pinned to
        incompatible/different version specs (using deep_equal to detect
        actual differences).
        """
        result = RequirementSet()
        for req in self:
            other_req = other.get(req.name)
            if other_req is not None and not req.deep_equal(other_req):
                result.add(req)
        return result

    def is_subset_of(self, other: "RequirementSet") -> bool:
        """True if every package in self also appears in other (name-only
        check)."""
        return all(req in other for req in self)

    def is_deeply_equal(self, other: "RequirementSet") -> bool:
        """True if both sets contain exactly the same requirements with the
        same specs."""
        if len(self) != len(other):
            return False
        for req in self:
            other_req = other.get(req.name)
            if other_req is None or not req.deep_equal(other_req):
                return False
        return True

    def update_merge(
        self, new: RequirementSet, remove_unused: bool, update_existing: bool
    ):
        """Update this RequirementSet (representing 'old' reqs read from a
        requirements.txt/etc file) with the new RequirementSet from a Scan.

        All 'new_reqs' are kept, with optional arguments to control how the reqs are merged.

        Args:
            new: The new RequirementSet to merge `self` with.
            remove_unused: Remove `self` deps that are not found in the `new_deps` set? (Default True).
            update_existing: Use the PackageRequirement from `new_deps` when the same package is found in `self` and `new_deps`? (Default True).

        Returns:
            Merged RequirementSet.
        """
        keep_unused = not remove_unused
        use_old_version = not update_existing
        merged = RequirementSet(new)
        for old_dep in self:
            if old_dep in merged:
                if use_old_version:
                    # Replace scanned version with OG version
                    merged.add(old_dep)
                else:
                    continue
            else:
                if keep_unused:
                    merged.add(old_dep)
        return merged

    # --- Dunder helpers ------------------------------------------------------

    def __or__(self, other: "RequirementSet") -> "RequirementSet":
        """Self | other  →  merge (other takes precedence)."""
        return self.merge(other)

    def __and__(self, other: "RequirementSet") -> "RequirementSet":
        """Self & other  →  intersection."""
        return self.intersection(other)

    def __sub__(self, other: "RequirementSet") -> "RequirementSet":
        """self - other  →  difference."""
        return self.difference(other)

    def __eq__(self, other: object) -> bool:
        """Shallow equality: same package names, regardless of specifiers."""
        if not isinstance(other, RequirementSet):
            return NotImplemented
        return set(self._reqs.keys()) == set(other._reqs.keys())

    def __repr__(self) -> str:
        reqs = ", ".join(str(r) for r in self)
        return f"RequirementSet([{reqs}])"
