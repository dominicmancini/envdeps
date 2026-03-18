from envdeps.common import PathOrStr
from envdeps.formatters.base import BaseFormatter


# NOTE: This one calls '.load()' in the __init__ now.
# No need to call it manually
class RequirementsFormatter(BaseFormatter):
    def __init__(self, text: str = "") -> None:
        super().__init__(text)
        self.load()

    def load(self) -> None:
        return super().load()

    def dump(self, path: PathOrStr) -> PathOrStr:
        deps = self.dependencies
        if not self.dependencies:
            print("No dependencies to write.")
            return path
        deps_text = deps.to_string()
        with open(path, "w") as f:
            f.write(deps_text)
        return path
