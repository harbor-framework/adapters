FROM python:3.12-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df
ENV PYTHONUTF8=1 LITELLM_LOCAL_MODEL_COST_MAP=True PYTHONPATH=/adapter/src BIZ_UPSTREAM_ROOT=/upstream
COPY src/bizagentbench/requirements.txt /requirements.txt
RUN pip install --no-cache-dir --require-hashes -r /requirements.txt
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir pytest==8.4.2 iniconfig==2.3.1 pluggy==1.7.0
WORKDIR /adapter
# A local clone materializes Git's LF blob contents even when /upstream is a
# Windows checkout. It never modifies the read-only caller checkout.
CMD ["sh", "-c", "git -c core.autocrlf=false clone --no-hardlinks /upstream /tmp/bizagentbench-test-source && BIZ_UPSTREAM_ROOT=/tmp/bizagentbench-test-source python -m pytest -q -p no:cacheprovider /adapter/tests"]
