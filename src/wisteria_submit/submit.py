"""Core logic for submitting a job to Wisteria's batch scheduler (Fujitsu
PJM / ``pjsub``) and following it until completion.

Flow: write the user's cell verbatim to a script file -> build a small wrapper
that carries the ``#PJM`` directives and runs that script with its output
redirected to a file we name -> submit the wrapper with ``pjsub`` -> poll with
``pjstat`` until the job leaves the queue, then tail our output file live while
it runs.

We deliberately do NOT rely on the scheduler's ``#PJM -o`` file for live
output: the batch system may not create or flush it until the job ends, so it
is useless for streaming. And we do NOT edit the user's script (which may be
arbitrary multi-line shell); we only run it from the wrapper and redirect its
output. See ``extract_directives`` and ``build_wrapper``.
"""

import subprocess
import os
import re
import time


def write_cell_to_script(cell, cmd_sh):
    """Write the job-script text ``cell`` to the file ``cmd_sh``."""
    wp = open(cmd_sh, "w")
    wp.write(cell)
    wp.close()

def run_cmd(cmd):
    """Run a command (list of argv) and return (exit_status, combined_output).

    stderr is merged into stdout so a single string captures everything.
    """
    result = subprocess.run(cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,  # stderrをstdoutに統合
                            text=True)
    out = result.stdout
    status = result.returncode
    return (status, out)

def submit_job(a_sh):
    """Submit script file ``a_sh`` with ``pjsub`` and extract the job id.

    Returns (status, output, job_id). ``job_id`` is None if the submission
    output did not contain the expected "Job <id> submitted." message.
    """
    status, out = run_cmd(["pjsub", a_sh])
    # Parse the job id out of e.g.:
    # [INFO] PJM 0000 pjsub Job 7280061 submitted.
    m = re.search(r"pjsub Job (?P<jobid>\d+) submitted.", out)
    if m is None:
        job_id = None
    else:
        job_id = m.group("jobid")
    return status, out, job_id

def stream_new_output(fp):
    """Print whatever ``fp`` has accumulated since the last call, unbuffered.

    ``fp`` is an open file positioned at the last byte we already printed.
    Reads everything appended since then and writes it straight through with
    ``flush=True`` so nothing is held back on our (the reader's) side.
    Returns True if anything was printed.
    """
    data = fp.read()
    if data:
        print(data, end="", flush=True)
        return True
    return False

def wait_finish(job_id, output_txt=None):
    """Poll ``pjstat`` until the job leaves the queue and finishes running.

    Phase 1: wait while the job is QUEUED, printing the status table once and
    then the job's status line on each poll.

    Phase 2: once RUNNING, tail the job's output file (``output_txt``, the
    file the injected ``exec > ... 2>&1`` redirects stdout+stderr into) and
    echo new content live until the job is no longer RUNNING, doing a final
    read afterwards to catch anything written between the last poll and exit.
    If ``output_txt`` is None we fall back to printing a dot per poll.

    Note on buffering: we read incrementally and print with ``flush=True`` so
    the reader side never buffers. Whether output appears promptly still
    depends on the *job program* flushing its own stdout -- when stdout is a
    file (not a tty) libc uses block buffering, so long-running programs may
    need ``stdbuf -oL -eL <cmd>`` / ``PYTHONUNBUFFERED=1`` / fflush to show
    progress in real time.
    """
    i = 0
    # Phase 1: wait out the queue. Print the full table on the first poll,
    # then just the line mentioning this job id thereafter.
    while 1:
        status, out = run_cmd(["pjstat", job_id])
        if i == 0:
            print(out, end="")
        else:
            for line in out.split("\n"):
                if job_id in line:
                    print(line)
        if "QUEUED" not in out:
            break
        time.sleep(1.0)
        i += 1
    # Phase 2: job has started; tail its output file until it finishes.
    if output_txt is None:
        # No output file to tail: keep the old dot-per-poll progress display.
        while 1:
            status, out = run_cmd(["pjstat", job_id])
            if "RUNNING" not in out:
                break
            print(".", end="", flush=True)
            time.sleep(1.0)
        print()
        return

    print("===== BEGIN output =====")
    fp = None
    while 1:
        # The output file may not exist until the job starts writing; open it
        # lazily once it appears.
        if fp is None and os.path.exists(output_txt):
            fp = open(output_txt)
        if fp is not None:
            stream_new_output(fp)
        status, out = run_cmd(["pjstat", job_id])
        if "RUNNING" not in out:
            break
        time.sleep(0.5)
    # Final read: the job may have written more (and exited) since the last
    # poll, so flush whatever remains before declaring the output complete.
    if fp is None and os.path.exists(output_txt):
        fp = open(output_txt)
    if fp is not None:
        stream_new_output(fp)
        fp.close()
    print("===== END output =====")

def read_output(output_txt):
    """Read the job's output file and print it framed by BEGIN/END markers."""
    fp = open(output_txt)
    out = fp.read()
    fp.close()
    print(f"""===== BEGIN output =====
{out}===== END output =====""")

def parse_args_to_dict(arg_string):
    """Parse the magic's line argument (e.g. ``--script foo.sh``) into a dict.

    Recognizes ``--key value`` pairs; a ``--key`` with no following value (or
    followed by another ``--key``) becomes a boolean True flag. Tokens that
    are not ``--`` options are ignored.
    """
    import shlex
    # シェル風の文字列をトークンに分解（空白・引用符対応）
    tokens = shlex.split(arg_string)
    # 辞書に変換
    result = {}
    i = 0
    while i < len(tokens):
        if tokens[i].startswith("--"):
            key = tokens[i][2:]  # "--" を除く
            if i + 1 < len(tokens) and not tokens[i + 1].startswith("--"):
                value = tokens[i + 1]
                i += 2
            else:
                value = True  # 値がなければフラグとして True
                i += 1
            result[key] = value
        else:
            i += 1  # 想定外のトークンはスキップ
    return result
    
def extract_directives(cell):
    """Return the ``#PJM`` directive lines from the user's cell, in order.

    ``#PJM`` lines are ordinary shell comments, so they are harmless when the
    cell is run as a plain script -- but the scheduler reads them from whatever
    file is handed to ``pjsub``. We lift them out and put them in the wrapper
    (see ``build_wrapper``).
    """
    p = re.compile(r"^\s*#PJM\b")
    return [line for line in cell.split("\n") if p.match(line)]

def build_wrapper(directives, cmd_sh, output):
    """Build the wrapper script that ``pjsub`` actually submits.

    The wrapper carries the ``#PJM`` directives (so the scheduler sees them)
    and a single line that runs the user's untouched script with its merged
    stdout/stderr redirected to ``output``::

        #!/bin/bash
        #PJM ...directives...

        stdbuf -oL -eL bash cmd.sh > output 2>&1

    Because the user's script is left verbatim in ``cmd_sh`` and only *run*
    (not transformed), arbitrary shell -- multi-line ``for`` loops, here-docs,
    functions -- works unchanged. ``stdbuf -oL -eL`` line-buffers stdout/stderr
    (the setting is inherited via the environment by dynamically linked child
    programs too), which keeps the redirected ``output`` flowing in near real
    time so the live tail in :func:`wait_finish` actually shows progress.
    """
    header = "\n".join(["#!/bin/bash"] + directives)
    body = f"stdbuf -oL -eL bash {cmd_sh} > {output} 2>&1"
    return header + "\n\n" + body + "\n"

def submit_cell(line, cell):
    """End-to-end submission: write user script + wrapper, submit, tail live.

    ``line`` is the magic's argument line; recognized options:
    ``--script FILE`` (user-script filename, default ``cmd.sh``),
    ``--wrapper FILE`` (wrapper filename, default ``wrapper.sh``),
    ``--out FILE`` (output filename we tail, default ``<script>.out``).
    ``cell`` is the job-script body, used verbatim.

    We submit a small wrapper (``#PJM`` directives + ``bash cmd.sh > out 2>&1``)
    rather than the cell itself, so the output file is one we name and control
    and can follow live -- independent of the scheduler's ``#PJM -o`` file,
    which may not be created/flushed until the job ends. Returns None.
    """
    dic = parse_args_to_dict(line)
    cmd_sh = dic.get("script", "cmd.sh")
    wrapper_sh = dic.get("wrapper", "wrapper.sh")
    # Output file we own and tail. Defaults next to the script; overridable.
    output = dic.get("out", cmd_sh + ".out")

    # User's script goes to disk untouched; the wrapper carries the directives
    # and redirects the script's output to the file we tail.
    write_cell_to_script(cell, cmd_sh)
    wrapper = build_wrapper(extract_directives(cell), cmd_sh, output)
    write_cell_to_script(wrapper, wrapper_sh)

    # Remove any leftover output file from a previous run so tailing only ever
    # shows this job's freshly written content. (The wrapper's ``>`` also
    # truncates it, but this clears it before the job starts.)
    if os.path.exists(output):
        os.remove(output)

    status, out, job_id = submit_job(wrapper_sh)
    if job_id is None:
        print(f"""===== failed to submit job =====
{out}""")
        return None
    # wait_finish tails ``output`` live while the job runs.
    wait_finish(job_id, output)
    return None

# The three functions below are the cell magics registered with IPython.
# Each receives (line, cell): `line` is the text on the %%magic line and
# `cell` is the body below it.

def bash_submit(line, cell):
    """``%%bash_submit``: submit the cell verbatim (user supplies all #PJM)."""
    return submit_cell(line, cell)

def bash_submit_a(line, cell):
    """``%%bash_submit_a``: prepend default #PJM options for the GPU (-a) queue.

    Targets rscgrp=lecture-a with 1 GPU and 9 OpenMP threads.
    """
    opt = """
#PJM -L rscgrp=lecture-a
#PJM -L elapse=0:01:00
#PJM -L gpu=1
#PJM --omp thread=9
#PJM -g gt69
#PJM -j
#PJM -o /dev/null
"""
    return submit_cell(line, opt + cell)

def bash_submit_o(line, cell):
    """``%%bash_submit_o``: prepend default #PJM options for the (-o) node queue.

    Targets rscgrp=lecture-o with 1 node and 48 OpenMP threads.
    """
    opt = """
#PJM -L rscgrp=lecture-o
#PJM -L elapse=0:01:00
#PJM -L node=1
#PJM --omp thread=48
#PJM -g gt69
#PJM -j
#PJM -o /dev/null
"""
    return submit_cell(line, opt + cell)


def register_magics(ipython=None):
    """Register the bash_submit cell magics with the active IPython shell.

    Called automatically on import when run inside IPython; safe to call
    explicitly (e.g. from ``load_ipython_extension``). Does nothing when no
    IPython shell is available.
    """
    if ipython is None:
        try:
            from IPython import get_ipython
            ipython = get_ipython()
        except ImportError:
            ipython = None
    if ipython is None:
        return False
    ipython.register_magic_function(bash_submit, "cell", "bash_submit")
    ipython.register_magic_function(bash_submit_a, "cell", "bash_submit_a")
    ipython.register_magic_function(bash_submit_o, "cell", "bash_submit_o")
    return True


# Register magics automatically when imported inside a running IPython shell.
register_magics()

