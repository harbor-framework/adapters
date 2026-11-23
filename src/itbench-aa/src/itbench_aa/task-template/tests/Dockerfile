# Verifier image for the separate verifier sandbox ([verifier].environment_mode
# = "separate" in task.toml). Harbor builds this from the tests/ directory, so
# everything the grader needs must live here: test.sh, grade.py, matching.py,
# and the per-scenario ground_truth.yaml rendered by the adapter.
#
# The ground-truth key is already public in the source HF dataset
# (ArtificialAnalysis/ITBench-AA) and these images are local-only, so baking
# it in adds no exposure; the invariant that matters -- the key never enters
# the agent image or the instruction -- still holds.
FROM docker.io/library/python:3.13-slim

# Match the pin the grader was validated with (same major/minor as the agent
# image's Python) so grading behavior cannot drift between environments.
RUN pip install --no-cache-dir pyyaml==6.0.3

# Bake the grader in at /tests (Harbor skips the runtime tests/ upload for
# dedicated verifier images) and drop the Dockerfile from the image layer.
COPY . /tests/
RUN chmod +x /tests/test.sh && rm -f /tests/Dockerfile

WORKDIR /tests
