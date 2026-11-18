FROM python:3.10-slim-bookworm@sha256:5be5aaecb962a41567bc8041f1e9e3432cb085b037fe057f9a562630b2e4b370
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/opt/balrog:/opt/textworld PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1
RUN apt-get update && apt-get install -y --no-install-recommends build-essential libffi-dev \
    && rm -rf /var/lib/apt/lists/*
COPY requirements-agent.lock requirements-game.lock /opt/
RUN python -m pip install --no-cache-dir -r /opt/requirements-agent.lock -r /opt/requirements-game.lock
COPY vendor/ /tmp/vendor/
RUN mkdir -p /opt/balrog /opt/textworld \
    && tar -xzf /tmp/vendor/balrog.tar.gz -C /opt/balrog \
    && tar -xzf /tmp/vendor/textworld.tar.gz -C /opt/textworld \
    && tar -xzf /tmp/vendor/assets.tar.gz -C /opt/balrog \
    && make -B -C /opt/textworld/textworld/thirdparty/glulx/cheapglk \
    && make -B -C /opt/textworld/textworld/thirdparty/glulx/Git-Glulx \
    && cd /opt/textworld && python -c "import glk_build, os; os.chdir('/tmp'); glk_build.ffibuilder.compile(tmpdir='/tmp/textworld-glk', verbose=True)" \
    && cp /tmp/textworld-glk/glk*.so /opt/textworld/ \
    && python -m pip freeze > /opt/runtime-requirements.txt \
    && rm -rf /tmp/vendor && useradd --create-home --uid 1000 game
# Run precompiled upstream games; do not regenerate a different dataset.
WORKDIR /app
COPY game_server.py episode.json /app/
USER game
CMD ["python", "game_server.py", "--episode", "/app/episode.json"]
