#!/bin/sh
set -eu
mkdir -p /logs/artifacts
cp "$(dirname "$0")/answer.txt" /logs/artifacts/answer.txt
