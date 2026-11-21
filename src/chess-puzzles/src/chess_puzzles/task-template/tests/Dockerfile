FROM python:3.12-slim-bookworm
WORKDIR /app
# Separate verifiers do not receive tests/ at runtime; bundle them at build time.
COPY . /tests/
