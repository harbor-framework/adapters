# Runtime packages mirror de_bench/modal_app.py:runtime_image at the pinned SHA.
# Agent installations/launch flags are selected separately with the parity plan.
FROM python:3.12-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl ca-certificates ripgrep procps psmisc unzip sqlite3 file iproute2 jq \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir apache-airflow==3.0.3 \
    apache-airflow-providers-standard apache-airflow-providers-amazon \
    apache-airflow-providers-cncf-kubernetes apache-airflow-providers-common-sql \
    apache-airflow-providers-google apache-airflow-providers-http \
    apache-airflow-providers-postgres apache-airflow-providers-snowflake \
    --constraint https://raw.githubusercontent.com/apache/airflow/constraints-3.0.3/constraints-3.12.txt
# Upstream installs this group without Airflow constraints. Use uv for faster
# resolution: pip backtracked for >8 minutes locally. Same declared packages;
# installer/resolved-version equivalence must be established before agent parity.
RUN pip install --no-cache-dir uv==0.13.9
ARG UV_DEFAULT_INDEX=https://pypi.org/simple/
# requirements.in documents the input declarations; requirements.lock records
# the complete, pip-check-clean resolution validated in this adapter.
COPY runtime-requirements.txt /tmp/runtime-requirements.txt
RUN uv pip install --system --no-cache -r /tmp/runtime-requirements.txt
ENV DBT_SEND_ANONYMOUS_USAGE_STATS=False DO_NOT_TRACK=1 SCARF_NO_ANALYTICS=1 \
    AIRFLOW__COSMOS__ENABLE_TELEMETRY=False AIRFLOW__COSMOS__ENABLE_CACHE=0 \
    AIRFLOW__COSMOS__ENABLE_DAG_VERSIONING=False AIRFLOW__CORE__LOAD_EXAMPLES=False
# Include the existing Snowpark and Prometheus consumers in resolution; otherwise
# auxiliary upgrades may leave their protobuf/OTel requirements inconsistent.
# Permit compatible upgrades, while keeping dbt-core on the 1.x series.
# OpenTelemetry intentionally versions some required companion libraries as beta.
RUN python -m pip check
RUN airflow db migrate >/dev/null 2>&1
RUN uv python install 3.11.18
RUN pip freeze > /opt/runtime-packages.txt
# Isolate verifier dependencies from installs in the default agent Python env.
RUN python -m venv /opt/verifier-venv && \
    /opt/verifier-venv/bin/pip install --no-cache-dir PyYAML==6.0.4 packaging==26.3
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/work:/work/dags:/work/plugins \
    AIRFLOW__CORE__DAGS_FOLDER=/work/dags AIRFLOW__CORE__PLUGINS_FOLDER=/work/plugins
WORKDIR /work
COPY workspace/ /work/
COPY bootstrap.py add-excludes.json /tmp/
RUN python /tmp/bootstrap.py && rm /tmp/bootstrap.py
