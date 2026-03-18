import os
import reprlib
from pathlib import Path
from typing import Any, Callable

from envdeps.environment import DependencyResolver
from envdeps.scanner import FileImports

prefix = os.getenv("VIRTUAL_ENV")
assert prefix is not None, "Prefix is none"
toabs = lambda path: Path(path).expanduser()

select: Callable[[str], dict[str, Any]] = lambda *keys: {key: data[key] for key in keys}

data = dict(
    prefix=Path(prefix),
    root=toabs("~/projects/envdeps"),
    target=toabs("~/projects/envdeps/envdeps"),
    ignore_dirs=["__pycache__", "dev", "tests", ".git", ".pytest_cache"],
)


def test_dep_resolver(prefix: Path, root: Path, file_imports: FileImports):
    dr = DependencyResolver(prefix, root)
    for file, imps in file_imports.items():
        for imp in imps:
            dr.add_import(imp, str(file))
    for key, dep in dr.resolved.items():
        print(dep.imported_modules)


# scanner = ProjectScanner(**select("target", "ignore_dirs"))
# all_imports, file_imports = scanner.scan()
# # test_dep_resolver(data["prefix"], data["root"], file_imports)  # type: ignore
# dr = DependencyResolver(**select("prefix", "root"))
# for file, imps in file_imports.items():
#     for imp in imps:
#         dr.add_import(imp, str(file))
# reqs = dr.to_requirement_set()
# print(reqs)


width = 10
l = ["Apples", "Oranges", "Bananas", "pies"]
r = reprlib.Repr(maxstring=10, fillvalue="")
print(f"{r.repr_str(str(r), 1)} (+{len(l) - 1})")
# print(str(l))

# r = reprlib.Repr(maxlist=2)
# print(f"{r.repr_list(l, 1)} (+{len(l) - r.maxlist})")

# n_items = cntchars(l, width)
# n_item = n_items or 2
# print(textwrap.shorten(", ".join(l), width=width))


# env = Environment(**select("prefix", "root", "ignore_dirs"))
# pkg_imports = env.resolve(all_imports)
# path_to_pkg_imports = env.get_package_imports_by_file(pkg_imports, file_imports)
#
# dists = env.scan_and_collect_packages(all_imports)
# req_set = RequirementSet()
# dist_imports = env.resolve(all_imports)
