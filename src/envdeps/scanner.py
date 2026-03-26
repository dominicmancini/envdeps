import ast
import os
from pathlib import Path
from pprint import pp
from warnings import deprecated

from envdeps.ipynb import _parse_raw_notebook

type ImportSet = set[str]
type FileImports = dict[Path, ImportSet]


def _line_past_imports(line: str) -> bool:
    """Check if the import section is over.

    This heuristic assumes import section is over before the first func
    or class definition.
    """
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return False
    if stripped.startswith("def ") or stripped.startswith("class "):
        return True
    return False


def _get_imports_from_tree(tree: ast.Module):
    """Collect the top-level module imports from this syntax tree."""
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module.split(".")[0])
    return imports


def try_parse_incrementally(text: str, fpath) -> set[str]:
    """Parse the given file text incrementally, for files that encountered
    `SyntaxError` during ast parsing.

    This parses one line at a time, collecting the imports until it is
    assumed the import section is over.
    """
    lines = text.strip().splitlines()
    # imports = set()
    accumulated_lines = []
    last_successful_imports = set()

    for i, line in enumerate(lines):
        accumulated_lines.append(line)
        if _line_past_imports(line):
            break
        try:
            partial_content = "".join(accumulated_lines)
            tree = ast.parse(partial_content)
            last_successful_imports = _get_imports_from_tree(tree)
        except SyntaxError:
            # keep going, might be incomplete statement
            continue
    return last_successful_imports


def extract_imports_from_text(text: str, fpath: str = "<unknown>") -> set[str]:
    """Extract imports from raw python code."""
    if not text.strip():
        return set()
    try:
        tree = ast.parse(text)
        file_imports = _get_imports_from_tree(tree)
        return file_imports
    except SyntaxError:
        pass
    file_imports = try_parse_incrementally(text, fpath=fpath)
    return file_imports


def extract_file_imports(file: Path) -> set[str]:
    """Extract imports from a '.py' or '.ipynb' file, returning a set of the
    file's imports."""
    if file.suffix.lower() == ".ipynb":
        raw_json = file.read_text()
        text = _parse_raw_notebook(raw_json)
        if not text:
            return set()
    else:
        text = file.read_text()
    if not text.strip():
        return set()
    try:
        tree = ast.parse(text, file)
        file_imports = _get_imports_from_tree(tree)
        return file_imports
    except SyntaxError:
        pass
    file_imports = try_parse_incrementally(text, file)
    return file_imports


class ProjectScanner:
    """Recursively scan files python source files in the `target` directory
    (respecting `ignore_dirs`) and extract the imports from each file.

    Attributes:
        target: Target directory in python project to scan recursively.
        ignore_dirs: List of directory names to ignore when searching.
        all_imports: Set of all the top-level import names found in files (not filtered, so includes stdlib + local names)
        file_imports: Mapping of files to the ImportSet extracted from the file.
    """

    def __init__(
        self, target: Path, ignore_dirs: list[str], scan_ipynb: bool = False
    ) -> None:
        self.target = target
        self.ignore_dirs = set(ignore_dirs)
        self.scan_ipynb = scan_ipynb
        self._exts = (".py", ".ipynb") if scan_ipynb else (".py")

        self.all_imports: ImportSet = set()
        self.file_imports: FileImports = {}  # Mapping of file to imports in file

    def scan(self):
        """Recursively iterate through target directory, collecting all the
        import names and imports from each file.

        If `self.scan_ipynb == True`, this will also scan ipynb notebooks in additon to python files. Otherwise

        Only method needed to call for this class.

        Returns:
            ImportSet, FileImports: A set of all import names from the scanned files, and a Mapping of file Paths to their ImportSet.
        """
        for dirpath, dirnames, filenames in self.target.walk():
            dirnames[:] = [d for d in dirnames if d not in self.ignore_dirs]
            for filename in filenames:
                if filename.lower().endswith(self._exts):
                    fpath = dirpath.joinpath(filename)
                    imports = extract_file_imports(fpath)
                    self.all_imports.update(imports)
                    self.file_imports[fpath] = imports
        return self.all_imports, self.file_imports

        # all_imports = set()

    @deprecated("Use 'scan()'. This method does not handle '.ipynb' files")
    def _old_scan(self):
        for file in self.target.rglob("*.py"):
            should_ignore = any(dir in file.parts for dir in self.ignore_dirs)
            if should_ignore:
                continue
            file_imports = extract_file_imports(file)
            if file_imports:
                self.all_imports.update(file_imports)
                self.file_imports[file] = file_imports
        return self.all_imports, self.file_imports

    def _iter_files(self):
        for dirpath, dirnames, filenames in os.walk(self.target):
            # modify dirnames in-place
            dirnames[:] = [d for d in dirnames if d not in self.ignore_dirs]
            for file in filenames:
                if file.endswith(".py"):
                    yield Path(dirpath) / file

    def iter_scan(self):
        """An alternate to `scan` that may be a *little bit* faster.

        NOTE: A `ProjectScanner` instance should NOT call both `.scan()` and `iter_scan()`, only one (these both modify the `all_imports`, and `file_imports` attributes.)

        Returns:
            ImportSet, FileImports: A set of all import names from the scanned files, and a Mapping of file Paths to their ImportSet.
        """
        for file in self._iter_files():
            imports = extract_file_imports(file)
            if imports:
                self.all_imports.update(imports)
                self.file_imports[file] = imports
        return self.all_imports, self.file_imports


if __name__ == "__main__":
    p = ProjectScanner(
        Path("/home/domancini/projects/envdeps/envdeps"),
        ["__pycache__"],
    )
    p.scan()
    pp(p.all_imports)
