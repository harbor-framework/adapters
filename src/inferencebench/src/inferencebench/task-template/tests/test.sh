#!/bin/bash
# Derived from aisa-group/InferenceBench src/harbor_adapter/template/tests/test.sh (Apache-2.0).
# Runs as root in the verifier's sandbox, which Harbor makes from the task's image after the
# agent's sandbox is gone. collect.sh packed the agent's work there, and receive_handoff puts it
# back here. The agent's code runs here too, but only as user agent: the evaluation server and
# whatever the judge's CLI starts. Nothing the agent owns may run as root: resolve commands
# through a clean PATH, and call tools by absolute path in `env -i`, which searches the PATH it
# was given.
# The evaluation server gets upstream's PATH order, with the agent's bin directory first.
AGENT_PATH="/root/.local/bin:/home/agent/.local/bin:${PATH}"
IMAGE_PYTHONPATH="${PYTHONPATH-}"
cd /
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
export PYTHONPATH="/opt/filelock_workarounds/soft_file_locks"
export PYTHONNOUSERSITE=1
unset PYTHONUSERBASE PIP_USER
source /usr/local/lib/inferencebench/agent_processes.sh

IB=/tests/ib
LIB=/usr/local/lib/inferencebench
STATE=/var/lib/ib_state
# What collect.sh packed in the agent's sandbox, at the path where Harbor uploads it here.
HANDOFF=/var/lib/ib_handoff
# A fresh download of the pinned model, and the /tmp snapshot while user agent unpacks it.
PINNED=/var/lib/ib_pinned
TMP_IN=/var/lib/ib_tmp_in
LOGS=/logs/verifier
AGENT_HOME=/home/agent
TASK="${AGENT_HOME}/task"
JUDGE_HOME=/var/lib/ib_judge
# receive_handoff fills this cache, and only root can write to it.
EVAL_HF=/opt/ib_eval_hf
EVAL_LOG="${LOGS}/eval.log"
SCENARIO="${INFERENCE_BENCH_SCENARIO}"
STUB_MARKER="ERROR: start_server.sh has no engine configured"
SERVER_PID=""
WATCHER_PID=""
FINAL_EVAL_RC=1
EVAL_ATTEMPT=0
# required (the default) or off. With off, the judge does not run and the trial is an unscored
# diagnostic run.
JUDGE_MODE="${INFERENCE_BENCH_JUDGE:-required}"
# valid, off, no_credential, or failed. Only a valid judge leads to a reward.
JUDGE_STATE=no_credential
JUDGE_NOTE=""
JUDGE_ATTEMPTS=3
JUDGE_TIMEOUT=15m
# Upstream has no limit on an evaluation attempt, and a slow but valid server needs hours:
# scenario B sends 64 sequential requests of about 7400 tokens, so vLLM's default 18 ms per
# token takes 2.4 h. Stop early enough to write a reward before Harbor's 12-hour verifier limit.
EVAL_DEADLINE=$(( $(date +%s) + 41400 ))
: "${PORT:=8000}" "${INFERENCE_BENCH_SERVER_URL:=http://127.0.0.1:8000}" "${INFERENCE_BENCH_SERVER_WAIT_S:=900}"

log() {
    echo "[${SCENARIO}] $(date --iso-8601=seconds) $*" | tee -a "${EVAL_LOG}"
}

# Harbor ignores this script's exit status and takes any reward file that it finds.
no_reward() {
    echo "[fatal] $*; no reward is written, so Harbor records an infrastructure error"
    rm -f "${LOGS}/reward.json" "${LOGS}/reward.txt"
    exit 1
}

finish() {
    [ -z "${WATCHER_PID}" ] || kill "${WATCHER_PID}" 2> /dev/null
    # Harbor reads this directory as the host user when it is a bind mount.
    chmod 755 "${LOGS}"
}
trap finish EXIT

write_error_metrics() {
    python3 -I - "${LOGS}/metrics.json" "${SCENARIO}" "${INFERENCE_BENCH_BASE_MODEL}" "$1" <<'PY'
import json
import sys
from pathlib import Path
path, scenario, model, error = sys.argv[1:]
Path(path).write_text(json.dumps({
    "scenario": scenario, "model_id": model, "profiles": {}, "vram_peak_mb": 0.0, "error": error,
}, indent=2), encoding="utf-8")
PY
}

link_eval_samples() {
    local baselines="${IB}/src/eval/inference/baselines"
    local samples=/opt/inference_eval/baselines/samples
    local eval_dir="${baselines}/samples/longbench_v2/${INFERENCE_BENCH_DATASET_SEED}_${INFERENCE_BENCH_LONGBENCH_N}"
    mkdir -p "${eval_dir}" "${baselines}/samples/mmlu_pro"
    ln -sfn "${samples}/longbench_v2/${INFERENCE_BENCH_QUALITY_SEED}_${INFERENCE_BENCH_LONGBENCH_N}/samples.jsonl" "${eval_dir}/samples.jsonl"
    ln -sfn "${samples}/mmlu_pro/${INFERENCE_BENCH_QUALITY_SEED}_${INFERENCE_BENCH_QUALITY_MMLUPRO_N}" \
        "${baselines}/samples/mmlu_pro/${INFERENCE_BENCH_QUALITY_SEED}_${INFERENCE_BENCH_QUALITY_MMLUPRO_N}"
    ln -sfn /opt/inference_eval/baselines/quality "${baselines}/quality"
}

# The agent's sandbox is gone. collect.sh packed /home/agent and the /tmp targets of the task
# directory's links into one stream, without the model files that the healthcheck downloaded and
# that the agent left unchanged, and Harbor brought its parts here. Download the same revision of
# the model, then have user agent unpack the stream into an empty home and put those model files
# back. Root reads the parts and hands the stream over a pipe, so the hand-off stays closed to
# user agent, and nothing in it acts with root's rights.
receive_handoff() {
    [ -d "${HANDOFF}" ] && [ ! -L "${HANDOFF}" ] && [ -f "${HANDOFF}/complete" ] ||
        no_reward "the hand-off from the agent's sandbox is missing: collect.sh did not finish there, or Harbor did not bring its files (see artifacts/var/lib/ib_handoff/collect.log and artifacts/manifest.json in the trial directory)"
    chown -R -h root:root "${HANDOFF}" && chmod -R go-rwx,a-s "${HANDOFF}" ||
        no_reward "could not take over ${HANDOFF}"
    python3 -I "${LIB}/handoff.py" verify "${HANDOFF}" --model "${INFERENCE_BENCH_BASE_MODEL}" \
        --revision "${INFERENCE_BENCH_MODEL_REVISION}" >> "${LOGS}/handoff.log" 2>&1 ||
        no_reward "the hand-off from the agent's sandbox is incomplete or damaged; see handoff.log"
    cp "${HANDOFF}/manifest.json" "${LOGS}/handoff.json" || no_reward "could not copy the hand-off's manifest"
    rm -rf "${PINNED}" "${TMP_IN}" && mkdir -m 700 "${PINNED}" "${TMP_IN}" ||
        no_reward "could not create the staging directories"
    local attempt
    for attempt in 1 2 3 4 5; do
        log "downloading ${INFERENCE_BENCH_BASE_MODEL} at ${INFERENCE_BENCH_MODEL_REVISION} (attempt ${attempt})"
        HF_HOME="${PINNED}" HF_HUB_CACHE="${PINNED}/hub" HUGGINGFACE_HUB_CACHE="${PINNED}/hub" \
            TRANSFORMERS_CACHE="${PINNED}/hub" HF_XET_CACHE="${PINNED}/xet" \
            /usr/bin/timeout --kill-after=60s 3600s \
            python3 "${LIB}/download_model.py" --evaluator >> "${LOGS}/model_download.log" 2>&1 && break
        [ "${attempt}" -lt 5 ] || no_reward "could not download the model in 5 attempts; see model_download.log"
        sleep 30
    done
    chmod -R a+rX,go-w "${EVAL_HF}" || no_reward "could not close ${EVAL_HF} to user agent"
    find "${AGENT_HOME}" -mindepth 1 -delete && chown agent:agent "${AGENT_HOME}" "${TMP_IN}" &&
        chown -R agent:agent "${PINNED}" || no_reward "could not prepare ${AGENT_HOME}"
    python3 -I "${LIB}/handoff.py" stream "${HANDOFF}" 2>> "${LOGS}/handoff.log" |
        /usr/bin/env -i /usr/bin/setpriv --no-new-privs --reuid=agent --regid=agent --clear-groups \
        /usr/bin/python3 -I "${LIB}/handoff.py" unpack --manifest-fd 3 --home "${AGENT_HOME}" \
        --tmp "${TMP_IN}" --staging "${PINNED}/hub" 3< "${HANDOFF}/manifest.json" >> "${LOGS}/handoff.log" 2>&1
    local status=("${PIPESTATUS[@]}")
    [ "${status[0]}" -eq 0 ] && [ "${status[1]}" -eq 0 ] || no_reward "could not unpack the hand-off; see handoff.log"
    rm -rf "${PINNED}"
    # restore_tmp copies the /tmp targets from a directory that only root can reach.
    mv "${TMP_IN}" "${STATE}/tmp" || no_reward "could not keep the /tmp snapshot"
    [ -d "${TASK}" ] && [ ! -L "${TASK}" ] || no_reward "the hand-off has no task directory"
    log "received the agent's home directory: $(du -sh "${AGENT_HOME}" | cut -f1)"
}

# Put back the /tmp targets that collect.sh saved, including names that start with a dot.
restore_tmp() {
    local entry name
    while IFS= read -r -d '' entry; do
        name="$(basename "${entry}")"
        rm -rf "/tmp/${name}"
        cp -a "${entry}" /tmp/ && chown -R agent:agent "/tmp/${name}" || return 1
    done < <(find "${STATE}/tmp" -mindepth 1 -maxdepth 1 -print0)
}

purge_tmp() {
    find /tmp /var/tmp /dev/shm -mindepth 1 -user agent -delete 2> /dev/null
}

agent_env() {
    local names=(HF_HOME HF_HUB_CACHE HUGGINGFACE_HUB_CACHE TRANSFORMERS_CACHE TMPDIR TMP TEMP XDG_CACHE_HOME
        VLLM_TORCH_COMPILE_CACHE_DIR TORCHINDUCTOR_CACHE_DIR TORCH_EXTENSIONS_DIR TRITON_CACHE_DIR
        PIP_CACHE_DIR SOFT_FILELOCK NO_PROXY no_proxy LD_LIBRARY_PATH HOST PORT INFERENCE_BENCH_SERVER_URL
        INFERENCE_BENCH_SERVER_WAIT_S INFERENCE_BENCH_BASE_MODEL INFERENCE_BENCH_MAX_MODEL_LEN)
    local name
    AGENT_ENV=("HOME=${AGENT_HOME}" "PATH=${AGENT_PATH}" "PYTHONPATH=${IMAGE_PYTHONPATH}" PIP_USER=1
        "PYTHONUSERBASE=${AGENT_HOME}/.local")
    for name in "${names[@]}" $(compgen -e | grep -E '^(NVIDIA_|CUDA_|RAY_)'); do
        [ -z "${!name+x}" ] || AGENT_ENV+=("${name}=${!name}")
    done
}

verdict_files_valid() {
    local f
    for f in contamination_judgement.txt disallowed_model_judgement.txt; do
        [ -f "$1/${f}" ] && [ ! -L "$1/${f}" ] && [ "$(stat -c %s "$1/${f}")" -le 1024 ] || return 1
    done
    valid_judgements "$1"
}

# The judge reviews a read-only copy of the task directory, as the original's judge reviews a
# read-only mount, with the agent's /tmp targets in place. The agent's home directory is closed
# to it until it has finished. A trial is graded only if the judge exits with status 0 and
# writes two valid verdicts. If the judge fails to start or fails three times, the evaluation
# still runs, as it does in run_task.sh, but the trial stays ungraded: it gets no reward.
# Without a credential the judge does not start, and the main sequence skips the evaluation.
run_judge() {
    if [ "${JUDGE_MODE}" = off ]; then
        JUDGE_STATE=off
        JUDGE_NOTE="diagnostic run: INFERENCE_BENCH_JUDGE=off"
        return 0
    fi
    local credential
    if [ -n "${CLAUDE_CODE_OAUTH_TOKEN:-}" ]; then
        credential=("CLAUDE_CODE_OAUTH_TOKEN=${CLAUDE_CODE_OAUTH_TOKEN}")
    elif [ -n "${ANTHROPIC_API_KEY:-}" ]; then
        credential=("ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}")
        [ -z "${ANTHROPIC_BASE_URL:-}" ] || credential+=("ANTHROPIC_BASE_URL=${ANTHROPIC_BASE_URL}")
    else
        JUDGE_NOTE="no judge credential (ANTHROPIC_API_KEY or CLAUDE_CODE_OAUTH_TOKEN)"
        return 0
    fi
    JUDGE_STATE=failed
    local judge_bin home_mode prompt="${STATE}/judge_prompt.txt" f attempt status
    if ! judge_bin="$(command -v claude)"; then
        JUDGE_NOTE="the judge's CLI is not installed in the image"
        return 0
    fi
    if ! restore_tmp; then
        JUDGE_NOTE="could not restore the /tmp snapshot for the judge"
        return 0
    fi
    home_mode="$(stat -c %a "${AGENT_HOME}")" || no_reward "could not read the mode of ${AGENT_HOME}"
    chown root:root "${AGENT_HOME}" && chmod 700 "${AGENT_HOME}" ||
        no_reward "could not close the agent's home directory"

    local problem="could not prepare the judge's copy of the task directory"
    local fatal=""
    rm -rf "${JUDGE_HOME}"
    if mkdir -p "${JUDGE_HOME}" && chown agent:agent "${JUDGE_HOME}" &&
        cp -a "${TASK}" "${JUDGE_HOME}/task" && chown -R -h root:root "${JUDGE_HOME}/task" &&
        chmod -R a+rX,a-s,go-w "${JUDGE_HOME}/task" &&
        python3 "${IB}/src/disallowed_usage_judge/get_judge_prompt.py" \
            --benchmark "$(cat "${IB}/src/eval/tasks/${SCENARIO}/benchmark.txt")" \
            --model "${INFERENCE_BENCH_BASE_MODEL}" --task-dir "${JUDGE_HOME}/task" > "${prompt}"; then
        problem="the judge produced no valid verdict in ${JUDGE_ATTEMPTS} attempts"
        for ((attempt = 1; attempt <= JUDGE_ATTEMPTS; attempt++)); do
            rm -f "${JUDGE_HOME}/contamination_judgement.txt" "${JUDGE_HOME}/disallowed_model_judgement.txt"
            (
                cd "${JUDGE_HOME}" || exit 1
                # The prompt arrives on stdin, as in run_rejudge.sh, because one argument
                # cannot hold more than 128 KiB.
                /usr/bin/env -i "${AGENT_ENV[@]}" "HOME=${JUDGE_HOME}" "${credential[@]}" \
                    /usr/bin/timeout --signal=TERM --kill-after=30s "${JUDGE_TIMEOUT}" \
                    /usr/bin/setpriv --no-new-privs --reuid=agent --regid=agent --clear-groups \
                    "${judge_bin}" --print --dangerously-skip-permissions --model "${DEFAULT_JUDGE_MODEL}" < "${prompt}"
            ) >> "${LOGS}/judge.log" 2>&1
            status=$?
            log "judge attempt ${attempt} exit code: ${status}"
            if ! kill_agent_processes; then
                fatal="could not stop the judge's processes"
                break
            fi
            # Keep what every attempt wrote. Only a valid pair gets the names that count.
            for f in contamination_judgement disallowed_model_judgement; do
                if [ -f "${JUDGE_HOME}/${f}.txt" ] && [ ! -L "${JUDGE_HOME}/${f}.txt" ]; then
                    head -c 1024 "${JUDGE_HOME}/${f}.txt" > "${LOGS}/${f}.attempt-${attempt}.txt"
                fi
            done
            if [ "${status}" -eq 0 ] && verdict_files_valid "${JUDGE_HOME}"; then
                for f in contamination_judgement disallowed_model_judgement; do
                    cp "${LOGS}/${f}.attempt-${attempt}.txt" "${LOGS}/${f}.txt"
                done
                problem=""
                break
            fi
        done
    fi
    rm -rf "${JUDGE_HOME}"
    chown agent:agent "${AGENT_HOME}" && chmod "${home_mode}" "${AGENT_HOME}" ||
        no_reward "could not reopen the agent's home directory"
    [ -z "${fatal}" ] || no_reward "${fatal}"
    if [ -n "${problem}" ]; then
        JUDGE_NOTE="${problem}"
        return 0
    fi
    JUDGE_STATE=valid
}

server_ready() {
    python3 /opt/inference_eval/bin/server_ready.py "${INFERENCE_BENCH_SERVER_URL}"
}

supervisor_alive() {
    [ -n "${SERVER_PID}" ] && kill -0 "${SERVER_PID}" 2> /dev/null
}

# The original runs the server in a container that dies with its supervisor, so a server that
# outlives its launcher is not evaluated. Here, a watcher stops every process of user agent as
# soon as the supervisor is gone.
watch_supervisor() {
    while kill -0 "$1" 2> /dev/null; do
        sleep 1
    done
    kill_agent_processes > /dev/null
}

stop_server() {
    if [ -n "${WATCHER_PID}" ]; then
        kill "${WATCHER_PID}" 2> /dev/null
        wait "${WATCHER_PID}" 2> /dev/null
        WATCHER_PID=""
    fi
    if [ -n "${SERVER_PID}" ]; then
        kill -- "-${SERVER_PID}" 2> /dev/null
        sleep 2
        SERVER_PID=""
    fi
    kill_agent_processes
}

start_server() {
    stop_server || return 1
    restore_tmp || return 1
    local launch=""
    local f
    for f in start_server.sh start_server_original.sh; do
        if [ -f "${TASK}/${f}" ] && ! grep -q "${STUB_MARKER}" "${TASK}/${f}"; then
            launch="${TASK}/${f}"
            break
        fi
    done
    if [ -z "${launch}" ]; then
        log "no configured start_server.sh found for the eval server."
        return 1
    fi
    log "starting the eval server via ${launch}"
    cd "${TASK}" || return 1
    /usr/bin/env -i "${AGENT_ENV[@]}" /usr/bin/setsid \
        /usr/bin/setpriv --no-new-privs --reuid=agent --regid=agent --clear-groups \
        /bin/bash -c 'set -euo pipefail; if [ -f /home/agent/task/final_runtime_env.sh ]; then . /home/agent/task/final_runtime_env.sh; fi; exec /opt/inference_eval/bin/launch_supervised_server.sh "$1"' \
        _ "${launch}" >> "${LOGS}/server.log" 2>&1 &
    SERVER_PID=$!
    cd "${IB}" || return 1
    watch_supervisor "${SERVER_PID}" &
    WATCHER_PID=$!
    local deadline=$(( $(date +%s) + INFERENCE_BENCH_SERVER_WAIT_S ))
    while [ "$(date +%s)" -lt "${deadline}" ]; do
        # An endpoint that answers after its supervisor is gone belongs to a detached server.
        if server_ready && supervisor_alive; then
            log "eval server is ready at ${INFERENCE_BENCH_SERVER_URL}"
            return 0
        fi
        if ! supervisor_alive; then
            log "eval server exited before becoming ready"
            return 1
        fi
        sleep 1
    done
    log "eval server did not become ready within ${INFERENCE_BENCH_SERVER_WAIT_S}s"
    return 1
}

run_eval_attempt() {
    local left=$(( EVAL_DEADLINE - $(date +%s) ))
    # GNU timeout takes 0 to mean no limit.
    [ "${left}" -gt 0 ] || return 124
    HOME=/root/eval_home TMPDIR=/root/eval_tmp XDG_CACHE_HOME=/root/eval_home/.cache \
        HF_HOME="${EVAL_HF}" HF_HUB_CACHE="${EVAL_HF}/hub" HUGGINGFACE_HUB_CACHE="${EVAL_HF}/hub" \
        TRANSFORMERS_CACHE="${EVAL_HF}/hub" \
        INFERENCE_BENCH_ALLOW_HF_DOWNLOAD=0 timeout --signal=TERM --kill-after=60s "${left}" \
        python3 "src/eval/tasks/${SCENARIO}/evaluate.py" \
        --server-url "${INFERENCE_BENCH_SERVER_URL}" \
        --json-output-file "${LOGS}/metrics.json" \
        --quality-tau "${INFERENCE_BENCH_QUALITY_TAU}" \
        "$@" >> "${EVAL_LOG}" 2>&1
}

run_eval_with_retry() {
    local max_retries="$1"
    shift
    local attempt
    for ((attempt = 1; attempt <= max_retries; attempt++)); do
        [ "$(date +%s)" -lt "${EVAL_DEADLINE}" ] || return 1
        if { ! supervisor_alive || ! server_ready; } && ! start_server; then
            FINAL_EVAL_RC=1
            continue
        fi
        log "eval attempt ${attempt}/${max_retries} $*"
        FINAL_EVAL_RC=0
        rm -f "${LOGS}/metrics.json"
        run_eval_attempt "$@" || FINAL_EVAL_RC=$?
        # metrics.json is the last attempt's; keep every attempt's.
        EVAL_ATTEMPT=$((EVAL_ATTEMPT + 1))
        [ ! -f "${LOGS}/metrics.json" ] || cp "${LOGS}/metrics.json" "${LOGS}/metrics.attempt-${EVAL_ATTEMPT}.json"
        # A measurement only counts if the supervisor outlived it: the original's server
        # cannot answer after its supervisor is gone.
        if [ "${FINAL_EVAL_RC}" -eq 0 ] && supervisor_alive &&
            python3 /tests/valid_eval_metrics.py "${LOGS}/metrics.json" "${IB}"; then
            return 0
        fi
        [ "${FINAL_EVAL_RC}" -ne 0 ] || FINAL_EVAL_RC=1
        log "attempt ${attempt} failed (rc=${FINAL_EVAL_RC})"
    done
    return 1
}

echo "=== InferenceBench verifier: ${SCENARIO} ${INFERENCE_BENCH_BASE_MODEL} ==="
# Root may not read or run anything that user agent can write, and only root writes the reward.
kill_agent_processes || no_reward "could not stop the agent's processes"
chown root:root "${LOGS}" && chmod 700 "${LOGS}" || no_reward "could not take over ${LOGS}"
find "${LOGS}" -mindepth 1 ! -name test-stdout.txt -delete
# Harbor's upload keeps the host user's uid on Daytona and Modal, which can be user agent's.
chown -R -h root:root /tests && chmod -R go-rwx /tests || no_reward "could not take over /tests"
mkdir -p /root/eval_home /root/eval_tmp
rm -rf "${STATE}" && mkdir -m 700 "${STATE}" || no_reward "could not create ${STATE}"
case "${JUDGE_MODE}" in
    required | off) ;;
    *) no_reward "INFERENCE_BENCH_JUDGE must be required or off, not '${JUDGE_MODE}'" ;;
esac
source "${IB}/src/disallowed_usage_judge/judge.sh"
receive_handoff
[ -d "${EVAL_HF}/hub" ] || no_reward "the evaluator's tokenizer cache is missing from ${EVAL_HF}"

# What this trial ran on, for the record. It cannot change the outcome, and a GPU that does
# not answer cannot hold up the verifier.
JUDGE_MODEL="${DEFAULT_JUDGE_MODEL}" JUDGE_ATTEMPTS="${JUDGE_ATTEMPTS}" JUDGE_TIMEOUT="${JUDGE_TIMEOUT}" \
    EVAL_DEADLINE="${EVAL_DEADLINE}" /usr/bin/timeout --kill-after=10s 300s \
    python3 -I /tests/record_environment.py "${LOGS}/environment.json" ||
    log "could not record the environment"

agent_env
link_eval_samples
log "judge start"
run_judge
log "judge done (${JUDGE_STATE}${JUDGE_NOTE:+: ${JUDGE_NOTE}})"

unset ANTHROPIC_API_KEY CLAUDE_CODE_OAUTH_TOKEN ANTHROPIC_BASE_URL HF_TOKEN
purge_tmp
for f in metrics_preview.json server.log final_runtime_env.sh final_runtime_manifest.txt; do
    [ ! -f "${TASK}/${f}" ] || [ -L "${TASK}/${f}" ] || head -c 67108864 "${TASK}/${f}" > "${LOGS}/${f}"
done
python3 /tests/snapshot.py "${TASK}" "${LOGS}/task"
# snapshot.py keeps mode bits, and these copies belong to root.
chmod -R a-s,go-w "${LOGS}/task"

cd "${IB}" || no_reward "the verifier's files are missing"
rm -f "${LOGS}/metrics.json"
if [ "${JUDGE_STATE}" = no_credential ]; then
    # Such a trial can never be graded, so it does not spend hours of GPU time on a measurement.
    # A run without the judge on purpose sets INFERENCE_BENCH_JUDGE=off.
    JUDGE_NOTE="${JUDGE_NOTE}; the evaluation did not run (set INFERENCE_BENCH_JUDGE=off for an unscored diagnostic run)"
    FINAL_EVAL_RC=not_run
    log "${JUDGE_NOTE}"
elif start_server; then
    log "starting final evaluation (speed + quality)"
    if ! run_eval_with_retry 3; then
        log "phase 1 failed; retrying with reduced request-timeout"
        run_eval_with_retry 2 --request-timeout-s 150
    fi
else
    log "final evaluation aborted: inference server unavailable"
    write_error_metrics "inference server unavailable before final eval at ${INFERENCE_BENCH_SERVER_URL}"
fi
log "final eval exit code: ${FINAL_EVAL_RC}"
stop_server || no_reward "could not stop the evaluation server's processes"
# Writes /logs/verifier/reward.json for a judged trial, and ungraded.json with the measurement,
# if there is one, otherwise.
PYTHONPATH="${IB}:${PYTHONPATH}" python3 /tests/write_reward.py \
    "${LOGS}" "${SCENARIO}" "${FINAL_EVAL_RC}" "${JUDGE_STATE}" "${JUDGE_NOTE}" ||
    no_reward "write_reward.py failed"
if [ "${JUDGE_STATE}" != valid ]; then
    rm -f "${LOGS}/reward.json" "${LOGS}/reward.txt"
    echo "[ungraded] ${JUDGE_NOTE}; ungraded.json has the details, and no reward is written"
fi
exit 0
