# pyright: reportIncompatibleMethodOverride=hint
from __future__ import annotations

from dataclasses import dataclass, field
from importlib.metadata import Distribution
from typing import Iterable, Iterator, MutableSet

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


@dataclass(frozen=True)
class RawRequirement:
    raw: str
    reason: str = field(default="unparseable", compare=False)

    def __str__(self):
        return self.raw


AnyRequirement = PackageRequirement | RawRequirement


class RequirementSet(MutableSet[AnyRequirement]):
    """An ordered collection of requirements that tolerates unparseable lines.

    Parsed requirements are deduplicated by canonical package name. Raw
    (unparseable) lines are kept verbatim and are never deduplicated —
    they appear in the output exactly as they were read in.

    The class maintains a single ordered sequence of AnyRequirement
    entries, so round-tripping a requirements.txt (including comments,
    options, and unknown lines) produces output in the original order.
    """

    def __init__(self, requirements: Iterable[AnyRequirement | str] = ()) -> None:
        # Ordered list of all entries (parsed + raw), preserving source order.
        self._entries: list[AnyRequirement] = []
        # Fast name-keyed lookup for parsed requirements only.
        self._parsed: dict[str, PackageRequirement] = {}
        for req in requirements:
            self.add(req)

    # --- Construction helpers ------------------------------------------------

    @classmethod
    def from_requirements_txt(cls, path: str) -> "RequirementSet":
        """Parse a requirements.txt, preserving all lines including
        unknowns."""
        rs = cls()
        with open(path) as f:
            for raw_line in f:
                line = raw_line.rstrip("\n")
                stripped = line.strip()

                # Blank lines and comments: keep verbatim as RawRequirement.
                if not stripped or stripped.startswith("#"):
                    rs._append_raw(line, reason="comment_or_blank")
                    continue

                # pip options (-r, --index-url, etc.): keep verbatim.
                if stripped.startswith("-"):
                    rs._append_raw(line, reason="pip_option")
                    continue

                # Attempt to parse as a PEP 508 requirement.
                try:
                    rs.add(PackageRequirement(stripped))
                except InvalidRequirement as e:
                    rs._append_raw(line, reason=str(e))

        return rs

    @classmethod
    def from_installed(cls) -> "RequirementSet":
        """Build a RequirementSet from currently installed packages."""
        import importlib.metadata as metadata

        rs = cls()
        for dist in metadata.distributions():
            name = dist.metadata["Name"]
            version = dist.metadata["Version"]
            if name and version:
                rs.add(PackageRequirement(f"{name}=={version}"))
        return rs

    # --- Core mutation -------------------------------------------------------

    def add(self, value: AnyRequirement | str) -> None:
        """Add a requirement.

        - PackageRequirement / str: parsed and deduplicated by package name.
          Adding a duplicate name replaces the existing entry in-place (so
          the position in the ordered list is preserved).
        - RawRequirement: appended verbatim; never deduplicated.
        """
        if isinstance(value, RawRequirement):
            self._append_raw(value.raw, value.reason)
            return

        if isinstance(value, str):
            try:
                value = PackageRequirement(value)
            except InvalidRequirement as e:
                self._append_raw(value, reason=str(e))
                return

        # It's a PackageRequirement (or plain Requirement — wrap it).
        if not isinstance(value, PackageRequirement):
            value = PackageRequirement(str(value))

        key = canonicalize_name(value.name)
        if key in self._parsed:
            # Replace in-place: find and update the existing entry in _entries.
            self._parsed[key] = value
            for i, entry in enumerate(self._entries):
                if (
                    isinstance(entry, PackageRequirement)
                    and canonicalize_name(entry.name) == key
                ):
                    self._entries[i] = value
                    break
        else:
            self._parsed[key] = value
            self._entries.append(value)

    def discard(self, value: PackageRequirement | str) -> None:
        """Remove a parsed requirement by name (no-op if absent).

        Raw entries are never removed by this method.
        """
        key = canonicalize_name(value if isinstance(value, str) else value.name)
        if key in self._parsed:
            del self._parsed[key]
            self._entries = [
                e
                for e in self._entries
                if not (
                    isinstance(e, PackageRequirement)
                    and canonicalize_name(e.name) == key
                )
            ]

    def _append_raw(self, raw: str, reason: str) -> None:
        self._entries.append(RawRequirement(raw=raw, reason=reason))

    # --- Querying ------------------------------------------------------------

    def _try_parse_str(self, value: str):
        """Try to parse a string into a PackageRequirement.

        > NOTE: This should not be used for parsing entries in
        `RequirementSet`.

        This is only used when comparing with a string that may be a PackageRequirement.
        """
        try:
            return PackageRequirement(value)
        except InvalidRequirement:
            return value

    def get(self, name: str) -> PackageRequirement | None:
        """Return the parsed requirement for a package name, or None."""
        req = self._try_parse_str(name)
        if isinstance(req, PackageRequirement):
            name = req.name
        return self._parsed.get(canonicalize_name(name))

    def __contains__(self, item: object) -> bool:
        if isinstance(item, str):
            return canonicalize_name(item) in self._parsed
        if isinstance(item, Requirement):
            return canonicalize_name(item.name) in self._parsed
        return False

    def __len__(self) -> int:
        return len(self._entries)

    def __iter__(self) -> Iterator[AnyRequirement]:
        """Iterate all entries (parsed + raw) in source order."""
        return iter(self._entries)

    def iter_parsed(self) -> Iterator[PackageRequirement]:
        """Iterate only the successfully parsed requirements."""
        return iter(self._parsed.values())

    def iter_raw(self) -> Iterator[RawRequirement]:
        """Iterate only the unparseable / raw entries."""
        return (e for e in self._entries if isinstance(e, RawRequirement))

    def has_raw(self) -> bool:
        """True if there are any unparseable entries."""
        return any(True for _ in self.iter_raw())

    # --- Round-trip output ---------------------------------------------------

    def _get_fmt_output(self, include_unknown: bool) -> list[str]:
        """Get entries as list of strings, optionally include/exclude unknown
        entries."""
        if include_unknown:
            # Use both parsed/unparsed entries
            return [str(e) for e in self._entries]
        return [str(e) for e in self.iter_parsed()]

    def to_requirements_txt(self, path: str) -> None:
        """Write all entries back to a requirements.txt, preserving raw
        lines."""
        with open(path, "w") as f:
            for entry in self._entries:
                f.write(str(entry) + "\n")

    def to_string(self) -> str:
        """Return the full requirements.txt content as a string."""
        return "\n".join(str(e) for e in self._entries)

    # --- Set-like operations (operate only on parsed requirements) -----------

    def merge(self, other: "RequirementSet") -> "RequirementSet":
        """Return a new RequirementSet: parsed entries merged (other wins),
        raw entries from both appended after parsed entries."""
        result = RequirementSet(self.iter_parsed())
        for req in other.iter_parsed():
            result.add(req)
        # Raw entries from both are appended verbatim at the end.
        for raw in self.iter_raw():
            result._append_raw(raw.raw, raw.reason)
        for raw in other.iter_raw():
            result._append_raw(raw.raw, raw.reason)
        return result

    def difference(self, other: "RequirementSet") -> "RequirementSet":
        """Parsed requirements in self not present in other.

        Raw lines excluded.
        """
        return RequirementSet(r for r in self.iter_parsed() if r not in other)

    def conflicts(self, other: "RequirementSet") -> "RequirementSet":
        """Parsed requirements in both sets that differ in their full spec."""
        result = RequirementSet()
        for req in self.iter_parsed():
            other_req = other.get(req.name)
            if other_req is not None and not req.deep_equal(other_req):
                result.add(req)
        return result

    def __or__(self, other: "RequirementSet") -> "RequirementSet":
        return self.merge(other)

    def __sub__(self, other: "RequirementSet") -> "RequirementSet":
        return self.difference(other)

    def __eq__(self, other: object) -> bool:
        """Shallow equality on parsed package names only."""
        if not isinstance(other, RequirementSet):
            return NotImplemented
        return set(self._parsed.keys()) == set(other._parsed.keys())

    def __repr__(self) -> str:
        parsed = len(self._parsed)
        raw = sum(1 for _ in self.iter_raw())
        return f"RequirementSet({parsed} parsed, {raw} raw)"

    def __getitem__(self, name: str) -> PackageRequirement:
        if isinstance(name, PackageRequirement):
            name = name.name
        req = self._parsed.get(canonicalize_name(name))
        if req is None:
            raise KeyError(f"No requirement found for package: {name!r}")
        return req

    def update_merge(
        self,
        new: RequirementSet,
        remove_unused: bool = True,
        update_existing: bool = True,
        remove_unknown: bool = True,
    ):
        keep_unused = not remove_unused
        keep_old_version = not update_existing
        keep_unknown = not remove_unknown
        merged = RequirementSet(new)
        for old_dep in self:
            if isinstance(old_dep, RawRequirement):
                if keep_unknown:
                    merged.add(old_dep)
                    continue
                else:
                    continue
            if old_dep in merged:
                if keep_old_version:
                    merged.add(old_dep)
            else:
                if keep_unused:
                    merged.add(old_dep)
        return merged

    def is_subset_of(self, other: RequirementSet) -> bool:
        """True if every package in self also appears in other (name-only
        check)."""
        return all(req in other for req in self.iter_parsed())

    def _view(self):
        header = repr(self)
        width = len(header) + 10

        print(header.center(width, "-"))
        for req in self:
            # print(str(req).center(width))
            print(str(req))


# class RequirementSet(MutableSet[PackageRequirement]):
#     """Ordered, deduplicated collection of requirements.
#
#     Deduplication is by canonical package name. Provides basic set
#     operations on RequirementSet objects.
#
#     Use `.merge()` to merge RequirementSet's, choosing whether to keep
#     or update version specifiers from existing dependencies.
#     """
#
#     def __init__(self, requirements: Iterable[PackageRequirement | str] = ()) -> None:
#         self._reqs: dict[str, PackageRequirement] = {}
#         for req in requirements:
#             self.add(req)
#
#     def __contains__(self, item: object) -> bool:
#         if isinstance(item, str):
#             return canonicalize_name(item) in self._reqs
#         if isinstance(item, Requirement):
#             return canonicalize_name(item.name) in self._reqs
#
#         return False
#
#     def __iter__(self) -> Iterator[PackageRequirement]:
#         return iter(self._reqs.values())
#
#     def __len__(self) -> int:
#         return len(self._reqs)
#
#     @classmethod
#     def from_dists(cls, dists: list[Distribution], mode: str) -> Self:
#         return cls([PackageRequirement.from_dist(dist, mode) for dist in dists])
#
#     @classmethod
#     def from_requirements(cls, path: str) -> tuple[Self, list[str]]:
#         """Parse RequirementSet from a 'requirements.txt' file. This parses
#         each line, adding it to the 'RequirementSet' if valid, or adding it to
#         a list of unknown strings if could not parse.
#
#         > NOTE: Despite being a class method, this returns 2 values.
#
#         Args:
#             path: 'requirements.txt' path
#
#         Returns:
#             RequirementSet and list[str] (Unknown entries)
#         """
#         reqs: list[PackageRequirement] = []
#         unknown: list[str] = []
#         with open(path, "r") as f:
#             for raw_line in f:
#                 line = raw_line.strip()
#                 if not line or line.startswith("#"):
#                     continue
#                 try:
#                     dep = PackageRequirement(line)
#                     reqs.append(dep)
#                 except InvalidRequirement:
#                     unknown.append(line)
#         return cls(reqs), unknown
#
#     def add(self, value: PackageRequirement | str) -> None:
#         """Add a requirement, replacing any existing entry for the same
#         package."""
#         if isinstance(value, str):
#             value = PackageRequirement(value)
#         elif not isinstance(value, PackageRequirement):
#             # Transparently wrap a plain Requirement in our subclass
#             value = PackageRequirement(str(value))
#         self._reqs[canonicalize_name(value.name)] = value
#
#     def discard(self, value: PackageRequirement | str) -> None:
#         if isinstance(value, str):
#             key = canonicalize_name(value)
#         else:
#             key = canonicalize_name(value.name)
#         self._reqs.pop(key, None)
#
#     # for lookup
#     def get(self, name: str) -> PackageRequirement | None:
#         return self._reqs.get(canonicalize_name(name))
#
#     def __getitem__(self, name: str) -> PackageRequirement:
#         try:
#             return self._reqs[canonicalize_name(name)]
#         except KeyError:
#             raise KeyError(f"No requirement found for package: {name!r}")
#
#     def merge(self, other: "RequirementSet", update: bool = True) -> "RequirementSet":
#         """Return a new RequirementSet combining both sets.
#
#         When `update == True`(default): When the same package appears in
#         both, `other` takes precedence and gets updated.
#
#         When `update == False`, the package from this set is kept.
#         """
#         merged = RequirementSet(self)
#         for req in other:
#             if req in merged and not update:
#                 continue
#             merged.add(req)
#         return merged
#
#     def intersection(self, other: "RequirementSet") -> "RequirementSet":
#         """Return requirements whose package names appear in _both_ sets.
#
#         The specifier from `self` is kept for packages present in both.
#         """
#         return RequirementSet(req for req in self if req in other)
#
#     def difference(self, other: "RequirementSet") -> "RequirementSet":
#         """Return requirements in `self` whose package names are not in
#         `other`.
#
#         '*Whats in A but not in B at all?*'
#         """
#         return RequirementSet(req for req in self if req not in other)
#
#     def conflicts(self, other: "RequirementSet") -> "RequirementSet":
#         """Return requirements present in both sets but with differing
#         specifiers. 'Whats in both A and B but disagrees on the version?'.
#
#         A 'conflict' means the same package is pinned to
#         incompatible/different version specs (using deep_equal to detect
#         actual differences).
#         """
#         result = RequirementSet()
#         for req in self:
#             other_req = other.get(req.name)
#             if other_req is not None and not req.deep_equal(other_req):
#                 result.add(req)
#         return result
#
#     def is_subset_of(self, other: "RequirementSet") -> bool:
#         """True if every package in self also appears in other (name-only
#         check)."""
#         return all(req in other for req in self)
#
#     def is_deeply_equal(self, other: "RequirementSet") -> bool:
#         """True if both sets contain exactly the same requirements with the
#         same specs."""
#         if len(self) != len(other):
#             return False
#         for req in self:
#             other_req = other.get(req.name)
#             if other_req is None or not req.deep_equal(other_req):
#                 return False
#         return True
#
#     def update_merge(
#         self, new: RequirementSet, remove_unused: bool, update_existing: bool
#     ):
#         """Update this RequirementSet (representing 'old' reqs read from a
#         requirements.txt/etc file) with the new RequirementSet from a Scan.
#
#         All 'new_reqs' are kept, with optional arguments to control how the reqs are merged.
#
#         Args:
#             new: The new RequirementSet to merge `self` with.
#             remove_unused: Remove `self` deps that are not found in the `new_deps` set? (Default True).
#             update_existing: Use the PackageRequirement from `new_deps` when the same package is found in `self` and `new_deps`? (Default True).
#
#         Returns:
#             Merged RequirementSet.
#         """
#         keep_unused = not remove_unused
#         use_old_version = not update_existing
#         merged = RequirementSet(new)
#         for old_dep in self:
#             if old_dep in merged:
#                 if use_old_version:
#                     # Replace scanned version with OG version
#                     merged.add(old_dep)
#                 else:
#                     continue
#             else:
#                 if keep_unused:
#                     merged.add(old_dep)
#         return merged
#
#     # --- Dunder helpers ------------------------------------------------------
#
#     def __or__(self, other: "RequirementSet") -> "RequirementSet":
#         """Self | other  →  merge (other takes precedence)."""
#         return self.merge(other)
#
#     def __and__(self, other: "RequirementSet") -> "RequirementSet":
#         """Self & other  →  intersection."""
#         return self.intersection(other)
#
#     def __sub__(self, other: "RequirementSet") -> "RequirementSet":
#         """self - other  →  difference."""
#         return self.difference(other)
#
#     def __eq__(self, other: object) -> bool:
#         """Shallow equality: same package names, regardless of specifiers."""
#         if not isinstance(other, RequirementSet):
#             return NotImplemented
#         return set(self._reqs.keys()) == set(other._reqs.keys())
#
#     def __repr__(self) -> str:
#         reqs = ", ".join(str(r) for r in self)
#         return f"RequirementSet([{reqs}])"
