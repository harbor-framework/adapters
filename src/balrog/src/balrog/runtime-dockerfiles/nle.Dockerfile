FROM python:3.10-slim-bookworm@sha256:5be5aaecb962a41567bc8041f1e9e3432cb085b037fe057f9a562630b2e4b370
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/opt/balrog PYTHONHASHSEED=0 SDL_VIDEODRIVER=dummy PYGAME_HIDE_SUPPORT_PROMPT=1
COPY requirements-agent.lock /opt/requirements-agent.lock
RUN python -m pip install --no-cache-dir -r /opt/requirements-agent.lock \
    && python -m pip install --no-cache-dir 'numpy==1.26.4' 'gym==0.23.0' 'gymnasium==0.29.1' 'pygame==2.6.1' 'pillow==12.3.0' 'omegaconf==2.4.0' 'pybind11==2.13.6' \
       'https://files.pythonhosted.org/packages/90/e3/3ea90f299b64b4896d3767ecac848304e9a96478f8164ad2cbb7da5a3323/balrog_nle-0.9.0-cp310-cp310-manylinux_2_17_x86_64.manylinux2014_x86_64.whl#sha256=b5a6ba1e6a7c406e7918e56f525937919bad6c8ec68df9ca2acbb6714e55dcd2'
COPY vendor/balrog.tar.gz /tmp/balrog.tar.gz
RUN mkdir /opt/balrog && tar -xzf /tmp/balrog.tar.gz -C /opt/balrog \
    && rm /tmp/balrog.tar.gz && python -m pip freeze > /opt/runtime-requirements.txt \
    && useradd --create-home --uid 1000 game
WORKDIR /app
COPY game_server.py episode.json /app/
USER game
CMD ["python", "game_server.py", "--episode", "/app/episode.json"]
