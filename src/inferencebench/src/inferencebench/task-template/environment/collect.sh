#!/bin/bash
# Derived from aisa-group/InferenceBench src/harbor_adapter/template/environment/collect.sh
# (Apache-2.0). Harbor runs this as root in the agent's sandbox after the agent phase. The
# verifier runs in a new sandbox from the same image, so this script hands the agent's work
# over, as upstream's does through a Modal volume: it packs /home/agent and the /tmp targets of
# the task directory's links into /var/lib/ib_handoff, which only root can write. task.toml
# declares its files as artifacts, so Harbor copies them to the trial directory and from there
# into the verifier's sandbox. Nothing the agent owns may run as root here: use a clean PATH and
# PYTHONPATH and leave the agent's working directory.
set -uo pipefail
cd /
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
export PYTHONPATH="/opt/filelock_workarounds/soft_file_locks"
export PYTHONNOUSERSITE=1
unset PYTHONUSERBASE PIP_USER
source /usr/local/lib/inferencebench/agent_processes.sh

LIB=/usr/local/lib/inferencebench
TASK=/home/agent/task
HANDOFF=/var/lib/ib_handoff
# The healthcheck's list of the model files that it downloaded; only root can read it.
RECORD=/var/lib/inferencebench/pinned_model.json
WORK=/var/lib/ib_collect
rm -rf "${WORK}"
mkdir -m 700 "${WORK}"
# Keep the log where only root can write it. Harbor gets a copy however this script ends.
exec 3>&1 >> "${WORK}/collect.log" 2>&1
publish_log() {
    cat "${WORK}/collect.log" >&3
    if [ -d "${HANDOFF}" ] && [ ! -L "${HANDOFF}" ]; then
        cp --remove-destination "${WORK}/collect.log" "${HANDOFF}/collect.log"
    fi
}
trap publish_log EXIT

phase() {
    echo "[collect] $(date --iso-8601=seconds) $*"
}

# As in run_task.sh, where the agent's container is gone before anything else happens: stop
# the agent's processes first. The final evaluation restarts start_server.sh from scratch, so
# the environment of a server that the agent left running is not carried over.
if ! kill_agent_processes; then
    phase "ERROR: could not stop the agent's processes"
    exit 1
fi
phase "stopped the agent's processes"

rm -rf "${HANDOFF}"
mkdir -m 755 "${HANDOFF}"

# Harbor runs every command with the task directory as its working directory, so this script
# only starts if that path resolves. A symbolic link there is not the agent's task directory.
if [ -L "${TASK}" ]; then
    rm -f "${TASK}"
    mkdir "${TASK}" && chown agent:agent "${TASK}"
    phase "the task directory was a symbolic link; replaced it with an empty directory"
fi

# As in run_task.sh: keep the /tmp targets of symbolic links in the task directory. Nothing else
# that the agent left in scratch space reaches the verifier.
: > "${WORK}/tmp.list"
while IFS= read -r link; do
    target="$(readlink "${link}")"
    case "${target}" in
        /tmp/?*) ;;
        *) continue ;;
    esac
    case "${target}" in
        *..*) continue ;;
    esac
    [ -e "${target}" ] || continue
    resolved="$(realpath -e -- "${target}")" || continue
    case "${resolved}" in
        /tmp/?*) ;;
        *) continue ;;
    esac
    printf '%s\0' "${target}" >> "${WORK}/tmp.list"
    phase "snapshot ${link} -> ${target} ($(du -sh "${target}" | cut -f1))"
done < <(find "${TASK}" -maxdepth 1 -type l)

# The evaluation server does not get the agent CLI's state or credentials. Remove them as
# user agent, so that root never follows a path that the agent laid out.
as_agent() {
    /usr/bin/env -i /usr/bin/setpriv --reuid=agent --regid=agent --clear-groups "$@"
}
as_agent /bin/rm -rf /home/agent/.nvm /home/agent/.npm /home/agent/.claude /home/agent/.claude.json \
    /home/agent/.codex /home/agent/.gemini /home/agent/.config/opencode \
    /home/agent/.local/share/opencode /home/agent/.local/share/claude
as_agent /usr/bin/find /home/agent \( -name oauth_token -o -name api_key \) -type f -delete
# Hugging Face tokens that a login writes, and git or netrc credentials, which the trial directory
# would otherwise keep: Harbor's secret scrubbing does not look inside the hand-off's archive.
as_agent /bin/rm -f /home/agent/hf_cache/token /home/agent/hf_cache/stored_tokens \
    /home/agent/.cache/huggingface/token /home/agent/.cache/huggingface/stored_tokens \
    /home/agent/.huggingface/token /home/agent/.git-credentials /home/agent/.netrc

# The model files that the healthcheck downloaded and that are unchanged stay out of the stream:
# the verifier downloads the same revision and puts them back.
phase "packing /home/agent ($(du -sh /home/agent | cut -f1))"
if ! python3 -I "${LIB}/handoff.py" pack --home /home/agent --record "${RECORD}" \
    --tmp-list "${WORK}/tmp.list" --out "${HANDOFF}"; then
    # Harbor would still carry the parts of an unfinished hand-off to the verifier.
    rm -f "${HANDOFF}"/part.* "${HANDOFF}/manifest.json"
    phase "ERROR: could not pack the hand-off"
    exit 1
fi
date --iso-8601=seconds > "${HANDOFF}/complete"
phase "ready for the verifier: $(du -sh "${HANDOFF}" | cut -f1) in ${HANDOFF}"
