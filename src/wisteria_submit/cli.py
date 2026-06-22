"""Command-line entry points: ``sub``, ``sub_a``, ``sub_o``.

Each submits a job to Wisteria by reusing the corresponding function from
:mod:`wisteria_submit.submit`:

- ``sub``   -> :func:`bash_submit`   (no default #PJM directives)
- ``sub_a`` -> :func:`bash_submit_a` (defaults for the GPU ``lecture-a`` queue)
- ``sub_o`` -> :func:`bash_submit_o` (defaults for the node ``lecture-o`` queue)

Usage, mirroring ``pjsub``::

    sub   a.sh
    sub_a a.sh
    sub_o a.sh

The named script file is read and submitted as the job body. With no file,
the body is read from standard input.
"""

import argparse
import sys

from .submit import bash_submit, bash_submit_a, bash_submit_o


def run(submit_fn, prog, argv):
    """Shared CLI body: read the script (file or stdin) and submit it.

    ``submit_fn`` is the submit function to call (``bash_submit`` /
    ``bash_submit_a`` / ``bash_submit_o``); ``prog`` is the command name shown
    in help/usage.
    """
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Submit a job to Wisteria (like pjsub).",
    )
    parser.add_argument(
        "script", nargs="?", default=None,
        help="job script file to submit (read from stdin if omitted)",
    )
    args = parser.parse_args(argv)

    if args.script is None:
        cell = sys.stdin.read()
    else:
        with open(args.script) as fp:
            cell = fp.read()

    submit_fn("", cell)
    return 0


def main(argv=None):
    """Entry point for ``sub`` (no default #PJM directives)."""
    return run(bash_submit, "sub", argv if argv is not None else sys.argv[1:])


def main_a(argv=None):
    """Entry point for ``sub_a`` (defaults for the GPU ``lecture-a`` queue)."""
    return run(bash_submit_a, "sub_a", argv if argv is not None else sys.argv[1:])


def main_o(argv=None):
    """Entry point for ``sub_o`` (defaults for the node ``lecture-o`` queue)."""
    return run(bash_submit_o, "sub_o", argv if argv is not None else sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
