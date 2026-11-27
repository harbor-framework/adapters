FROM harbor-control-arena-infra-training:85bddf54
RUN python -m venv /opt/infra-scorer \
    && /opt/infra-scorer/bin/pip install --no-cache-dir inspect-ai==0.3.292 \
    && chmod 700 /opt/infra-scorer
WORKDIR /workspace/training-infra
COPY . /tests/
RUN mkdir -p training/tests && cp /tests/train.py training/train.py \
    && touch training/__init__.py && chmod 700 /tests
