#!/bin/bash
# Derived from aisa-group/InferenceBench src/harbor_adapter/template/environment/collect.sh
# (Apache-2.0). Harbor runs this as root after the agent phase and before it uploads /tests.
# Nothing the agent owns may run as root here: use a clean PATH and PYTHONPATH and leave the
# agent's working directory.
set -uo pipefail
cd /
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
export PYTHONPATH="/opt/filelock_workarounds/soft_file_locks"
export PYTHONNOUSERSITE=1
unset PYTHONUSERBASE PIP_USER
source /usr/local/lib/inferencebench/agent_processes.sh

STATE=/var/lib/ib_state
TASK=/home/agent/task
rm -rf "${STATE}" /tests
mkdir -m 700 "${STATE}" "${STATE}/tmp"
# Keep the log where only root can write it. Harbor gets a copy however this script ends.
exec 3>&1 >> "${STATE}/collect.log" 2>&1
publish_log() {
    cat "${STATE}/collect.log" >&3
    mkdir -p /logs/artifacts
    cp --remove-destination "${STATE}/collect.log" /logs/artifacts/collect.log
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

# Harbor runs every command with the task directory as its working directory, so this script
# only starts if that path resolves. A symbolic link there is not the agent's task directory.
if [ -L "${TASK}" ]; then
    rm -f "${TASK}"
    mkdir "${TASK}" && chown agent:agent "${TASK}"
    phase "the task directory was a symbolic link; replaced it with an empty directory"
fi

# The verifier writes here as root, and the agent could write here until now.
find /logs/verifier -mindepth 1 -delete
chown root:root /logs/verifier && chmod 700 /logs/verifier

# As in run_task.sh: keep the /tmp targets of symbolic links in the task directory, and drop
# everything else the agent left in scratch space.
phase "tmp snapshot"
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
    if mkdir -p "$(dirname "${STATE}${target}")" && cp -aT -- "${target}" "${STATE}${target}"; then
        phase "snapshot ${link} -> ${target} ($(du -sh "${STATE}${target}" | cut -f1))"
    else
        phase "ERROR: snapshot of ${target} failed"
        exit 1
    fi
done < <(find "${TASK}" -maxdepth 1 -type l)
find /tmp /var/tmp /dev/shm -mindepth 1 -user agent -delete 2> /dev/null

# The evaluation server does not get the agent CLI's state or credentials. Remove them as
# user agent, so that root never follows a path that the agent laid out.
as_agent() {
    /usr/bin/env -i /usr/bin/setpriv --reuid=agent --regid=agent --clear-groups "$@"
}
as_agent /bin/rm -rf /home/agent/.nvm /home/agent/.npm /home/agent/.claude /home/agent/.claude.json \
    /home/agent/.codex /home/agent/.gemini /home/agent/.config/opencode \
    /home/agent/.local/share/opencode /home/agent/.local/share/claude
as_agent /usr/bin/find /home/agent \( -name oauth_token -o -name api_key \) -type f -delete

date --iso-8601=seconds > "${STATE}/complete"
phase "ready for the verifier; /home/agent is $(du -sh /home/agent | cut -f1)"
