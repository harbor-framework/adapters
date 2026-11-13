#!/bin/bash
# ARE tasks are open-ended, so there is no reference solution. This checks the
# grading path only: submit the deliverable folder as shipped (empty in most tasks)
# and wait for both graders to score it.
set -euo pipefail
python3 - <<'PY'
import json, time, urllib.request as u

def call(path, post=False):
    req = u.Request("http://grader:8000" + path, method="POST" if post else "GET")
    return json.loads(u.urlopen(req, timeout=60).read())

sub = call("/submit?note=starter", post=True)
while (res := call(f"/result/{sub['id']}"))["status"] != "graded":
    time.sleep(15)
print("validation_score:", res.get("validation_score"), "error:", res.get("error"))
PY
