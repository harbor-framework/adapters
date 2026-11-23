# The game sidecar: the only container that holds the engine and the world.
# Python is pinned so the oracle replays to the recorded score bit for bit.
FROM python:3.11.7-slim-bookworm

WORKDIR /app
RUN pip install --no-cache-dir pyyaml==6.0.2

COPY fmbench/ /app/
COPY game_server.py /app/game_server.py

ENV PYTHONPATH=/app PYTHONHASHSEED=0
CMD ["python3", "/app/game_server.py"]
