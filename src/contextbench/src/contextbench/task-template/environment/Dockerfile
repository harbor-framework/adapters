FROM --platform=linux/amd64 __GIT_IMAGE__ AS source

ARG REPOSITORY_URL="__REPOSITORY_URL__"
ARG BASE_COMMIT="__BASE_COMMIT__"
RUN git init /repository \
    && git -C /repository remote add origin "$REPOSITORY_URL" \
    && git -C /repository fetch --depth=1 origin "$BASE_COMMIT" \
    && git -C /repository checkout --detach "$BASE_COMMIT" \
    && git -C /repository remote remove origin \
    && rm -f /repository/.git/FETCH_HEAD \
    && rm -rf /repository/.git/logs /repository/.git/refs/remotes \
    && git -C /repository reflog expire --expire=now --all \
    && git -C /repository gc --prune=now \
    && test "$(git -C /repository rev-parse HEAD)" = "$BASE_COMMIT"

FROM --platform=linux/amd64 __NATIVE_IMAGE__

USER root
ENTRYPOINT []

# Keep the native repository tree with its build state (compiled extensions,
# installed dependencies), but replace its history with the one-commit base
# checkout and remove the files the source benchmark ships for grading.
# /workspace is a stable Harbor-facing alias for the native repository location.
# A wrong repository path must fail here: the swap would otherwise build a fresh
# tree and leave the native one, with its history, beside it.
RUN test -e "__NATIVE_REPOSITORY_PATH__/.git"
RUN rm -rf __REMOVED_PATHS__
COPY --from=source /repository/.git __NATIVE_REPOSITORY_PATH__/.git
# Populated submodules point into the removed native history, so their files
# stay as plain directories. HEAD and the index are the base commit, while the
# working tree keeps the image's build-time edits to tracked files, as native
# agents see them. Git ignores file modes, because some images change the mode
# of every file and their own history records it. The model patch must hold
# only the agent's changes, so the image's untracked files are excluded (the
# patterns escape glob characters), and the tree the image left is recorded in
# .git/contextbench-baseline-tree as the patch's baseline. That tree is an
# unreferenced object, so garbage collection must not prune it. The index that
# holds it, .git/contextbench-baseline-index, is what the collect step updates
# (in a copy), so the agent's own index never affects the patch.
#
# A container sees the image's files with new inodes and ctimes, so under Git's
# default stat checks the first Git command in a container re-reads every
# tracked file (37 s for mui/material-ui with a cold page cache). Git compares
# only the size and the whole-second mtime instead, which image layers keep
# (core.checkStat=minimal, and core.trustctime=false, without which Git's
# documentation says the ctime second is still compared). The trade-off: an
# edit that keeps a file's size and its recorded mtime second goes unseen. The
# collect step compares against the baseline index, which records the image's
# mtimes, so there it takes resetting the mtime to the image's (touch -r,
# cp -p). Before Git 2.35, `reset --quiet` does not refresh the index, so
# update-index records the image's stat data.
RUN ln -s "__NATIVE_REPOSITORY_PATH__" /workspace \
    && git config --global --add safe.directory "__NATIVE_REPOSITORY_PATH__" \
    && cd /workspace \
    && git ls-files --stage | while read -r mode object stage path; do \
        if [ "$mode" = 160000 ]; then rm -rf "$path/.git"; fi; \
    done \
    && git config core.fileMode false \
    && git config core.checkStat minimal \
    && git config core.trustctime false \
    && git reset --quiet "__BASE_COMMIT__" \
    && git update-index -q --refresh \
    && test "$(git rev-parse HEAD)" = "__BASE_COMMIT__" \
    && git config gc.auto 0 \
    && git config gc.pruneExpire never \
    && mkdir -p .git/info \
    && git ls-files -z --others --exclude-standard --directory | tr '\0' '\n' \
        | sed 's/[][\\*?]/\\&/g; s/ $/\\ /; s|^|/|' >> .git/info/exclude \
    && test -z "$(git ls-files --others --exclude-standard)" \
__RECORD_BASELINE__
__PROJECT_ENVIRONMENT__
WORKDIR /workspace
CMD ["/bin/bash"]
