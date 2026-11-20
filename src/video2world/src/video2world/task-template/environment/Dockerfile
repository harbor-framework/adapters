ARG RUNTIME_IMAGE
FROM ${RUNTIME_IMAGE}
USER root
ARG PUBLIC_PYTHON
COPY public/lib/ /opt/video2world/
COPY public/task/ /workspace/task/
COPY public/pkg/ /workspace/pkg/
COPY client.py /opt/v2w-client.py
RUN printf '#!/bin/sh\nexec "${V2W_PUBLIC_PYTHON:?}" /opt/v2w-client.py "$@"\n' > /usr/local/bin/v2w && chmod +x /usr/local/bin/v2w
ENV V2W_PUBLIC_PYTHON=${PUBLIC_PYTHON}
ENV PYTHONPATH=/opt/video2world
WORKDIR /workspace/pkg
ENTRYPOINT []
