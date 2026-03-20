import tomlkit
from tomlkit.items import Array, Table

from envdeps.common import PathOrStr
from envdeps.dependencies import RequirementSet
from envdeps.formatters.base import BaseFormatter

# NOTE: Instead of accessing the intermediate `self._dependencies` attribute,
# this class uses the `self._project` table in the `self.doc` TOMLDocument to directly
# change the dependencies
# This


class PyProjectFormatter(BaseFormatter):
    """Formatter for 'pyproject.toml' dependencies.

    Usage::

        p = Pyproject("...") # from text
        p = Pyproject.from_file(...) # from path
        deps = p.dependencies
        merged = deps.update_merge(new_deps, ...)
        p.dependencies = merged
        print(p.dependencies) # check new deps
        p.dump(path) # optionally write new deps

    NOTE: Instead of accessing an intermediate `self._dependencies` attribute, this class directly reads and sets from `self._project` - the 'project' table in the `self.doc` TOMLDocument. These are apart of the same document, so any changes to the dependencies list in `self._project` affect the upstream TOMLDocument too.

    The property `self.dependencies` just reads from and sets the `self._project["dependencies"]` field.

    Still, the modfied document is not persisted/written until `self.dump()`.

    Attributes:
        doc: TOMLDocument object for the 'pyproject.toml'
    """

    def __init__(self, text: str = "") -> None:
        super().__init__(text)
        self.doc: tomlkit.TOMLDocument = self._init_doc(text)
        self._project: Table = self.doc.setdefault("project", tomlkit.table())

    def _init_doc(self, text: str) -> tomlkit.TOMLDocument:
        if self.text.strip():
            doc = tomlkit.parse(text)
        else:
            doc = tomlkit.document()
        doc_deps: Array = doc.setdefault("project", tomlkit.table()).setdefault(
            "dependencies", tomlkit.array()
        )
        return doc

    def _get_doc_dependencies(self):
        dep_list: list = self._project["dependencies"].unwrap()
        deps = RequirementSet(dep_list)
        return deps

    @property
    def dependencies(self):
        dep_list = self._project["dependencies"].unwrap()
        deps = RequirementSet(dep_list)
        return deps

    @dependencies.setter
    def dependencies(self, deps: RequirementSet):
        dep_strs = [str(dep) for dep in deps]
        self._project["dependencies"] = dep_strs

    def load(self) -> None:
        dep_list: list = self._project["dependencies"].unwrap()
        deps = RequirementSet(dep_list)
        self._dependencies = deps

    def dump(self, path: PathOrStr) -> PathOrStr:
        if not self.dependencies:
            print("No dependencies to write.")
            return path
        with open(path, "w") as f:
            tomlkit.dump(self.doc, f)
        return path

    def _as_text(self) -> str:
        doc_text = tomlkit.dumps(self.doc)
        return doc_text
