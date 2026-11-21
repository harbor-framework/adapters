#!/bin/bash
set -euo pipefail

mode=${1:?expected freeze, collect or verify}
repo=${2:-/testbed}
state=${3:-/usr/local/share/harbor-lighthouse1549}
base=${4:-e5fdadd8272ca456afb5dcd4b52c8e67f7d9e73c}
output=${5:-/tmp/harbor-submission/model.patch}
[[ "$repo" = /* && "$state" = /* && "$output" = /* ]]
[[ "$base" =~ ^[0-9a-f]{40}$ ]]
cd "$repo"
git_image() {
    git -c "safe.directory=$repo" -c core.fileMode=true "$@"
}
files=(. ':(exclude)problem_assets' ':(exclude)problem_assets/**')
scratch=$(mktemp -d)
pending=
trap 'rm -rf -- "$scratch"; if [[ -n "$pending" ]]; then rm -f -- "$pending"; fi' EXIT

read_frozen() {
    baseline=$(cat "$state/baseline.tree")
    [[ "$baseline" =~ ^[0-9a-f]{40}$ ]]
    [[ "$(git_image cat-file -t "$baseline")" = tree ]]
}
capture_tree() {
    git_image read-tree "$1" &&
    git_image add -A -- "${files[@]}" &&
    git_image write-tree
}
export GIT_INDEX_FILE="$scratch/index"
case "$mode" in
    freeze)
        [[ "$(git_image rev-parse --verify HEAD)" = "$base" ]]
        mkdir -p "$state"
        [[ ! -e "$state/baseline.tree" ]]
        capture_tree "$base" > "$state/baseline.tree"
        chmod 0444 "$state/baseline.tree"
        ;;
    collect)
        mkdir -p "$(dirname -- "$output")"
        rm -f -- "$output"
        read_frozen
        submitted=$(capture_tree "$baseline")
        pending=$(mktemp "$(dirname -- "$output")/model.patch.XXXXXXXX")
        git_image diff --binary --no-ext-diff --no-textconv "$baseline" "$submitted" -- "${files[@]}" > "$pending"
        mv -- "$pending" "$output"
        pending=
        ;;
    verify)
        [[ "$(git_image rev-parse --verify HEAD)" = "$base" ]]
        read_frozen
        observed=$(capture_tree "$baseline")
        [[ "$observed" = "$baseline" ]]
        ;;
    *)
        exit 2
        ;;
esac
