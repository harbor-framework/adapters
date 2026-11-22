FROM python:3.12-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df
ENV PYTHONUTF8=1 LITELLM_LOCAL_MODEL_COST_MAP=True
WORKDIR /service
COPY requirements.txt /service/requirements.txt
RUN pip install --no-cache-dir --require-hashes -r /service/requirements.txt
COPY upstream.tar /service/upstream.tar
RUN mkdir /opt/bizagentbench && tar -xf /service/upstream.tar -C /opt/bizagentbench
COPY runtime.py private.json collect.py submit_response.py /service/
CMD ["python", "-I", "/service/runtime.py"]
