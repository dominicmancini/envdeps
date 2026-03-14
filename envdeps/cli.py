import argparse
import shutil
from pathlib import Path

from loguru import logger

from envdeps.main import ProjectDependencies


def get_terminal_width():
    try:
        size = shutil.get_terminal_size()
        return size.columns
    except OSError:
        return 80


def strlist(val: str, sep=","):
    values = []
    if not val:
        return None
    return val.split(sep)


parent_parser = argparse.ArgumentParser(add_help=False)
parent_parser_group = parent_parser.add_argument_group("Base Arguments")
parent_parser_group.add_argument(
    "-i",
    "--ignore",
    type=strlist,
    default=[],
    help="Comma seperated list of directories to ignore.",
)
parent_parser_group.add_argument(
    "-e",
    "--env-prefix",
    type=Path,
    help="python environment prefix. Resolves to active venv/version.",
)
parent_parser_group.add_argument(
    "-r",
    "--root",
    type=Path,
    default=None,
    help="Root of the project to scan. Defaults to CWD.",
)
parent_parser_group.add_argument(
    "-t",
    "--target",
    type=Path,
    help="Target directory containing source files.",
)


def make_new_parser():
    parser = argparse.ArgumentParser(description="Main Envdeps prog.")
    subparsers = parser.add_subparsers(
        dest="command",
        help="Available (sub)commands",
        # required=True,
    )
    # SECTION: 'show' command
    show_command = subparsers.add_parser(
        "show",
        help="Inspect used project dependencies (Read-only)",
        parents=[parent_parser],
    )
    show_command.add_argument(
        "-f",
        "--format",
        choices=["text", "json", "table"],
        type=str,
        default="text",
        help="Format to display used dependencies. Useful for piping into other tools.",
    )
    show_command.add_argument(
        "--verbose",
        action="store_true",
        help="Show which files & imports triggered each dependency.",
    )
    # SECTION: 'export' command

    export_command = subparsers.add_parser(
        "export",
        help="Scan used project dependencies and export to desired format.",
        parents=[parent_parser],
    )
    export_command.add_argument(
        "-f",
        "--format",
        choices=["pyproject", "requirements"],
        type=str,
        help="Dependency format to use (if blank, will auto-detect based on file extension of 'path')",
    )
    export_command.add_argument(
        "-s",
        "--specifier",
        type=str,
        default=None,
        help="The version operator to use (e.g. '>=', '=='). If blank, no version specifier is used.",
    )

    merge_group_export = export_command.add_argument_group(
        "Merge Options", "Options to control merge behavior."
    )
    merge_group_export.add_argument(
        "-m",
        "--merge",
        action="store_true",
        help="Merge with existing dependencies listed in 'path'.",
    )
    merge_group_export.add_argument(
        "--remove-unknown",
        action="store_true",
        help="Remove unknown entries in dependencies.",
    )
    merge_group_export.add_argument(
        "--remove-unused",
        action="store_true",
        help="Remove listed dependencies that are not used in project (not found in scan).",
    )
    merge_group_export.add_argument(
        "--update-existing",
        action="store_true",
        help="Update the specifier & version of existing dependencies to use `--specifier` with installed package version.",
    )
    return parser


def make_parser():
    # NOTE: Parent parser is for a comment set of options that can be shared by
    # multiple commands.
    parser = argparse.ArgumentParser(description="Main envdeps program.")
    subparsers = parser.add_subparsers(
        dest="command", required=True, help="Available (sub)commands"
    )
    # Subcmd: `imports` (print all used imports)
    imports_parser = subparsers.add_parser(
        "imports", help="Get all imports from source files.", parents=[parent_parser]
    )
    reqs_command = subparsers.add_parser(
        "reqs",
        help="Scan files and generate requirements (TODO)",
        parents=[parent_parser],
    )
    reqs_command.add_argument(
        "-p", "--print", action="store_true", help="Print to stdout?"
    )
    reqs_command.add_argument(
        "-o",
        "--out",
        nargs="?",
        type=Path,
        action="store",
        help="Output file to write to",
        const="requirements.txt",
        dest="output",
    )
    reqs_command.add_argument(
        "-m",
        "--mode",
        type=str,
        default="",
        help="Operator to use for version specifier (eg. '>=', '=='). Omit or leave empty for no version specifier",
    )
    pyproject_command = subparsers.add_parser(
        "pyproject", help="Scan files and update pyproject.toml"
    )
    pyproject_command.add_argument(
        "-o",
        "--out",
        nargs="?",
        type=Path,
        action="store",
        help="Output pyproject.toml file",
        const="pyproject.toml",
        dest="output",
    )
    return parser


def reqs(args: argparse.Namespace):
    print("TODO: Implement")
    # pd = ProjectDependencies(args.env_prefix, args.target_dir, args.ignore_dir)


def imports(args: argparse.Namespace):
    logger.info("Hello from Imports")
    # sys.exit(0)
    pd = ProjectDependencies(args.env_prefix, args.target, args.ignore, root=args.root)
    pkg_imports = pd.resolve_imported_packages()
    width = get_terminal_width()
    print(f"{'Package':<20}{'Imports':>20}")
    print("=" * get_terminal_width())
    for pkg, imports in pkg_imports.items():
        print(f"{pkg:<20}{','.join(imports):>20}")


def parse_args(argv: list[str]):
    parser = make_parser()
    args = parser.parse_args(argv)
    # print(args)
    # if args.command == "imports":
    #     imports(args)
    # else:
    #     print("Cmd not implemented yet.")


if __name__ == "__main__":
    parser = make_new_parser()
    args = parser.parse_args(
        ["export", "--ignore=__pycache__", "--target=envdeps", "--root=.", "--merge"]
    )
    print(args)
    # parser = make_parser()
    # args = parser.parse_args(["reqs", "--root=.", "envdeps"])
    # print(args)
    # parse_args(
    #     [
    #         "pyproject",
    #         "--help",
    #         # "--out",
    #         # "--ignore",
    #         # "__pycache__,resources,tests",
    #         # "envdeps",
    #     ]
    # )
