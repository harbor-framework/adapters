FROM harbor-control-arena-infra-training:85bddf54
WORKDIR /workspace/training-infra
COPY training/ training/
ENV ENVIRONMENT=test PYTHONPATH=/workspace/training-infra AWS_EC2_METADATA_DISABLED=true HF_HUB_OFFLINE=1
