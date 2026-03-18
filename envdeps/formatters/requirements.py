from envdeps.common import PathOrStr
from envdeps.formatters.base import BaseFormatter


class RequirementsFormatter(BaseFormatter):
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
