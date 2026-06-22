# wisteria_submit
utility for submiting jobs in Wisteria

## Install

```
pip install --upgrade git+ssh://git@github.com/taura/wisteria_submit.git
```

## Usage

In a Jupyter cell:

```
import wisteria_submit
```

then submit a job with one of the cell magics:

```
%%bash_submit
#PJM -L rscgrp=lecture-a
#PJM -o 0output.txt
#PJM -j
...your job script...
```

`%%bash_submit_a` and `%%bash_submit_o` are also provided; they prepend a set
of default `#PJM` directives for the GPU (`lecture-a`) and node (`lecture-o`)
queues respectively, so the cell only needs the actual commands.

### About `#PJM -o`

The job's standard output (and error) is captured by this tool and streamed
back to you live, so the scheduler's own `-o` output file is not used. It
still has to point at a real file on the Lustre filesystem (e.g. `/dev/null`
is rejected), so just give it something like `0output.txt` — nothing is ever
written there, so the name does not matter:

```
#PJM -o 0output.txt
#PJM -j
```

### Command line (`sub`, `sub_a`, `sub_o`)

Installing also provides `sub`, `sub_a`, and `sub_o` commands, which work like
`pjsub` — give them a script file:

```
sub   job.sh   # no default #PJM directives (put them in job.sh yourself)
sub_a job.sh   # defaults for the GPU  (lecture-a) queue
sub_o job.sh   # defaults for the node (lecture-o) queue
```

With no file argument, the script is read from standard input:

```
sub_a <<'EOF'
echo hello
EOF
```
