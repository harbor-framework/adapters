#!/bin/bash
# Oracle: the PyTorch reference itself, renamed ModelNew (speedup ~1.0). It proves the
# task builds, the reference runs on the GPU, and the grader accepts a correct answer.
set -e
cp /solution/reference.py /workspace/solution.py
printf '\n\nclass ModelNew(Model):\n    pass\n' >> /workspace/solution.py
