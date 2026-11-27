FROM python:3.4 AS native
FROM python:3.13-slim-bookworm
COPY --from=native / /opt/apps-runtime/
COPY . /tests/
WORKDIR /tests
