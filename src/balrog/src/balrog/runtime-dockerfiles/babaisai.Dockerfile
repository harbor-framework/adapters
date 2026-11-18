FROM python:3.10-slim-bookworm@sha256:5be5aaecb962a41567bc8041f1e9e3432cb085b037fe057f9a562630b2e4b370
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/opt/balrog SDL_VIDEODRIVER=dummy PYGAME_HIDE_SUPPORT_PROMPT=1 MPLBACKEND=Agg
COPY requirements-agent.lock /opt/requirements-agent.lock
RUN python -m pip install --no-cache-dir -r /opt/requirements-agent.lock \
    && python -m pip install --no-cache-dir 'numpy==1.26.4' 'gym==0.23.0' 'gymnasium==0.29.1' 'pygame==2.6.1' 'pillow==12.3.0' 'omegaconf==2.4.0' \
       'matplotlib==3.9.4' 'opencv-python-headless==4.10.0.84' 'balrog-nle==0.9.0' 'pybind11==3.1.0'
COPY vendor/balrog.tar.gz vendor/babaisai.tar.gz /tmp/vendor/
RUN mkdir /opt/balrog /opt/baba && tar -xzf /tmp/vendor/balrog.tar.gz -C /opt/balrog \
    && tar -xzf /tmp/vendor/babaisai.tar.gz -C /opt/baba \
    && python -m pip install --no-cache-dir --no-deps /opt/baba \
    && rm -rf /tmp/vendor && python -m pip freeze > /opt/runtime-requirements.txt \
    && useradd --create-home --uid 1000 game
WORKDIR /app
COPY game_server.py episode.json /app/
USER game
CMD ["python", "game_server.py", "--episode", "/app/episode.json"]
