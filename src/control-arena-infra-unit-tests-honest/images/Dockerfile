FROM python:3.12-slim-bookworm

# CPU wheel and library versions from ca-k8s-infra at 85bddf54.
RUN pip install --no-cache-dir torch==2.6.0+cpu --index-url https://download.pytorch.org/whl/cpu
RUN apt-get update \
    && apt-get install -y --no-install-recommends bash util-linux \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir \
    "ray[train]==2.42.1" transformers==4.49.0 datasets==3.3.1 \
    pyarrow==17.0.0 pandas==2.2.3 numpy==2.2.3 protobuf==5.29.3 fsspec==2023.5.0 \
    pytest==8.3.5
ENV HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1
RUN command -v setpriv && python -c "import datasets, pyarrow.fs, pytest, ray.train.torch, torch, transformers; assert torch.version.cuda is None"
WORKDIR /workspace/training-infra
