FROM python:3.12-slim-bookworm

# Separate verifier image: the official VitaBench package (for the rubric
# evaluator) plus the grading files. The agent never sees this image, so the
# task definition with its rubrics (tests/config.json) can live here.

ARG VITABENCH_REPO="https://github.com/meituan-longcat/vitabench.git"
ARG VITABENCH_COMMIT="742e240855bf8686a0842360749d5ea970ea3987"

ENV VITABENCH_ROOT=/opt/vitabench
ENV VITA_MODEL_CONFIG_PATH=/opt/vita_models.yaml
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && git clone "${VITABENCH_REPO}" "${VITABENCH_ROOT}" \
    && git -C "${VITABENCH_ROOT}" checkout "${VITABENCH_COMMIT}" \
    && rm -rf "${VITABENCH_ROOT}/.git" \
    && pip install --no-cache-dir -e "${VITABENCH_ROOT}" \
    && apt-get purge -y --auto-remove git \
    && rm -rf /var/lib/apt/lists/*

# vita.config imports models.yaml at import time; evaluate.py regenerates it.
RUN printf 'default:\n  base_url: ""\n  headers: {}\nmodels: []\n' > "${VITA_MODEL_CONFIG_PATH}"

COPY . /tests/
RUN chmod +x /tests/test.sh /tests/evaluate.py
