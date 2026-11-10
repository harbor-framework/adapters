"""Build replay-verified oracle solutions for VimGolf-Gym tasks.

Candidate sources, tried in order for every challenge:
  1. ``public``   - the worst public solution scraped from vimgolf.com
  2. ``repaired`` - the public solution with key names unknown to vimgolf 0.5.1's
                    tokenizer rewritten (e.g. <BS> -> <C-H>, normal-mode arrows -> hjkl)
  3. ``diff``     - a deterministic line/char-diff edit script (diff_solver.py)
  4. ``minimized``- any replay-correct candidate above shrunk by delta debugging
  5. ``llm``      - solutions supplied in llm_solutions.json (see README)
A candidate is accepted only if it passes the same checks as tests/grade.py:
first non-empty line, keystrokes <= len(raw output), replay checksum match.
This is candidate screening with the local Vim (and `--not-a-term`, which only skips
Vim's 2 s not-a-terminal pause). Certification is a `harbor run -a oracle` over every
generated task in the pinned image with the real grader (its 10 s / 15 s timeouts, no
`--not-a-term`); an oracle that does not get reward 1 there is dropped and its challenge
listed in excluded.txt.

Usage: python build_oracles.py <challenges.zip> <out oracle_solutions.json> [--minimize]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import vimgolf.vimgolf
from vimgolf.vimgolf import format_, tokenize_keycode_reprs

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from vimgolf_gym.adapter import load_challenges  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
from diff_solver import solve as diff_solve  # noqa: E402

VIMRC = os.path.join(os.path.dirname(vimgolf.vimgolf.__file__), "vimgolf.vimrc")
LLM_FILE = Path(__file__).parent / "llm_solutions.json"
# vimgolf-verifier.py waits 10 s for Vim. Delta-debugging trials often drop the final
# write/quit and would hang for the full 10 s, so they use a short timeout; the result
# is re-checked with the full timeout before it is accepted.
REPLAY_TIMEOUT_SEC = 10
TRIAL_TIMEOUT_SEC = 2
MINIMIZE_BUDGET_SEC = 600  # per challenge, shared by all minimized candidates


def sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def first_line(content: str) -> str:
    for line in format_(content).split("\n"):
        if line.strip():
            return line
    return ""


def to_feedkeys(keys: str) -> str:
    out = []
    for item in tokenize_keycode_reprs(keys):
        if item == "\\":
            item = "\\\\"
        elif item == '"':
            item = '\\"'
        elif item.startswith("<") and item.endswith(">"):
            item = "\\" + item
        out.append(item)
    return "".join(out)


def replay_checksum(input_content: str, keys: str, timeout: float = REPLAY_TIMEOUT_SEC) -> str:
    """Same as vimgolf-verifier.py (image v0.0.3) run_vimgolf_replay checksum."""
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "input.txt")
        with open(p, "w") as f:
            f.write(input_content)
        cmd = ["vim", "--not-a-term", "-Z", "-n", "--noplugin", "-i", "NONE", "+0", "-u", VIMRC,
               "-U", "NONE", '+call feedkeys("{}", "t")'.format(to_feedkeys(keys)), p]
        try:
            # cwd = the temp dir: keystrokes like ":w name" write relative files.
            # env = tests/grade.py's replay env. No TERM: with one, Vim decodes termcodes
            # such as <Esc>[201~ (bracketed-paste end) that the grader replays literally.
            env = {"PATH": os.environ["PATH"], "HOME": d, "LANG": "C.UTF-8"}
            subprocess.run(cmd, capture_output=True, timeout=timeout, stdin=subprocess.DEVNULL,
                           cwd=d, env=env)
        except subprocess.TimeoutExpired:
            pass
        if not os.path.isfile(p):
            return ""
        try:
            with open(p) as f:
                out = f.read()
        except UnicodeDecodeError:
            return ""
        return sha(out) if out else ""


def passes(c, keys: str) -> tuple[bool, str, int]:
    line = first_line(keys)
    if not line:
        return False, "empty", 0
    n = len(tokenize_keycode_reprs(line))
    if n > len(c.output):
        ok = replay_checksum(format_(c.input), line) == sha(format_(c.output))
        return False, "too_long_correct" if ok else "too_long", n
    ok = replay_checksum(format_(c.input), line) == sha(format_(c.output))
    return ok, "ok" if ok else "mismatch", n


ARROWS = {"<Left>": "h", "<Right>": "l", "<Up>": "k", "<Down>": "j"}


def repair(keys: str) -> str:
    """Rewrite key names that vimgolf 0.5.1 cannot tokenize into equivalents it can."""
    keys = re.sub(r"<BS>", "<C-H>", keys, flags=re.I)
    keys = re.sub(r"<kEnter>", "<CR>", keys, flags=re.I)
    for k, v in ARROWS.items():
        keys = re.sub(re.escape(k), v, keys, flags=re.I)
    return keys


def minimize(c, keys: str, deadline: float) -> str | None:
    """Delta-debug a replay-correct solution down to the keystroke budget."""
    toks = tokenize_keycode_reprs(first_line(keys))
    target = sha(format_(c.output))
    inp = format_(c.input)

    def ok(ts):
        return replay_checksum(inp, "".join(ts), TRIAL_TIMEOUT_SEC) == target

    if not ok(toks):
        return None
    chunk = max(1, len(toks) // 2)
    while chunk >= 1 and len(toks) > len(c.output) and time.monotonic() < deadline:
        i, changed = 0, False
        while i < len(toks) and time.monotonic() < deadline:
            trial = toks[:i] + toks[i + chunk:]
            if trial and ok(trial):
                toks, changed = trial, True
            else:
                i += chunk
        if not changed:
            chunk //= 2
    if len(toks) > len(c.output):
        return None
    small = "".join(toks)
    return small if replay_checksum(inp, small) == target else None


def build_one(c, llm: dict, do_minimize: bool) -> dict:
    tried = []
    public = c.public_solution or ""
    candidates = [("public", public), ("repaired", repair(public)),
                  ("diff", diff_solve(c.input, c.output))]
    for extra in llm.get(c.challenge_id, []):
        candidates.append(("llm", extra))
    seen = set()
    correct_long = []
    for source, keys in candidates:
        if not keys or keys in seen:
            continue
        seen.add(keys)
        ok, why, n = passes(c, keys)
        tried.append({"source": source, "why": why, "keystrokes": n})
        if ok:
            return {"id": c.challenge_id, "keys": first_line(keys), "source": source,
                    "keystrokes": n, "budget": len(c.output), "tried": tried}
        if why == "too_long_correct":
            correct_long.append((n, source, keys))
    if do_minimize:
        deadline = time.monotonic() + MINIMIZE_BUDGET_SEC
        for n, source, keys in sorted(correct_long):
            if time.monotonic() >= deadline:
                break
            small = minimize(c, keys, deadline)
            if small:
                k = len(tokenize_keycode_reprs(small))
                return {"id": c.challenge_id, "keys": small, "source": f"minimized-{source}",
                        "keystrokes": k, "budget": len(c.output), "tried": tried}
    return {"id": c.challenge_id, "keys": None, "source": None,
            "budget": len(c.output), "tried": tried}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("zip_path", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--minimize", action="store_true")
    ap.add_argument("--report", type=Path, default=None)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--retry-failed", action="store_true",
                    help="rebuild challenges the report lists without a solution")
    args = ap.parse_args()

    challenges = load_challenges(args.zip_path)
    llm = json.loads(LLM_FILE.read_text()) if LLM_FILE.exists() else {}
    # the report is appended per challenge, so an interrupted run resumes where it stopped
    done = {}
    if args.report and args.report.exists():
        for line in args.report.read_text().splitlines():
            try:
                r = json.loads(line)
            except json.JSONDecodeError:  # torn last line of an interrupted run
                continue
            if r["keys"] or not args.retry_failed:
                done[r["id"]] = r
    todo = [c for cid, c in challenges.items() if cid not in done]
    print(f"{len(done)} done, {len(todo)} to build", flush=True)
    lock = threading.Lock()
    rows = list(done.values())
    with ThreadPoolExecutor(args.workers) as ex:
        futures = [ex.submit(build_one, c, llm, args.minimize) for c in todo]
        for k, fut in enumerate(as_completed(futures), 1):
            r = fut.result()
            with lock:
                rows.append(r)
                if args.report:
                    with args.report.open("a") as f:
                        f.write(json.dumps(r) + "\n")
            print(f"[{k}/{len(todo)}] {r['id']} {r['source']}", flush=True)

    oracles = {r["id"]: {"keys": r["keys"], "source": r["source"], "keystrokes": r["keystrokes"]}
               for r in rows if r["keys"]}
    args.out.write_text(json.dumps(dict(sorted(oracles.items())), indent=1) + "\n")
    from collections import Counter
    print("challenges", len(rows), "verified", len(oracles))
    print(Counter(r["source"] for r in rows))


if __name__ == "__main__":
    main()
