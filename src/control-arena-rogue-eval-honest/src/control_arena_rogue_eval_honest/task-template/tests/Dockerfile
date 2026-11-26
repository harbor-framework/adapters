FROM {replay_image} AS replay
FROM {judge_image}
ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1
{fixture_packages}
# The scorer imports GitPython indirectly and never invokes Git.
ENV GIT_PYTHON_REFRESH=quiet
COPY --from=replay / /opt/replay
WORKDIR /tests
COPY . /tests/
RUN install -d -m 0755 /opt/replay/workspace /opt/replay/var/log \
    && cp /tests/monitoring.py /opt/replay/workspace/monitoring.py \
    && touch /opt/replay/var/log/oversight_log.txt && chmod 666 /opt/replay/var/log/oversight_log.txt
