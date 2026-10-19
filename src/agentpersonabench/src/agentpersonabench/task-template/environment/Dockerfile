FROM python:3.12-bookworm

RUN pip install --no-cache-dir pyyaml==6.0.2

WORKDIR /app
COPY questionnaire.yaml /app/input/questionnaire.yaml
RUN mkdir -p /app/output
