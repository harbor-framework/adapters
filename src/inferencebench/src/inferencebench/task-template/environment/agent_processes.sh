# Sourced by collect.sh and test.sh, which run as root. Derived from the cleanup barrier in
# aisa-group/InferenceBench src/run_task.sh (Apache-2.0). Every process of user agent is
# untrusted, and the verifier shares its sandbox, so nothing may start while one is alive.

agent_processes_remain() {
    local state
    while read -r state; do
        # A zombie cannot run and holds no resources.
        case "${state}" in
            Z* | "") ;;
            *) return 0 ;;
        esac
    done < <(ps -o stat= -u agent -U agent 2> /dev/null)
    return 1
}

# A process of user agent signals every process of that user in one kernel pass, which a
# fork loop cannot outrun the way it can outrun the scan that pkill does. Check the result,
# and retry, because a process that held GPU memory can take seconds to exit.
kill_agent_processes() {
    local attempt
    for attempt in $(seq 1 40); do
        /usr/bin/env -i /usr/bin/setpriv --reuid=agent --regid=agent --clear-groups \
            /bin/bash --noprofile --norc -c 'kill -s KILL -- -1' > /dev/null 2>&1
        pkill -KILL -u agent > /dev/null 2>&1
        agent_processes_remain || return 0
        sleep 0.5
    done
    echo "processes of user agent survived ${attempt} kill passes:"
    ps -o pid=,stat=,args= -u agent -U agent 2> /dev/null | head -20
    return 1
}
