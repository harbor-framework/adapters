"""HumanEvalPack verifier.

Rebuilds ``candidate + "\\n" + test`` the way the upstream octopack evaluator
does, using a pristine copy of the upstream test block, and runs it with the
same command and pass criterion as upstream. Exit code 0 means pass.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
CONFIG = json.loads((TESTS_DIR / "config.json").read_text(encoding="utf-8"))
TEST_BLOCK = (TESTS_DIR / "test_block.txt").read_text(encoding="utf-8")


def run(cmd: list[str], cwd: Path, timeout: int, env: dict | None = None):
    print(f"$ {' '.join(cmd)}  (cwd={cwd}, timeout={timeout}s)", flush=True)
    # Own process group, so that a timeout also kills grandchildren (e.g. the
    # test binary started by `cargo test`), not only the direct child.
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**os.environ, **(env or {})},
        start_new_session=True,
    )
    try:
        out_b, err_b = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.communicate()
        print("TIMED OUT")
        return None
    out = out_b.decode("utf-8", "replace")
    err = err_b.decode("utf-8", "replace")
    if out:
        print("--- stdout ---\n" + out[-4000:])
    if err:
        print("--- stderr ---\n" + err[-4000:])
    print(f"exit code: {proc.returncode}")
    return proc.returncode, out, err


def build_program() -> str | None:
    source = Path(CONFIG["file"])
    if not source.is_file():
        print(f"FAIL: {source} does not exist")
        return None
    content = source.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
    # Trailing whitespace of the test block is not significant (editors and the
    # oracle heredoc may drop trailing newlines).
    idx = content.rfind(TEST_BLOCK.rstrip())
    if idx == -1:
        print(
            "FAIL: the original test code at the end of the file was modified or "
            "removed; the verifier needs it unchanged."
        )
        return None
    # Everything before the test block is the candidate; re-append the pristine
    # tests (anything after them is discarded).
    return content[:idx] + TEST_BLOCK


def check(lang: str, program: str, work: Path) -> bool:
    if lang == "python":
        (work / "test.py").write_text(program, encoding="utf-8")
        r = run(["python3", "test.py"], work, 10)
        return r is not None and r[0] == 0

    if lang == "js":
        (work / "test.js").write_text(program, encoding="utf-8")
        r = run(["node", "test.js"], work, 10)
        # Upstream: any stderr or stdout output counts as failure
        # (console.assert writes to stderr and does not change the exit code).
        return r is not None and r[0] == 0 and not r[1] and not r[2]

    if lang == "java":
        (work / "Main.java").write_text(program, encoding="utf-8")
        r = run(["javac", "Main.java"], work, 120)
        if r is None or r[0] != 0:
            return False
        r = run(["java", "-cp", ".", "Main"], work, 10)
        return r is not None and r[0] == 0

    if lang == "go":
        for f in ("go.mod", "go.sum"):
            shutil.copy(Path("/opt/humanevalpack/go") / f, work / f)
        (work / "main_test.go").write_text(program, encoding="utf-8")
        r = run(
            ["go", "test", "-timeout=20s", "main_test.go"],
            work,
            180,
            env={"GOFLAGS": "-mod=mod", "GOPROXY": "off"},
        )
        return r is not None and r[0] == 0

    if lang == "cpp":
        (work / "test.cpp").write_text(program, encoding="utf-8")
        r = run(["g++", "-std=c++11", "test.cpp", "-lcrypto", "-lssl"], work, 120)
        if r is None or r[0] != 0:
            return False
        r = run(["./a.out"], work, 60)
        return r is not None and r[0] == 0

    if lang == "rust":
        shutil.copy(Path("/opt/humanevalpack/rust/Cargo.toml"), work / "Cargo.toml")
        shutil.copy(Path("/opt/humanevalpack/rust/Cargo.lock"), work / "Cargo.lock")
        (work / "src").mkdir()
        (work / "src" / "main.rs").write_text(program, encoding="utf-8")
        env = None  # CARGO_TARGET_DIR (prebuilt deps) comes from the image
        r = run(["cargo", "check", "--offline"], work, 300, env)
        if r is None or r[0] != 0:
            return False
        r = run(["cargo", "test", "--offline"], work, 300, env)
        return r is not None and r[0] == 0

    raise ValueError(f"unknown language {lang}")


def main() -> int:
    program = build_program()
    if program is None:
        return 1
    with tempfile.TemporaryDirectory() as tmp:
        ok = check(CONFIG["lang"], program, Path(tmp))
    print("PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
