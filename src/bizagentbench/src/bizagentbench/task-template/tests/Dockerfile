FROM python:3.12-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df
ENV PYTHONUTF8=1 LITELLM_LOCAL_MODEL_COST_MAP=True
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir --require-hashes -r /requirements.txt
COPY upstream.tar /upstream.tar
RUN mkdir /opt/bizagentbench && tar -xf /upstream.tar -C /opt/bizagentbench
COPY . /tests/
WORKDIR /tests
