"""Repurposed module to format different outputs for the envdeps 'show'
command."""

import pygments.token as t
from pygments.lexer import RegexLexer
from pygments.style import Style
from rich.console import Console
from rich.syntax import Syntax
from rich.table import Table

console = Console(no_color=None)


def get_console(**kwargs):
    if "no_color" in kwargs:
        console.no_color = kwargs["no_color"]
    return console


def lists_to_table(
    *cols: list, header: list, title: str | None = None, **tbl_kwargs
) -> Table:
    """Convert lists (columns) and a header row to a rich Table.

    `**tbl_kwargs` will be passed to the `Table(..)` constructor
    """
    colors = ["cyan", "magenta", "green", "red"]
    tbl = Table(title=title, **tbl_kwargs)
    i = 0
    for head in header:
        tbl.add_column(head, style=colors[i])
        i = i + 1
    for row in zip(*cols):
        tbl.add_row(*row)

    return tbl


class RequirementsLexer(RegexLexer):
    name = "requirements"
    aliases = ["reqs"]
    tokens = {
        "root": [
            (r"[ \t]*#.*$", t.Comment),
            (r"(\@\s)?(https?|ftp|gopher)://[^\s]+", t.Literal),
            (r"^(\-\w|\-{2}\w+)\s", t.Literal),  # -r, --option
            (r"\[\S+\]", t.Name.Attribute),  # [extras]
            (r"\d+[a-zA-Z0-9\.\-\*]*", t.Number),  # version numbers
            (r"(\=\=\=?|\<\=?|\>\=?|\~\=|\!\=)", t.Operator),  # version specifiers
            (r"^([a-zA-Z0-9][a-zA-Z0-9\-_\.]*[a-zA-Z0-9])", t.Name),  # package name
            (r";\s[^#]+", t.Keyword),  # environment markers
            (r"\s+", t.Whitespace),
            (r".+", t.Text),
        ]
    }


class ReqStyle(Style):
    styles = {
        t.Comment: "italic #888",
        t.Literal: "bold #005",
        t.Name: "#f00",
        t.Name.Attribute: "bold #0af",
        t.Number: "#0a0",
        t.Operator: "#fa0",
        t.Keyword: "bold #a0f",
        t.Text: "#fff",
        t.Whitespace: "#fff",
    }


def print_reqs(reqs_str: str):
    syntax = Syntax(reqs_str, RequirementsLexer())
    console.print(syntax)


def toml_syntax(code: str):
    return Syntax(code, "toml")
