# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm
RUN pip install --no-cache-dir torch==2.9.1+cpu --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir control-arena==20.1.1 inspect-ai==0.3.292 transformers==5.0.0 accelerate==1.12.0
ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1
# Supply a local Transformers chat checkpoint. Only safe model files enter the verifier.
COPY --from=judge_snapshot /*.json /*.safetensors /opt/private-judge/
RUN chmod 700 /opt/private-judge && test -f /opt/private-judge/config.json \
    && test -f /opt/private-judge/tokenizer.json \
    && sha256sum /opt/private-judge/* > /opt/private-judge.manifest
