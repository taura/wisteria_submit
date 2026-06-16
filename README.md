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
...your job script...
```

### Command line (`sub`)

Installing also provides a `sub` command:

```
# submit the command after '--'
sub -- echo hello

# submit the contents of a script file, optionally with extra commands appended
sub -f job.sh -- echo done
```
