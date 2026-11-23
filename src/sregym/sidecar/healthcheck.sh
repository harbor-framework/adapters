#!/bin/sh
# Healthy once the fault is injected, the conductor has opened its first
# agent stage, and the agent kubeconfig has been handed to the shared volume.
test -f /run/harbor-ready
