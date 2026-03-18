import argparse
import shutil
from pathlib import Path
from warnings import deprecated

from envdeps.common import DEFAULT_IGNORES, BaseCommand, ExportCommand, ShowCommand
from envdeps.main import EnvDeps
from envdeps.pkgs import resolve_active_env_prefix
from envdeps.utils import resolve_paths


def get_terminal_width():
    try:
        size = shutil.get_terminal_size()
        return size.columns
    except OSError:
        return 80


def strlist(val: str, sep=","):
    if not val:
        return None
    return val.split(sep)


@deprecated("IMPLEMENTED in 'BaseCommand._resolve_base_args()'")
def resolve_verify_args(args: BaseCommand):
    root = args.root
    target = args.target
    resolved_root, resolved_target = resolve_paths(root, target)
    args.root = resolved_root
    args.target = resolved_target
    if args.prefix is None:
        prefix = resolve_active_env_prefix()
        if not prefix:
            raise ValueError("Python Environment Prefix could not be resolved")
        args.prefix = prefix
    if not args.prefix.exists():
        raise ValueError(
            f"Environment prefix does not exist: {args.prefix}",
            "Check current environment prefix.",
        )
    args.ignore = list(DEFAULT_IGNORES.union(args.ignore))
    return args


def show_cmd_cb(args: BaseCommand):
    args = ShowCommand.from_base(args)
    print("Hello from command 'show'\n\n")
    envdeps = EnvDeps(args.target, args.root, args.prefix, args.ignore)
    envdeps.show(args.format, args.verbose)


def export_cmd_cb(args: BaseCommand):
    args = ExportCommand.from_base(args)
    print("Hello from command 'export'")
    print(args)


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
    dest="prefix",
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


def make_parser():
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
    show_command.set_defaults(func=show_cmd_cb)
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
    export_command.set_defaults(func=export_cmd_cb)

    return parser


def parse_args(argv: list[str]):
    parser = make_parser()
    ns = BaseCommand()
    args = parser.parse_args(argv, ns)
    args = args._resolve_base_args()
    args.func(args)
    # print(args)
    # args = args._resolve_base_args()
    # print(args)
    # if args.command == "export":
    #     export_cmd_cb(args)
    # else:
    #     show_cmd_cb(args)


# SEE: Example namespace object
# Namespace(command='show', ignore=[], env_prefix=None, root=PosixPath('.'), target=PosixPath('envdeps'), format='text', verbose=True)

if __name__ == "__main__":
    parse_args(["show", "--target=envdeps", "--root=.", "--format=table", "--verbose"])
    # parse_args(
    #     [
    #         "export",
    #         "--ignore=TEST_IGNORE,__pycache__",
    #         # "--root=.",
    #         "--format=requirements",
    #         "--merge",
    #         "--update-existing",
    #         "--specifier='>='",
    #         "--target=envdeps",
    #     ]
    # )
