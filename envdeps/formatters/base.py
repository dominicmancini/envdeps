from abc import ABC, abstractmethod
from pathlib import Path

from packaging.requirements import InvalidRequirement

from envdeps.common import PathOrStr
from envdeps.dependencies import PackageRequirement, RequirementSet


class BaseFormatter(ABC):
    @abstractmethod
    def __init__(self, text: str = "") -> None:
        self.text = text
        self._dependencies: RequirementSet = RequirementSet()
        self._unknown = []

    @classmethod
    def from_file(cls, path: Path):
        if not path.exists():
            raise FileNotFoundError(f"Path {path} does not exist.")
        text = path.read_text()
        return cls(text=text)

    def _parse_lines(self, raw_lines: list[str]) -> tuple[RequirementSet, list[str]]:
        reqs = []
        unknown = []
        for raw_line in raw_lines:
            line = raw_line.strip()
            if not raw_line or raw_line.startswith("#"):
                continue
            try:
                dep = PackageRequirement(line)
                reqs.append(dep)
            except InvalidRequirement:
                unknown.append(line)
        return RequirementSet(reqs), unknown

    @abstractmethod
    def load(self) -> None:
        """Load the dependencies from `self.text`.

        After calling this, they will be accessible in `.dependencies`.
        """
        raw_lines = self.text.splitlines()
        deps, unknown = self._parse_lines(raw_lines)
        self._dependencies = deps
        self._unknown = unknown

    @property
    def dependencies(self):
        return self._dependencies

    @abstractmethod
    def dump(self, path: PathOrStr) -> Path:
        """Write dependencies to the file specified by `path`."""
        pass
