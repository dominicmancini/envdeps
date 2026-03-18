import argparse
import os
import shutil
from pathlib import Path

from envdeps.common import BaseCommand, ExportCommand, ShowCommand
from envdeps.main import EnvDeps


# NOTE: To get colorized output, replace '... = argparse.ArgumentParser(..)' with '... =
# RichArgumentParser(...)'
class RichArgumentParser(argparse.ArgumentParser):
    pass
    # def print_help(self, file=None):
    #     help_text = self.format_help()
    #     text = Text(help_text)
    #
    #     # Colorize section headings (e.g. "positional arguments:", "options:")
    #     for match in re.finditer(r"^[a-zA-Z ]+:$", help_text, re.MULTILINE):
    #         text.stylize("bold green", match.start(), match.end())
    #
    #     # Colorize short options like -h, -v
    #     for match in re.finditer(r"(?<!\w)-[a-zA-Z]", help_text):
    #         text.stylize("bold cyan", match.start(), match.end())
    #
    #     # Colorize long options like --help, --verbose
    #     for match in re.finditer(r"--[a-zA-Z\-]+", help_text):
    #         text.stylize("bold cyan", match.start(), match.end())
    #
    #     # Colorize the usage: prefix
    #     for match in re.finditer(r"^usage:", help_text, re.MULTILINE):
    #         text.stylize("bold yellow", match.start(), match.end())
    #
    #     console.print(text)


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


def show_cmd_cb(args: BaseCommand):
    args = ShowCommand.from_base(args)
    print("Hello from command 'show'\n\n")
    envdeps = EnvDeps(args.target, args.root, args.prefix, args.ignore)
    envdeps.show(args.format, args.verbose)


def export_cmd_cb(args: BaseCommand):
    args = ExportCommand.from_base(args)
    print("Hello from command 'export'")
    write = not args._debug
    envdeps = EnvDeps(args.target, args.root, args.prefix, args.ignore)
    envdeps.export(
        args.path,
        args.format,
        args.specifier,
        args.merge,
        args.remove_unknown,
        args.remove_unused,
        args.update_existing,
        _write=write,
    )


parent_parser = RichArgumentParser(add_help=False)
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
parent_parser_group.add_argument(
    "-d",
    "--debug",
    dest="_debug",
    action="store_true",
    help="DEV: Do not actually write to `path` (for 'export'). Enable additional logging.",
)
parent_parser_group.add_argument(
    "--color",
    action=argparse.BooleanOptionalAction,
    default=True,
    help="Enable/Disable colorized output (enabled by default).",
)


def make_parser():
    parser = RichArgumentParser(description="Main Envdeps prog.")
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
        default="",
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
    # NOTE: Finally, get the path to the desired output file
    export_command.add_argument(
        "path",
        type=Path,
        # default=None,
        help="Path to the desired output file. Relative paths are interpreted relative to `--root` (cwd if unspecified). If `format` is not specified, it will be determined from this path's extension. ",
    )

    export_command.set_defaults(func=export_cmd_cb)
    return parser


def parse_args(argv: list[str]):
    parser = make_parser()
    ns = BaseCommand()
    args = parser.parse_args(argv, ns)
    if args.color == False:
        os.environ["NO_COLOR"] = "1"
        from envdeps import output

        output.console.no_color = True
    args.func(args)
    # print(args._resolved)
    # args = args._resolve_base_args()
    # print(args._resolved)


test_args = {
    "show": [
        "show",
        "--target=envdeps",
        "--root=.",
        "--format=text",
        "--verbose",
        # "--no-color",
    ],
    "export": [
        "export",
        "--target=envdeps",
        "--root=.",
        "--format=pyproject",
        "--debug",
        "--merge",
        "--remove-unused",
        "requirements-test.txt",
    ],
}

if __name__ == "__main__":
    # parse_args(test_args["show"])
    parse_args(test_args["export"])
    # parse_args(["--help"])
