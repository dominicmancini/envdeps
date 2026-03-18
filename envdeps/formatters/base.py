from abc import ABC, abstractmethod
from pathlib import Path

from envdeps.common import PathOrStr
from envdeps.dependencies import RequirementSet


class BaseFormatter(ABC):
    def __init__(self, text: str = "") -> None:
        self.text = text
        self._dependencies: RequirementSet = RequirementSet()
        # self.load()

    @classmethod
    def from_file(cls, path: Path):
        if not path.exists():
            raise FileNotFoundError(f"Path {path} does not exist.")
        text = path.read_text()
        return cls(text=text)

    @property
    def dependencies(self):
        return self._dependencies

    @dependencies.setter
    def dependencies(self, deps: RequirementSet):
        self._dependencies = deps

    def _parse_lines(self, raw_lines: list[str]) -> RequirementSet:
        return RequirementSet(raw_lines)

    @abstractmethod
    def load(self) -> None:
        """Load the dependencies from `self.text`.

        After calling this, they will be accessible in `.dependencies`.
        """
        raw_lines = self.text.splitlines()
        self._dependencies = self._parse_lines(raw_lines)

    @abstractmethod
    def dump(self, path: PathOrStr) -> PathOrStr:
        """Write dependencies to the file specified by `path`."""
        pass
