FROM python:3.10-slim-bookworm@sha256:5be5aaecb962a41567bc8041f1e9e3432cb085b037fe057f9a562630b2e4b370
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/opt/balrog SDL_VIDEODRIVER=dummy PYGAME_HIDE_SUPPORT_PROMPT=1 MPLBACKEND=Agg
COPY requirements-game.lock apt-game.lock runtime-lock.json runtime_guard.py /opt/
RUN python /opt/runtime_guard.py apt && python /opt/runtime_guard.py python \
    && rm -rf /var/lib/apt/lists/*
COPY vendor/ /tmp/vendor/
RUN python /opt/runtime_guard.py sources
RUN mkdir /opt/balrog /opt/baba && tar -xzf /tmp/vendor/balrog.tar.gz -C /opt/balrog \
    && tar -xzf /tmp/vendor/babaisai.tar.gz -C /opt/baba \
    && python -m pip install --no-cache-dir --no-deps --no-build-isolation /opt/baba \
    && python /opt/runtime_guard.py patch-baba \
    && rm -rf /tmp/vendor && python /opt/runtime_guard.py verify \
    && python -m pip freeze --all > /opt/runtime-requirements.txt \
    && useradd --create-home --uid 1000 game
WORKDIR /app
COPY game_server.py export_result.py episode.json /app/
RUN mkdir -p /var/lib/balrog && chown game:game /var/lib/balrog
USER game
CMD ["python", "game_server.py", "--episode", "/app/episode.json"]
