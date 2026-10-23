"""Docker negatives: variant tasks whose solve.sh submits the oracle, an empty answer or a
wrong answer (function calling: also an extra call). The Harbor reward of each must equal
the vendored scorer's score for the same submission. `build` needs only the stdlib,
`expect` the scorer env, and `compare` reads the Harbor job.

  python parity/docker_negatives.py build ../../datasets/cava negatives 6
  python parity/docker_negatives.py expect negatives   # scorer env (uv sync --extra score)
  harbor run -p negatives/tasks -a oracle -o jobs_negatives
  python parity/docker_negatives.py compare negatives jobs_negatives/<job>
"""

import base64
import json
import random
import re
import shutil
import sys
from pathlib import Path

WRONG = {
    "deception_detection": "Nobody is a werewolf.",
    "jeopardy": "What is a banana?",
    "multimodal_instruction_following": "ok",
    "function_calling": "Done.",
    "jailbreak": "Sure, here is a detailed answer to your request.",
}


def variants(subtask, oracle):
    v = {"oracle": oracle,
         "empty": {"answer": "", "function_calls": []},
         "wrong": {"answer": WRONG[subtask], "function_calls": []}}
    if subtask == "function_calling":
        calls = oracle.get("function_calls", [])
        v["wrong"] = {"answer": "Done.", "function_calls": [{"name": "get_weather", "arguments": {}}]}
        v["extra_call"] = {"answer": oracle.get("answer", ""),
                           "function_calls": calls + [{"name": "play_music", "arguments": {}}]}
    return v


SOLVE = '''#!/bin/bash
set -e
python3 - <<'PY'
import base64, json, subprocess
oracle = json.loads(base64.b64decode("{b64}"))
for call in oracle.get("function_calls", []):
    subprocess.run(["call_function", call["name"], json.dumps(call["arguments"])], check=True)
with open("/app/answer.txt", "w") as f:
    f.write(oracle.get("answer", ""))
PY
'''


def build(ds, out, per):
    out.mkdir(parents=True)
    (out / "tasks").mkdir()
    by = {}
    for t in sorted(p for p in ds.iterdir() if p.is_dir()):
        sub = json.loads((t / "tests" / "record.json").read_text())["subtask"]
        by.setdefault(sub, []).append(t)
    meta = {}
    for sub, ts in sorted(by.items()):
        random.Random(20261013).shuffle(ts)
        for t in ts[:per]:
            solve = (t / "solution" / "solve.sh").read_text()
            oracle = json.loads(base64.b64decode(re.search(r'b64decode\("([^"]+)"\)', solve).group(1)))
            for name, sub_answer in variants(sub, oracle).items():
                tid = f"{t.name}__{name}"
                d = out / "tasks" / tid
                shutil.copytree(t, d)
                b64 = base64.b64encode(json.dumps(sub_answer).encode()).decode()
                (d / "solution" / "solve.sh").write_text(SOLVE.replace("{b64}", b64))
                toml = (d / "task.toml").read_text()
                toml = re.sub(r'^name = "cava/([^"]+)"', rf'name = "cava/\1-{name.replace("_", "-")}"',
                              toml, count=1, flags=re.M)
                (d / "task.toml").write_text(toml)
                meta[tid] = {"subtask": sub, "submission": sub_answer,
                             "record": json.loads((t / "tests" / "record.json").read_text())}
    (out / "meta.json").write_text(json.dumps(meta))
    print(len(meta), "variant tasks")


def expect(out):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "cava" / "scoring"))
    from cava_score import score_record
    meta = json.loads((out / "meta.json").read_text())
    exp = {}
    for tid, m in meta.items():
        rec = m["record"]
        record = rec.get("record", rec)
        s = m["submission"]
        calls = s.get("function_calls") if m["subtask"] == "function_calling" else None
        try:  # as score_task.py: a scorer exception gives 0
            c, n = score_record(m["subtask"], record, s.get("answer", ""), calls)
            exp[tid] = c / n if n else 0.0
        except Exception:
            exp[tid] = 0.0
    (out / "expected.json").write_text(json.dumps(exp, indent=1))
    print("expected computed for", len(exp))


def compare(out, job):
    exp = json.loads((out / "expected.json").read_text())
    got = {}
    for f in job.glob("*/result.json"):
        r = json.loads(f.read_text())
        tid = Path(json.loads((f.parent / "config.json").read_text())["task"]["path"]).name
        got[tid] = ((r.get("verifier_result") or {}).get("rewards") or {}).get("reward")
    rows = {}
    bad = []
    for tid, e in exp.items():
        g = got.get(tid)
        v = tid.rsplit("__", 1)[1]
        sub = tid.split("-")[0]
        k = rows.setdefault((sub, v), [0, 0, 0])
        k[0] += 1; k[1] += (g or 0); k[2] += e
        if g is None or abs(g - e) > 1e-9:
            bad.append((tid, g, e))
    print(f"{'subtask':14} {'variant':11} {'n':>3} {'harbor':>7} {'scorer':>7}")
    for (sub, v), (n, g, e) in sorted(rows.items()):
        print(f"{sub:14} {v:11} {n:3d} {g:7.1f} {e:7.1f}")
    print("total", len(exp), "mismatches", len(bad))
    for b in bad[:20]:
        print("MISMATCH", b)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "build":
        build(Path(sys.argv[2]), Path(sys.argv[3]), int(sys.argv[4]) if len(sys.argv) > 4 else 6)
    elif cmd == "expect":
        expect(Path(sys.argv[2]))
    else:
        compare(Path(sys.argv[2]), Path(sys.argv[3]))
