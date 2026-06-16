"""wisteria_submit: utility for submitting jobs on Wisteria from Jupyter.

Importing this package registers the following cell magics with IPython:

    %%bash_submit
    %%bash_submit_a
    %%bash_submit_o

Usage in a Jupyter cell::

    %%bash_submit
    #PJM -L rscgrp=lecture-o
    #PJM -o 0output.txt
    ...your job script...
"""

from .submit import (
    bash_submit,
    bash_submit_a,
    bash_submit_o,
    submit_cell,
    register_magics,
)

__all__ = [
    "bash_submit",
    "bash_submit_a",
    "bash_submit_o",
    "submit_cell",
    "register_magics",
]

__version__ = "0.1.0"


def load_ipython_extension(ipython):
    """Allow loading via ``%load_ext wisteria_submit``.

    The cell magics are already registered as a side effect of importing
    :mod:`wisteria_submit.submit`; this hook exists so the package also works
    with the explicit ``%load_ext`` mechanism.
    """
    register_magics(ipython)
