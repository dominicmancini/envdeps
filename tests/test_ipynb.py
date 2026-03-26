import json
from dataclasses import dataclass
from http.client import HTTPResponse
from pathlib import Path
from urllib.request import urlopen

from rich import print

from envdeps.ipynb import get_notebook_imports

abspath = lambda path: Path(path).expanduser().resolve()


def make_nb(cells: list[list[str]]):
    """Make a barebones, raw notebook from a list of code cells.

    Each list in `cells` represents a cell, with each string being a line in that cell.
    """
    nb = {
        "metadata": {
            "kernel_info": {
                # if kernel_info is defined, its name field is required.
                "name": "the name of the kernel"
            },
            "language_info": {
                # if language_info is defined, its name field is required.
                "name": "the programming language of the kernel",
                "version": "the version of the language",
                "codemirror_mode": "The name of the codemirror mode to use [optional]",
            },
        },
        "nbformat": 4,
        "nbformat_minor": 0,
        "cells": [],
    }
    for cell_lines in cells:
        nb["cells"].append({"cell_type": "code", "metadata": {}, "source": cell_lines})
    return json.dumps(nb)


def request(url: str) -> str:
    resp: HTTPResponse = urlopen(url)
    return resp.read().decode()


@dataclass
class Test:
    data: str
    imports: set[str]

    @classmethod
    def from_file(cls, path: str, imports):
        text = Path(path).expanduser().read_text()
        return cls(text, imports)

    @classmethod
    def from_url(cls, url: str, imports):
        data = request(url)
        if not data or not data.strip():
            raise ValueError("Request response is None")
        return cls(data, imports)

    @classmethod
    def from_cells(cls, cells: list[list[str]], imports):
        data = make_nb(cells)
        return cls(data, imports)


tests = [
    Test.from_url(
        "https://jakevdp.github.io/downloads/notebooks/XKCD_plots.ipynb",
        {
            "IPython",
            "numpy",
            "pylab",
            "scipy",
            "matplotlib",
            "os",
            "urllib2",
        },
    ),
    Test.from_cells(
        [
            [
                "import numpy as np",
                "import pandas as pd",
                "import matplotlib.pyplot as plt",
            ],
            ["import seaborn", "import local_mod"],
            [
                "import sklearn",
                "from sklearn.linear import LinearRegression",
                "%test_magic",
            ],
        ],
        {"numpy", "pandas", "matplotlib", "seaborn", "local_mod", "sklearn"},
    ),
]

versions_tests = {
    "2": Test.from_url(
        "https://raw.githubusercontent.com/jupyter/nbformat/refs/heads/main/tests/test2.ipynb",
        set(),
    ),  # NOTE: No Imports
    "4.5": Test.from_url(
        "https://raw.githubusercontent.com/jupyter/nbformat/refs/heads/main/tests/test4.5.ipynb",
        {"__future__", "IPython"},
    ),
}


def diff_summary(s1: set, s2: set):
    equal = s1 == s2
    if equal:
        print("Sets are equal")
        return True
    only_in_s1 = s1.difference(s2)
    only_in_s2 = s2.difference(s2)
    if only_in_s1:
        print(f"Only in Set1: {only_in_s1}")
    if only_in_s2:
        print(f"Only in Set2: {only_in_s2}")
    return False


def test_notebook_imports(test: Test):
    imports = get_notebook_imports(test.data)
    res = diff_summary(test.imports, imports)

    # assert imports == test.imports, f"Imports do not match\nResolved imports: {imports}\nTest Imports: {test.imports}"


if __name__ == "__main__":
    for name, t in versions_tests.items():
        print(name)
        test_notebook_imports(t)
    # for t in file_tests:
    #     test_notebook_imports(t)
