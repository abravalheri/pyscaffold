# -*- coding: utf-8 -*-
"""
Command-Line-Interface of PyScaffold
"""
from __future__ import absolute_import, print_function

import argparse
import logging
import os.path
import shlex
import sys
import textwrap

import pyscaffold

from . import api, shell, templates, termui, utils
from .api.helpers import get_id
from .log import (
    DEFAULT_LOGGER,
    ColoredReportFormatter,
    ReportFormatter,
    logger
)

__author__ = "Florian Wilhelm"
__copyright__ = "Blue Yonder"
__license__ = "new BSD"

OSX_CONFIG = '${HOME}/Library/Application Support'
WIN_CONFIG = '${APPDATA}'
XDG_CONFIG = '${XDG_CONFIG_HOME}'
UNIX_CONFIG = '${HOME}/.config'
DEFAULT_PROFILE = 'default'


def get_config_dir():
    """Get the path used to store config data for the user.
    """
    # Check for known paths in popular OSs
    candidates = [os.path.expandvars(c)
                  for c in (OSX_CONFIG, WIN_CONFIG, XDG_CONFIG, UNIX_CONFIG)]

    for candidate in candidates:
        if os.path.exists(candidate):
            return os.path.join(candidate, 'pyscaffold')

    # If none is found, return a default
    return os.path.expanduser(os.path.join('~', '.pyscaffold'))


def get_args_file(profile):
    """Return the path to the user default arguments file.
    """
    return os.path.join(get_config_dir(),
                        (profile or DEFAULT_PROFILE) + '.args')


class ArgumentParser(argparse.ArgumentParser):
    """Enable writing several options in the same line for args from files.

    Also supports comments starting with `#` that spans to the end of each
    line, thanks to builtin `shlex` module.
    """

    def convert_arg_line_to_args(self, arg_line):
        """Split string as a list of command line arguments/options."""
        return shlex.split(arg_line, True)


def add_default_args(parser):
    """Add the default options and arguments to the CLI parser.

    Args:
        parser (argparse.ArgumentParser): CLI parser object
    """

    parser.add_argument(
        dest="project",
        help="project name",
        metavar="PROJECT")
    parser.add_argument(
        "-p",
        "--package",
        dest="package",
        required=False,
        help="package name (default: project name)",
        metavar="NAME")
    parser.add_argument(
        "-d",
        "--description",
        dest="description",
        required=False,
        help="package description (default: '')",
        metavar="TEXT")
    parser.add_argument(
        "-u",
        "--url",
        dest="url",
        required=False,
        help="package url (default: '')",
        metavar="URL")
    license_choices = templates.licenses.keys()
    parser.add_argument(
        "-l",
        "--license",
        dest="license",
        choices=license_choices,
        required=False,
        default="none",
        help="package license from {choices} (default: {default})".format(
            choices=str(license_choices), default="No license"),
        metavar="LICENSE")
    parser.add_argument(
        "-f",
        "--force",
        dest="force",
        action="store_true",
        default=False,
        help="force overwriting an existing directory")
    parser.add_argument(
        "-U",
        "--update",
        dest="update",
        action="store_true",
        default=False,
        help="update an existing project by replacing the most important files"
             " like setup.py etc. Use additionally --force to "
             "replace all scaffold files.")

    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--pretend",
        "--dry-run",
        dest="pretend",
        action="store_true",
        default=False,
        help="do not create project, but displays the log of all operations"
             " as if it had been created.")
    group.add_argument(
        "--list-actions",
        dest="command",
        action="store_const",
        const=list_actions,
        help="do not create project, but show a list of planned actions")

    version = pyscaffold.__version__
    parser.add_argument('-v',
                        '--version',
                        action='version',
                        version='PyScaffold {ver}'.format(ver=version))
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_const",
        const="CRITICAL",
        dest="log_level",
        help="suppress logs and warnings (still reporting critical errors).")


def parse_args(args):
    """Parse command line parameters

    Args:
        args ([str]): command line parameters as list of strings

    Returns:
        dict: command line parameters
    """

    # `setuptools_scm` (used to determine PyScaffold version) requires features
    # from setuptools not available for old versions, so let's check ...
    utils.check_setuptools_version()

    # Specify the functions that add arguments to the cli
    cli_creators = [
        add_default_args
    ]

    # Find any extra function that also do it
    from pkg_resources import iter_entry_points
    cli_extensions = iter_entry_points('pyscaffold.cli')
    cli_extenders = [extension.load() for extension in cli_extensions]

    # Create the argument parser
    parser = ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.fill(
            "PyScaffold is a tool for easily putting up the scaffold "
            "of a Python project."),
        fromfile_prefix_chars="@",
        epilog=(
            textwrap.fill(
                "Command line arguments can be read from a file. "
                "In order to do that, prefix the file name with a `@` symbol. "
                "For example, consider a file named `pyscaffold.args` "
                "with the following contents:") +
            "\n\n"
            "    --license mozilla\n"
            "    --with-pre-commit\n"
            "    --with-tox\n"
            "    --with-travis\n\n"
            "The command\n\n"
            "    putup mypkg @pyscaffold.args\n\n" +
            textwrap.fill(
                "will then produce a new project configured to use tox, "
                "pre-commit, travis and the Mozilla license.") +
            "\n\n" +
            textwrap.fill(
                "An argument file named `default.args` placed under the "
                "`{}` directory is automatically loaded, unless the "
                "environment variable `PYSCAFFOLD_PROFILE` is set to "
                "'none'. Alternatively, if this variable is set to a "
                "different name, a file corresponding to another profile "
                "is loaded instead. It is possible, for instance, to keep a "
                "`{}` file for personal projects and a `{}` file when working "
                "for the {} organization, switching between then using some "
                "kind of dotenv manager.".format(
                    get_config_dir(), get_args_file('default'),
                    get_args_file('mycompany'), 'My Company'))
        )
    )
    parser.set_defaults(log_level="INFO", extensions=[], command=run_scaffold)

    for augment in cli_creators + cli_extenders:
        augment(parser)

    profile = os.getenv('PYSCAFFOLD_PROFILE')
    if profile != 'none':
        args_file = get_args_file(profile)
        if os.path.exists(args_file):
            args = ['@'+args_file] + args
            # prepend default args to ensure it can be overwritten

    # Parse options and transform argparse Namespace object into common dict
    opts = vars(parser.parse_args(args))

    # Strip (back)slash when added accidentally during update
    opts['project'] = opts['project'].rstrip(os.sep)

    # Convert log level from name to actual value
    opts['log_level'] = getattr(logging, opts['log_level'])

    # Remove options with None values
    return {k: v for k, v in opts.items() if v is not None}


def configure_logger(opts):
    logging.getLogger(DEFAULT_LOGGER).setLevel(opts['log_level'])

    # if terminal supports, use colors
    stream = getattr(logger.handler, 'stream', None)
    if termui.supports_color(stream):
        logger.formatter = ColoredReportFormatter()
        logger.handler.setFormatter(logger.formatter)


def run_scaffold(opts):
    """Actually scaffold the project, calling the python API."""
    configure_logger(opts)
    api.create_project(opts)
    if opts['update'] and not opts['force']:
        note = "Update accomplished!\n" \
               "Please check if your setup.cfg still complies with:\n" \
               "http://pyscaffold.readthedocs.org/en/v{}/configuration.html"
        print(note.format(pyscaffold.__version__))


def list_actions(opts):
    """Do not create a project, just list actions considering extensions."""
    actions = api.discover_actions(opts.get('extensions', []))

    print('Planned Actions:\n')
    for action in actions:
        print(ReportFormatter.SPACING + get_id(action))


def main(args):
    """PyScaffold is a tool for putting up the scaffold of a Python project.
    """
    opts = parse_args(args)
    opts['command'](opts)


@shell.called_process_error2exit_decorator
@utils.exceptions2exit([RuntimeError])
def run():
    """Entry point for setup.py
    """
    main(sys.argv[1:])


if __name__ == '__main__':
    main(sys.argv[1:])
