FROM python:3.11-slim

# openai SDK is used by the verifier's LLM judge (same client as upstream evaluate.py)
RUN pip install --no-cache-dir openai==1.109.1

WORKDIR /app
COPY images/{{image_filename}} /app/images/{{image_filename}}
