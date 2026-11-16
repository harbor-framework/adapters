# Verifier image. The verifier runs in its own container, so the agent never
# sees the rubric, the grader library or the judge client.
FROM python:3.12-slim

# The official DRACO grader library, pinned to the commit whose default judge
# prompt matches the paper's Appendix C.5, and LiteLLM as the judge client.
RUN pip install --no-cache-dir \
        "litellm==1.103.4" \
        "https://github.com/paper-instruments/rubric/archive/eb0755a1c4682cd20c490550bd6260ccea8bafe0.tar.gz"

COPY . /tests/
