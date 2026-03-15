import ast
from pathlib import Path
from pprint import pp

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
            tree = ast.parse(partial_content, filename=str(fpath))
            last_successful_imports = _get_imports_from_tree(tree)
        except SyntaxError:
            # keep going, might be incomplete statement
            continue
    return last_successful_imports


def extract_file_imports(file: Path) -> set[str]:
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
    def __init__(self, target: Path, ignore_dirs: list[str]) -> None:
        self.target = target
        self.ignore_dirs = ignore_dirs

        self.all_imports: ImportSet = set()
        self.file_imports: FileImports = {}  # Mapping of file to imports in file

    def scan(self):
        # all_imports = set()
        for file in self.target.rglob("*.py"):
            should_ignore = any(dir in file.parts for dir in self.ignore_dirs)
            if should_ignore:
                continue
            file_imports = extract_file_imports(file)
            if file_imports:
                self.all_imports.update(file_imports)
                self.file_imports[file] = file_imports
        return self.all_imports, self.file_imports


if __name__ == "__main__":
    p = ProjectScanner(
        Path("/home/domancini/projects/envdeps/envdeps"),
        ["__pycache__"],
    )
    p.scan()
    pp(p.all_imports)
