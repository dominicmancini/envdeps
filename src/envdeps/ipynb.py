import ast
import json
from pathlib import Path

from loguru import logger


def read_nb(path: Path):
    with open(path, "r") as f:
        data_str = f.read()
    data: dict = json.loads(data_str)
    return data


def _is_line_magic(line: str):
    return line.startswith("%")


def _is_cell_magic(cell_lines: list[str]):
    """Check if this given cell (a list of code lines from cell) is a 'cell
    magic'.

    Cell magics occupy the entire cell, but may have empty lines before
    hand/etc. This finds the first non-empty line, and checks if the
    stripped line starts with '%%'.
    """
    if not cell_lines:
        return False
    first_non_empty = next((line for line in cell_lines if line.strip()), None)
    if first_non_empty and first_non_empty.strip().startswith("%%"):
        return True
    return False


def _extract_code_from_cells(data: dict) -> list[str]:
    """From the raw Notebook json text, extract all the text from cells in the
    notebook. NOTE: This removes all 'cell magics' cells from the notebook, but
    not the 'line magics'. Line magics should be removed after this by parsing
    each line.

    Args:
        data: Raw Notebook Json text.

    Returns:
        lines: Each line from all code cells in a single list.
    """
    lines: list[str] = []
    cells: list[dict] = data.get("cells", [])
    for cell in cells:
        cell_type = cell.get("cell_type", "")
        if cell_type == "code":
            code: list[str] = cell.get("source", [])
            if isinstance(code, str):
                code = code.splitlines()
            if _is_cell_magic(code):
                continue
            lines.extend(code)
    return lines


def _parse_raw_notebook(json_text: str):
    """Given the notebook JSON text, return a string containing just the code
    lines joined from all code cells in the notebook.

    Args:
        json_text: Raw notebook JSON text.

    Returns:
        string of all code lines from notebook.
    """
    data: dict = json.loads(json_text)
    if not data or not data.get("cells", None):
        return None
    lines = _extract_code_from_cells(data)
    if not lines:
        return None
    _magic_lines = []
    for line in lines[:]:
        if _is_line_magic(line):
            lines.remove(line)
            _magic_lines.append(line)

    if _magic_lines:
        logger.debug(f"Found and removed magic lines: {_magic_lines}")
    # lines = [line for line in lines if not _is_line_magic(line)]
    code = "\n".join(lines)
    return code


def get_notebook_imports(nb_data: str, fpath="notebook.ipynb") -> set[str]:
    """Scan the notebook given by the raw notebook data `nb_data` and return
    the set of imports parsed from the file.

    Args:
        nb_data: String of raw JSON notebook data.

    Returns:
        Set of used imports in the notebook.
    """
    from envdeps.scanner import _get_imports_from_tree, try_parse_incrementally

    imports = set()
    if not nb_data.strip():
        return set()
    data: dict = json.loads(nb_data)
    lines = _extract_code_from_cells(data)
    if not lines:
        return imports
    _magic_lines = []
    for line in lines[:]:
        if _is_line_magic(line):
            lines.remove(line)
            _magic_lines.append(line)

    if _magic_lines:
        logger.debug(f"Found and removed magic lines: {_magic_lines}")
    # Removing magic lines
    # lines = [line for line in lines if not _is_line_magic(line)]

    code = "\n".join(lines)
    try:
        tree = ast.parse(code, filename=fpath)
        file_imports = _get_imports_from_tree(tree)
        return file_imports
    except SyntaxError:
        pass
    file_imports = try_parse_incrementally(code, fpath)
    return file_imports


def read_notebook_imports_from_file(path: Path):
    """Utility function for `read_notebook_imports` that accepts a file path to
    a '.ipynb' file instead of the raw text. This calls `read_notebook_imports`
    after reading the file.

    Args:
        path: Path to 'ipynb' notebook file with imports to scan.

    Returns:
        ImportSet: Set of imports found in notebook.

    Raises:
        FileNotFoundError: File doesn't exist.
    """
    if not path.exists():
        raise FileNotFoundError(f"File not found: '{path}'")
    nb_data = path.read_text()
    return get_notebook_imports(nb_data, str(path))
