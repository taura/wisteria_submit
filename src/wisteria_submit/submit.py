import subprocess
import re
import time


def write_cell_to_script(cell, cmd_sh):
    wp = open(cmd_sh, "w")
    wp.write(cell)
    wp.close()

def run_cmd(cmd):
    result = subprocess.run(cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,  # stderrをstdoutに統合
                            text=True)
    out = result.stdout
    status = result.returncode
    return (status, out)

def submit_job(a_sh):
    status, out = run_cmd(["pjsub", a_sh])
    # [INFO] PJM 0000 pjsub Job 7280061 submitted.
    m = re.search(r"pjsub Job (?P<jobid>\d+) submitted.", out)
    if m is None:
        job_id = None
    else:        
        job_id = m.group("jobid")
    return status, out, job_id

def wait_finish(job_id):
    i = 0
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
    while 1:
        status, out = run_cmd(["pjstat", job_id])
        if "RUNNING" not in out:
            break
        print(".", end="", flush=True)
        time.sleep(1.0)
    print()

def read_output(output_txt):
    fp = open(output_txt)
    out = fp.read()
    fp.close()
    print(f"""===== BEGIN output =====
{out}===== END output =====""")

def parse_args_to_dict(arg_string):
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
    
def get_output(fcell):
    p = re.compile(r"#PJM\s+\-o\s+(?P<output>.*)")
    output = None
    for line in fcell.split("\n"):
        m = p.match(line)
        if m:
            output = m.group("output")
    return output
    
def submit_cell(line, cell):
    dic = parse_args_to_dict(line)
    cmd_sh = dic.get("script", "cmd.sh")
    fcell = cell # cell.format(**dic)
    output = get_output(fcell)
    write_cell_to_script(fcell, cmd_sh)
    status, out, job_id = submit_job(cmd_sh)
    if job_id is None:
        print(f"""===== failed to submit job =====
{out}""")
        return None
    wait_finish(job_id)
    if output is None:
        print("===== could not get output file name (specify with #PJM -o filename) =====")
        return None
    else:
        return read_output(output)

def bash_submit(line, cell):
    return submit_cell(line, cell)

def bash_submit_a(line, cell):
    opt = """
#PJM -L rscgrp=lecture-a
#PJM -L elapse=0:01:00
#PJM -L gpu=1
#PJM --omp thread=9
#PJM -g gt47
#PJM -j
#PJM -o 0output.txt
"""
    return submit_cell(line, opt + cell)

def bash_submit_o(line, cell):
    opt = """
#PJM -L rscgrp=lecture-o
#PJM -L elapse=0:01:00
#PJM -L node=1
#PJM --omp thread=48
#PJM -g gt47
#PJM -j
#PJM -o 0output.txt
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

