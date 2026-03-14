from abc import ABC, abstractmethod
from collections import defaultdict
from pathlib import Path
from typing import Sequence, TypedDict, Unpack

import tomlkit
from loguru import logger
from packaging.requirements import InvalidRequirement, Requirement

from envdeps.common import Dependency

type DepOrStr = Dependency | str
type MixedDependencies = Sequence[Dependency | str]
type DependencyList = Sequence[Dependency]


DEFAULT_OPTS = {
    "remove_unused": True,
    "remove_unknown": False,
    "update_existing": False,
}


class MergeOpts(TypedDict):
    remove_unused: bool
    remove_unknown: bool
    update_existing: bool


class BaseDepFormat(ABC):
    @abstractmethod
    def __init__(self, text: str = "") -> None:
        pass

    @classmethod
    def from_file(cls, path: Path):
        if not path.exists():
            raise FileNotFoundError(f"Path: {path} does not exist.")
        text = path.read_text()
        return cls(text=text)

    @property
    @abstractmethod
    def dependencies(self) -> list[DepOrStr]:
        pass

    @abstractmethod
    def update_dependencies(
        self,
        new_deps: list[Dependency],
        remove_unknown: bool = False,
        remove_unused: bool = True,
        update_existing: bool = False,
    ):
        pass

    @abstractmethod
    def write_file(self, path: Path) -> Path:
        pass

    def _merge_deps(
        self,
        old_deps: MixedDependencies,
        new_deps: DependencyList,
        **opts: Unpack[MergeOpts],
    ) -> set[Dependency | str]:
        unknown: set[str] = set()
        old: set[Dependency] = set()
        for dep in old_deps:
            parsed_dep = try_parse_dep(dep)
            if isinstance(parsed_dep, str):
                unknown.add(parsed_dep)
            else:
                old.add(parsed_dep)
        scanned = set(new_deps)
        merged_deps = set()
        to_add = scanned.copy()
        for dep in old:
            if dep in scanned:
                if opts["update_existing"]:
                    continue
                else:
                    merged_deps.add(dep)
                    to_add.remove(dep)
            else:
                if opts["remove_unused"]:
                    continue
                else:
                    merged_deps.add(dep)
        if not opts["remove_unknown"]:
            return unknown | merged_deps | to_add
        return merged_deps | to_add


class Pyproj(BaseDepFormat):
    def __init__(self, text: str) -> None:
        self.text = text
        self.document = self._init_doc(text)
        # self._dependencies: list[Dependency|str] = self._init_deps()

    def _init_doc(self, text: str) -> tomlkit.TOMLDocument:
        if text.strip():
            doc = tomlkit.parse(text)
        else:
            doc = tomlkit.document()

        doc.setdefault("project", tomlkit.table())
        if "dependencies" not in doc["project"]:  # type: ignore[index]
            doc["project"]["dependencies"] = tomlkit.array()  # type: ignore[index]
        return doc

    # def _init_deps(self) -> list[Dependency|str]:
    #     deps: list = self.document["project"]["dependencies"].unwrap()  # type: ignore
    #     if not deps:
    #         return []
    #     parsed_deps = []
    #     for dep in deps:
    #         parsed_dep = try_parse_dep(dep)
    #         parsed_deps.append(parsed_dep)
    #     return parsed_deps

    @property
    def dependencies(self) -> list[DepOrStr]:
        # return self.document["project"]["dependencies"]  # type: ignore[index]
        deps = self.document["project"]["dependencies"].unwrap()  # type: ignore[index]
        if not deps:
            return []
        parsed_deps = [try_parse_dep(dep) for dep in deps]
        return parsed_deps

    @dependencies.setter
    def dependencies(self, values: list):
        str_values = [str(i) for i in values]
        self.document["project"]["dependencies"] = str_values  # type: ignore[index]

    def write_file(self, path: Path) -> Path:
        with open(path, "w") as f:
            tomlkit.dump(self.document, f)
        return path

    @classmethod
    def from_file(cls, path: Path):
        if not path.exists():
            raise FileNotFoundError(f"Path: {path} does not exist.")
        text = path.read_text()
        return cls(text=text)

    def update_dependencies(
        self,
        new_deps: list[Dependency],
        remove_unknown: bool = False,
        remove_unused: bool = True,
        update_existing: bool = False,
    ):
        """[TODO:description]

        Args:
            dependencies: List of scanned dependencies
            remove_unknown: Remove unknown entries in dependencies. (default False)
            remove_unused: Remove entries that are not used in project (not found in scan) (defualt True)
            update_existing: Keep the specifier used for existing dependencies (False), or update to the specified 'mode' (True) (default False)
        """
        if not self.dependencies:
            self.dependencies = new_deps
            return
        merged_deps: set[DepOrStr] = self._merge_deps(
            self.dependencies,
            new_deps,
            remove_unused=remove_unused,
            update_existing=update_existing,
            remove_unknown=remove_unknown,
        )
        if not merged_deps:
            logger.warning("Merged Dependencies are empty.")
        self.dependencies = list(merged_deps)
        # NOTE: OLD Implementation
        # old_deps = [_parse_requirement(dep) for dep in self.dependencies]
        # merged_dependencies = parse_merge(
        #     old_deps,
        #     new_deps,
        #     remove_unknown=remove_unknown,
        #     remove_unused=remove_unused,
        #     update_existing=update_existing,
        # )
        # if not merged_dependencies:
        #     logger.warning("Merged dependencies is empty.")
        # self.dependencies = merged_dependencies


class Requirements(BaseDepFormat):
    def __init__(self, text: str) -> None:
        self.text = text
        self._dependencies = self._init_deps(text)

    def _init_deps(self, text: str) -> list[Dependency | str]:
        if not text.strip():
            return []
        lines = text.splitlines()
        deps: list[Dependency | str] = []
        for line in lines:
            try:
                dep = Dependency(line)
                deps.append(dep)
            except InvalidRequirement:
                deps.append(line)
        return deps

    @property
    def dependencies(self) -> list[DepOrStr]:
        return self._dependencies
        # return [str(dep) for dep in self._dependencies]

    @dependencies.setter
    def dependencies(self, values: list):
        self._dependencies = values

    def update_dependencies(
        self,
        new_deps: list[Dependency],
        remove_unknown: bool = False,
        remove_unused: bool = True,
        update_existing: bool = False,
    ):
        if not self.dependencies:
            self.dependencies = new_deps
            return
        merged_deps: set[DepOrStr] = self._merge_deps(
            self.dependencies,
            new_deps,
            remove_unused=remove_unused,
            update_existing=update_existing,
            remove_unknown=remove_unknown,
        )
        if not merged_deps:
            logger.warning("Merged Dependencies are empty.")
        self.dependencies = list(merged_deps)
        # NOTE: OLD IMPLEMENTATION
        # old_reqs = self.dependencies.copy()
        # new_list = []
        # deps_to_add = new_deps.copy()
        # if not remove_unknown:
        #     unknown_reqs = [i for i in old_reqs if isinstance(i, str)]
        #     logger.debug(f"Adding unknown reqs to 'new_list': {unknown_reqs}")
        #     new_list.extend(unknown_reqs)
        # # Remove all strings from old_reqs, now all are 'Dependency'
        # old_reqs = [i for i in old_reqs if not isinstance(i, str)]
        # if not remove_unused:
        #     _found_unused = []
        #     for old_req in old_reqs:
        #         if old_req not in new_deps:
        #             new_list.append(old_req)
        #             _found_unused.append(old_req)
        #     logger.debug(f"Adding 'found_unused' to 'new_list': {_found_unused}")
        # if not update_existing:
        #     _found_existing = []
        #     # NOTE: using 'enumerate' so we can modify list while iterating
        #     for _, req in enumerate(old_reqs):
        #         req = Dependency(str(req))
        #         new_list.append(req)
        #         _found_existing.append(req)
        #         deps_to_add = [
        #             d
        #             for d in deps_to_add
        #             if not d.normalized_name == req.normalized_name
        #         ]
        #     logger.debug(f"Adding 'found_existing' to 'new_list': {_found_existing}")
        # new_list.extend(deps_to_add)
        # if not new_list:
        #     logger.warning("Merged dependencies is empty.")
        # self.dependencies = new_list
        # return super().update_dependencies(new_deps, remove_unknown, remove_unused, update_existing)

    def write_file(self, path: Path) -> Path:
        if not self.dependencies:
            print("No Dependencies to write!")
        lines = [str(dep) for dep in self.dependencies]
        with open(path, "w") as f:
            f.write("\n".join(lines))
        return path


def try_parse_dep(dep) -> Dependency | str:
    if isinstance(dep, Dependency):
        return dep
    try:
        return Dependency(str(dep))
    except InvalidRequirement:
        return str(dep)


def filter_type(l, typ: type, keep_typ: bool = True):
    if keep_typ:
        return [i for i in l if isinstance(i, typ)]
    else:
        return [i for i in l if not isinstance(i, typ)]


def remove_dep(dep: Dependency, dep_list: list[Dependency]):
    return [d for d in dep_list if not d == dep]


def parse_merge(
    old_reqs: list[Requirement | Dependency | str],
    scanned_deps: list[Dependency],
    **kwargs,
):
    new_list = []
    deps_to_add = scanned_deps.copy()
    kwargs = defaultdict(lambda: False, kwargs)
    if not kwargs["remove_unknown"]:
        # unknown_reqs = [req for req in old_reqs if isinstance(old_reqs, str)]
        # unknown_reqs = filter_type(old_reqs, str, True)
        unknown_reqs = [i for i in old_reqs if isinstance(i, str)]
        logger.debug(f"Adding unknown reqs to 'new_list': {unknown_reqs}")
        new_list.extend(unknown_reqs)
    # old_reqs = cast(list[Requirement|Dependency], filter_type(old_reqs, str, False))
    # old_reqs = [i for i in old_reqs if not isinstance(old_reqs, str)]
    old_reqs = [i for i in old_reqs if not isinstance(i, str)]
    # old_reqs = filter_type(old_reqs, str, False)
    if not kwargs["remove_unused"]:
        _found_unused = []
        for old_req in old_reqs:
            if old_req not in scanned_deps:
                new_list.append(old_req)
                _found_unused.append(old_req)
        logger.debug(f"Adding 'found_unused' to 'new_list': {_found_unused}")
    if not kwargs["update_existing"]:
        _found_existing = []
        for _, req in enumerate(old_reqs):
            req = Dependency(str(req))
            # Append the dep to new list
            new_list.append(req)
            _found_existing.append(req)
            # Remove it from the deps we will add (because already in 'new_list')
            deps_to_add = [
                d for d in deps_to_add if not d.normalized_name == req.normalized_name
            ]
        logger.debug(f"Adding 'found_existing' to 'new_list': {_found_existing}")
    # final_deps = new_list + deps_to_add
    new_list.extend(deps_to_add)
    return new_list


if __name__ == "__main__":
    test = """
project = {dependencies = ['pandas', 'numpy', 'typer', 'tomlkit']}"""
    test_cmts = """
[project]
dependencies = [
    # These are dependencies
    'pandas>=0.12.1',
    'numpy==1.0',
    'typer',
    'tomlkit'
]
    """
    p = Pyproj(test_cmts)
    print(p.dependencies)
