FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1

# Pinned agentdojo==0.1.35 and fastmcp==4.0.11 with their resolved dependencies.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py task_config.json ./

EXPOSE 8000

CMD ["python3", "server.py"]
