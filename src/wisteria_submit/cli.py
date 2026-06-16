"""Command-line entry point: ``sub``.

Submits a job to Wisteria by reusing :func:`wisteria_submit.submit.bash_submit`.

Usage::

    sub [-f FILENAME] -- COMMAND [ARGS...]

- Without ``-f``: the command line given after ``--`` is submitted, i.e.
  ``bash_submit("", COMMAND)``.
- With ``-f FILENAME``: the contents of FILENAME, followed by whatever comes
  after ``--``, are submitted together.
"""

import argparse
import sys

from .submit import bash_submit


def split_argv(argv):
    """Split argv into (options_before_dashdash, command_after_dashdash)."""
    if "--" in argv:
        i = argv.index("--")
        return argv[:i], argv[i + 1:]
    return argv, []


def build_cell(filename, command):
    """Build the job-script text to submit."""
    command_line = " ".join(command)
    if filename is None:
        return command_line
    with open(filename) as fp:
        contents = fp.read()
    if command_line:
        if not contents.endswith("\n"):
            contents += "\n"
        return contents + command_line
    return contents


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    options, command = split_argv(list(argv))

    parser = argparse.ArgumentParser(
        prog="sub",
        description="Submit a job to Wisteria.",
        epilog="Place the command to run after '--'.",
    )
    parser.add_argument(
        "-f", "--file", dest="file", default=None,
        help="file whose contents are submitted (plus anything after '--')",
    )
    args = parser.parse_args(options)

    if args.file is None and not command:
        parser.error("nothing to submit: give -f FILENAME and/or a command after '--'")

    cell = build_cell(args.file, command)
    bash_submit("", cell)
    return 0


if __name__ == "__main__":
    sys.exit(main())
