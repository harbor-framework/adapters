FROM python:3.11.10-slim-bookworm

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

# The Python stack the task card promises.
RUN pip install --no-cache-dir \
    numpy==2.2.6 \
    scipy==1.15.3 \
    pymupdf==1.26.4 \
    matplotlib==3.10.6 \
    pillow==11.3.0 \
    opencv-python-headless==4.12.0.88 \
    scikit-image==0.25.2

WORKDIR /app

# The paper is not redistributed with the task. It is fetched at build time
# from the public arXiv mirror at a pinned version and checked by hash.
RUN curl -fsSL --retry 5 --retry-delay 5 -o /app/paper.pdf "{pdf_url}" \
    && echo "{pdf_sha256}  /app/paper.pdf" | sha256sum -c -
