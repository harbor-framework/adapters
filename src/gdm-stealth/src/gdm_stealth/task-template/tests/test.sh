#!/bin/bash
# Harbor verifier: reward comes from the episode outcome written by
# the trusted parity custom agent (see verify.py header).
mkdir -p /logs/verifier
python3 /tests/verify.py "{dataset_name}" "{sample_key}" | tail -n 1 > /logs/verifier/reward.txt
cat /logs/verifier/reward.txt
