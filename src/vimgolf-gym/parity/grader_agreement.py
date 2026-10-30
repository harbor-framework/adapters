"""Grader agreement: the same solutions graded by upstream vimgolf-evaluate.py and by the
Harbor verifier. Builds (a) task dirs whose oracle writes each solution variant (oracle,
oracle padded to exactly the keystroke budget, one over it, last key dropped, wrong,
empty, and two attempts to read the expected output from agent-shipped files) and (b) the
vimgolf-benchmark jsonl for the upstream evaluator. Needs the `vimgolf` package (vimgolf-gym deps).

Usage:
  python parity/grader_agreement.py build ../../datasets/vimgolf-gym agree 40
  harbor run -p agree/tasks -a oracle -o jobs_agree
  python vimgolf-evaluate.py --solution-format vimgolf-benchmark \
      --jsonl-file agree/upstream.jsonl --validator vimgolf-validator \
      --solution-not-longer-than-output --result-savepath agree/upstream_result.json
  python parity/grader_agreement.py compare agree jobs_agree/<job> agree/upstream_result.json
"""

import base64
import json
import random
import re
import shutil
import sys
from pathlib import Path

from vimgolf.vimgolf import tokenize_keycode_reprs

CHEAT_TAIL = ":%d|r /app/solution.txt<CR>:1,2d|wq<CR>"
CHEAT_ART = ":%d|r /logs/artifacts/o<CR>:1d|wq<CR>"


def variants(keys: str, budget: int, output: str) -> dict[str, tuple[str, str, bool]]:
    """name -> (solution.txt content, extra shell for solve.sh, expected pass)."""
    toks = tokenize_keycode_reprs(keys)
    v = {
        "oracle": (keys, "", True),
        "drop_last": ("".join(toks[:-1]), "", None),  # usually fails; graded either way
        "wrong": ("ihello<Esc>:wq<NL>", "", False),
        "empty": ("", "", False),
        "tail_cheat": (CHEAT_TAIL + "\n" + output, "", False),
        "artifacts_cheat": (CHEAT_ART, "mkdir -p /logs/artifacts && cp /app/output.txt /logs/artifacts/o\n", False),
    }
    if len(toks) < budget:
        v["at_budget"] = (keys + "<Esc>" * (budget - len(toks)), "", True)
    v["over_budget"] = (keys + "<Esc>" * (budget - len(toks) + 1), "", False)
    return v


def build(ds: Path, out: Path, n: int) -> None:
    tasks = sorted(p for p in ds.iterdir() if p.is_dir())
    random.Random(20261013).shuffle(tasks)
    out.mkdir(parents=True)
    (out / "tasks").mkdir()
    rows, meta = [], {}
    for t in tasks[:n]:
        grading = json.loads((t / "tests" / "grading.json").read_text())
        solve = (t / "solution" / "solve.sh").read_text()
        keys = base64.b64decode(re.search(r"echo '([^']+)' \| base64", solve).group(1)).decode()
        # newline="": keep CRs, which count toward the keystroke budget upstream
        output = (t / "environment" / "output.txt").open(newline="").read()
        budget = grading["output_len"]
        for name, (content, extra, expect) in variants(keys, budget, output).items():
            tid = f"{t.name}__{name}"
            d = out / "tasks" / tid
            shutil.copytree(t, d)
            b64 = base64.b64encode(content.encode()).decode()
            (d / "solution" / "solve.sh").write_text(
                "#!/bin/bash\nset -e\n" + extra + f"echo '{b64}' | base64 -d > /app/solution.txt\n")
            toml = (d / "task.toml").read_text()
            toml = re.sub(r'^name = "vimgolf-gym/([^"]+)"', rf'name = "vimgolf-gym/\1-{name.replace("_", "-")}"',
                          toml, count=1, flags=re.M)
            (d / "task.toml").write_text(toml)
            # upstream receives the same solution text; the evaluator extracts line 1
            rows.append(dict(task_id=grading["challenge_id"], dataset_name="agreement",
                             trial_name=tid, start_time=0.0, elapsed_time=0.0, solution=content,
                             input_content=grading["input"], output_content=output))
            meta[tid] = expect
    (out / "upstream.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (out / "expected.json").write_text(json.dumps(meta, indent=1))
    print(len(rows), "solutions from", n, "tasks")


def compare(out: Path, job: Path, upstream_result: Path) -> None:
    meta = json.loads((out / "expected.json").read_text())
    up = json.loads(upstream_result.read_text())
    up_pass = set((up.get("eval_result") or up)["validated_ids"])
    harbor = {}
    for f in job.glob("*/result.json"):
        r = json.loads(f.read_text())
        cfg = json.loads((f.parent / "config.json").read_text())
        tid = Path(cfg["task"]["path"]).name
        rw = ((r.get("verifier_result") or {}).get("rewards") or {}).get("reward")
        harbor[tid] = rw
    rows, disagree, unexpected = [], [], []
    for tid, expect in meta.items():
        h = harbor.get(tid)
        u = tid in up_pass
        hp = h == 1.0
        if h is None:
            disagree.append((tid, "harbor missing", u))
        elif hp != u:
            disagree.append((tid, f"harbor={h}", f"upstream={u}"))
        if expect is not None and hp != expect:
            unexpected.append((tid, hp, expect))
        rows.append((tid.rsplit("__", 1)[1], hp, u))
    by = {}
    for v, hp, u in rows:
        s = by.setdefault(v, [0, 0, 0])
        s[0] += 1; s[1] += hp; s[2] += u
    print(f"{'variant':16} {'n':>4} {'harbor pass':>12} {'upstream pass':>14}")
    for v, (n, hp, u) in sorted(by.items()):
        print(f"{v:16} {n:4d} {hp:12d} {u:14d}")
    print(f"total {len(rows)}; disagreements {len(disagree)}; unexpected vs design {len(unexpected)}")
    for d in disagree[:20]:
        print("DISAGREE", d)
    for d in unexpected[:20]:
        print("UNEXPECTED", d)


if __name__ == "__main__":
    if sys.argv[1] == "build":
        build(Path(sys.argv[2]), Path(sys.argv[3]), int(sys.argv[4]) if len(sys.argv) > 4 else 40)
    else:
        compare(Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]))
