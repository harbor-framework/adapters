# Verifier image. The grader runs here, in a separate container from the agent
# (environment_mode = "separate" in task.toml), so the agent cannot change the
# grader or its dependencies. Harbor copies the declared artifacts
# (/workspace/response.txt and /logs/agent/trajectory.json) in before grading.
# The punkt data is baked in because the verifier inherits no-network.
FROM python:3.12-slim
RUN pip install --no-cache-dir langdetect==1.0.9 nltk==3.9.4 'six>=1.16.0' \
    && python -m nltk.downloader -d /usr/local/share/nltk_data punkt punkt_tab
COPY . /tests/
RUN chmod +x /tests/test.sh && rm -f /tests/Dockerfile
