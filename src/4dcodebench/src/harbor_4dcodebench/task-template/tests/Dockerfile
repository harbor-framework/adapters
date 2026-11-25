# Verifier image for 4DCodeBench case {case_key}.
#
# {scorer_image} is the upstream scorer image (harness/scorer/Dockerfile at 4DCodeBench
# commit {upstream_commit}) with the scorer checkpoints at /checkpoints; the adapter
# README shows how to build it. This image also holds the case's private reference
# data. It is used only by the separate verifier: the agent's container never sees it.
FROM {scorer_image}

# The scorer image's ENTRYPOINT is `python -m scorer`; Harbor starts the container
# with its own command and runs /tests/test.sh in it.
ENTRYPOINT []

# The reference video, world, annotation and estimates, in the scorer's layout.
COPY bench/ /bench/
COPY test.sh run_verifier.py rewards.py case.json /tests/
RUN chmod +x /tests/test.sh

WORKDIR /workspace
