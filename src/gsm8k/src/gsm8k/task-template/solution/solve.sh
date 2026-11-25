#!/bin/sh
set -eu
mkdir -p /app/output
printf '%s\n' {gold} > /app/output/answer.txt
