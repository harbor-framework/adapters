FROM python:3.13-slim

WORKDIR /workspace

RUN pip install --no-cache-dir "litellm>=1.82.0,<2" nltk==3.8.1 \
    && python -c "import nltk; nltk.download('punkt', quiet=True); nltk.download('wordnet', quiet=True)"
