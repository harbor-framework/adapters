#!/usr/bin/env bash
# Oracle for 4DCodeBench real-world case {case_key}: UNRESOLVED.
#
# Real-world cases have no reference 4D world; they are scored against the video and
# the published estimates only. No reference submission exists, so this oracle writes
# nothing and exits with status 1. How real-world oracle validation is accepted is an
# open decision recorded in the adapter README.
echo "oracle: UNRESOLVED for real-world case {case_key}: the benchmark has no reference 4D world" >&2
exit 1
