# The adapter prepends upstream's src/harbor_adapter/template/Dockerfile, which mirrors
# containers/inference.def, to this file when it generates a task.

# LongBench-v2 has exactly 503 rows and the benchmark asks for 503, so the cached file is
# the same for every seed (the seed selects requests at evaluation time). It is 465 MB, so
# the build downloads it instead of each task storing it. The 12 tasks' Dockerfiles are
# identical up to the last two instructions, so a local Docker build cache downloads it once;
# environments that build each task's image separately download it once per task. The
# checksums fail the build if the upstream dataset changes.
COPY inference_eval /opt/inference_eval
RUN cd /opt && HF_HOME=/opt/tmp/hf_samples HF_HUB_CACHE=/opt/tmp/hf_samples/hub \
    HUGGINGFACE_HUB_CACHE=/opt/tmp/hf_samples/hub XDG_CACHE_HOME=/opt/tmp/hf_samples/xdg \
    python3 -m inference_eval.cache_samples \
        --seed {quality_seed} --mmlupro-n {quality_n} --longbench-n {longbench_n} && \
    rm -rf /opt/tmp/hf_samples && \
    cd /opt/inference_eval/baselines/samples && \
    echo "{longbench_sha256}  longbench_v2/{quality_seed}_{longbench_n}/samples.jsonl" | sha256sum -c - && \
    echo "{mmlu_sha256}  mmlu_pro/{quality_seed}_{quality_n}/samples.jsonl" | sha256sum -c - && \
    chmod -R a+rX,go-w /opt/inference_eval && \
    chmod a+x /opt/inference_eval/bin/launch_supervised_server.sh

# Harbor runs the collect hook as root in the agent's sandbox and the verifier as root in a
# sandbox from this same image, after test.sh has put the agent's files back. Both resolve
# commands through the image's PATH, so the agent-writable bin directory must come last. The
# evaluation server still gets it first, because test.sh prepends it, and so does Claude Code,
# because Harbor's agent prepends it.
ENV PATH="/usr/local/nvidia/bin:/usr/local/cuda/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/root/.local/bin:/home/agent/.local/bin"

# On Daytona and Modal, Harbor's uploads give /tests and the hand-off in /var/lib/ib_handoff the
# uid of the user who runs Harbor, and upstream's image gives user agent uid 1000, which is that
# user's uid on many Linux hosts.
RUN usermod -u 64321 agent && groupmod -g 64321 agent

COPY collect.sh /usr/local/bin/
COPY agent_processes.sh download_model.py handoff.py /usr/local/lib/inferencebench/
COPY home /home/agent
RUN if [ "{agent_seed}" != "{quality_seed}" ]; then \
        mkdir -p /opt/inference_eval/baselines/samples/longbench_v2/{agent_seed}_{longbench_n} && \
        ln -s ../{quality_seed}_{longbench_n}/samples.jsonl \
            /opt/inference_eval/baselines/samples/longbench_v2/{agent_seed}_{longbench_n}/samples.jsonl; \
    fi && \
    chmod +x /home/agent/task/*.sh && chown -R agent:agent /home/agent
WORKDIR /home/agent/task
