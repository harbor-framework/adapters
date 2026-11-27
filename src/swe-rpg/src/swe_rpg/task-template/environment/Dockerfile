# The published task images are built for linux/amd64 only.
FROM --platform=linux/amd64 {docker_image}

WORKDIR {working_dir}

{image_fixup}

# The published image keeps the upstream remote and every later commit, which
# include the fix. Keep only the history up to the task's base commit, and
# remove files left behind by earlier test runs. Some images also carry local
# changes on top of the base commit, so the starting state of the working tree
# is recorded under refs/task/start; the agent's changes are later measured
# against it.
RUN set -eu; cd {working_dir}; \
    git config --global --add safe.directory {working_dir}; \
    test "$(git rev-parse HEAD)" = "{base_commit}"; \
    for r in $(git remote); do git remote remove "$r"; done; \
    branch="$(git symbolic-ref -q HEAD || true)"; \
    git for-each-ref --format='%(refname)' | while read -r ref; do \
        if [ "$ref" = "$branch" ]; then continue; fi; \
        case "$ref" in refs/tags/*) if git merge-base --is-ancestor "$ref^{commit}" HEAD 2>/dev/null; then continue; fi;; esac; \
        git update-ref -d "$ref"; \
    done; \
    rm -f .git/FETCH_HEAD .git/ORIG_HEAD; rm -rf .git/logs; \
    git reflog expire --expire=now --all; \
    git gc -q --prune=now; \
    test "$(git rev-parse HEAD)" = "{base_commit}"; \
    test "$(git rev-list --all | wc -l)" = "$(git rev-list HEAD | wc -l)"; \
    git ls-files --others --exclude-standard -z | xargs -0 -r rm -f; \
    git add -A; \
    start="$(git -c user.name=task -c user.email=task@localhost commit-tree "$(git write-tree)" -p HEAD -m 'task start')"; \
    git update-ref refs/task/start "$start"; \
    git reset -q
