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
#PJM -L rscgrp=lecture-o
#PJM -o 0output.txt
...your job script...
```
