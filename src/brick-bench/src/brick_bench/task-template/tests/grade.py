"""BrickBench verifier: upstream verify.py + flatten.py + bricknet-render + vqa.py.

Ports the exact evaluation logic from kulits/BrickAgent@b3df55e36c669b22ef089b13db1ee841907d09b3:
1. Physical verification (verify.py) executed in an unprivileged subprocess (`builder`).
2. Flatten rebuilt MPD to LDR (flatten.py) and render 8 views at 1024x1024, 64 samples via bricknet-render.
3. Dependency-gated VQA judging with google/gemma-4-31B-it @ 842da3794eaa0b77d5f08bae87a17459d91ff475.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from contextlib import redirect_stdout
from pathlib import Path

import numpy as np

# --- Upstream verify.py constants ---
LIMITS: dict[str, tuple[int, int | None]] = {
    "model": (1, 400),
    "val": (1, 100),
    "set": (400, 4000),
    "alt-build": (1, None),
}

# --- Upstream vqa.py / vlm.py constants ---
VIEWS = 8
DEFAULT_MODEL = "google/gemma-4-31B-it"
DEFAULT_REVISION = "842da3794eaa0b77d5f08bae87a17459d91ff475"

BINARY = """Say yes if the views support it and no if they do not. You must choose one of the two
for every question; there is no third option. Where the evidence is thin, decide on the balance
of what the eight views show."""

HEADER = """{intro}

It was built from this brief:
{prompt}

Answer the numbered questions below about THIS build. Use the views together -- a feature need
not be visible in every view. Judge only what you can see: do not assume a detail is present
because the brief asks for it, and do not infer hidden details from how such an object is
usually made. Keep one consistent assignment of objects to roles across all the questions.

{answer_policy}

{questions}

End your reply with exactly {count} lines, nothing after them, one per question:

<number>: <yes|no>
"""

LINE = re.compile(r"^\s*(\d+)\s*[:.)]\s*(yes|no)\b", re.IGNORECASE | re.MULTILINE)


# --- Upstream verify.py logic ---


def geometry(data: bytes) -> dict[bytes, list[list[bytes]]]:
    """Each embedded file's part lines, sorted: same placements in another order are the same model."""
    files: dict[bytes, list[list[bytes]]] = {}
    name = b""
    for line in data.splitlines():
        if line.startswith(b"0 FILE "):
            name = line[7:].strip()
            files.setdefault(name, [])
        elif line.startswith(b"1 "):
            files.setdefault(name, []).append(line.split())
    return {name: sorted(lines) for name, lines in files.items()}


def rebuild(work: Path):
    """The Assembly returned by work/build.py's build(), imported with workspace first on sys.path."""
    sys.path.insert(0, str(work))
    spec = importlib.util.spec_from_file_location("build", work / "build.py")
    if spec is None or spec.loader is None:
        raise ValueError(f"Could not load spec from {work / 'build.py'}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build()


def verify_workspace(work: Path, split: str, rebuilt_mpd: Path | None = None) -> dict:
    """Exact upstream verify() report; optionally writes the rebuilt MPD for downstream rendering."""
    import brickagent as b
    from bricknet import collision

    started, errors = time.perf_counter(), []
    report: dict = {"split": split, "collision": {"tau_ldu": collision.TAU}}
    try:
        if collision.TAU != 1.0:
            raise ValueError("Evaluation requires TAU=1.0 LDU")
        inventory = os.environ.get("BRICKAGENT_SET")
        if split == "alt-build" and not inventory:
            raise ValueError("Alt-Build is validated against its inventory; set BRICKAGENT_SET")
        inventory_bytes = Path(inventory).read_bytes() if inventory else None
        report["build_sha256"] = hashlib.sha256((work / "build.py").read_bytes()).hexdigest()
        os.chdir(work)
        with redirect_stdout(sys.stderr):
            model = rebuild(work)
        if os.environ.get("BRICKAGENT_SET") != inventory:
            raise ValueError("The build changed the inventory setting")
        if inventory and Path(inventory).read_bytes() != inventory_bytes:
            raise ValueError("The build changed the inventory file")
        flat_parts = b.parts(model)
        report.update(
            parts=len(flat_parts),
            distinct_parts=len({p.stem for p in flat_parts}),
            authored_attachments=len(tuple(b.attachments(model))),
            part_color_counts=[
                [stem, color, count]
                for (stem, color), count in sorted(Counter((p.stem, p.color) for p in flat_parts).items())
            ],
        )
        minimum, maximum = LIMITS[split]
        if len(flat_parts) < minimum or (maximum is not None and len(flat_parts) > maximum):
            errors.append(f"{len(flat_parts)} parts outside {split} limits")
        expected = (work / "model.mpd").read_bytes()
        with tempfile.TemporaryDirectory() as folder:
            actual_path = b.write(model, Path(folder) / "model.mpd")
            actual = actual_path.read_bytes()
        if rebuilt_mpd is not None:
            rebuilt_mpd.parent.mkdir(parents=True, exist_ok=True)
            rebuilt_mpd.write_bytes(actual)
        report.update(
            mpd_sha256=hashlib.sha256(expected).hexdigest(),
            mpd_geometry_reproduced=geometry(actual) == geometry(expected),
            mpd_reproduced_byte_for_byte=actual == expected,
        )
        try:
            with redirect_stdout(sys.stderr):
                b.check(model)
            report["full_default_check"] = "passed"
        except Exception as exc:  # noqa: BLE001 — match upstream verify.py catch-all
            report["full_default_check"] = "failed"
            errors.append(f"{type(exc).__name__}: {exc}")
        graph = b.connections(model)
        report.update(
            connected_components=len(graph.components),
            component_sizes=sorted(map(len, graph.components), reverse=True),
            native_connection_edges=len(graph.edges),
        )
    except Exception as exc:  # noqa: BLE001 — match upstream verify.py catch-all
        errors.append(f"{type(exc).__name__}: {exc}")
    return dict(report, valid=not errors, errors=errors, seconds=time.perf_counter() - started)


# --- Upstream flatten.py logic ---


def _mpd_files(text: str) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    name, lead = None, []
    for line in text.splitlines():
        if line.startswith("0 FILE "):
            name = line[7:].strip().lower()
            found.setdefault(name, [])
            found.setdefault("", found[name])
        elif line.strip() != "0 NOFILE":
            (found.setdefault(name, []) if name else lead).append(line)
    return found or {"": lead}


def _mpd_parts(found: dict, name: str = "", pose=None, color: str = "16", above: tuple = ()) -> list:
    if pose is None:
        pose = np.eye(4)
    rows = [line.split() for line in found[name]]
    return [
        placed
        for fields in rows
        if len(fields) >= 15 and fields[0] == "1"
        for placed in _mpd_expand(found, fields, name, pose, color, above)
    ]


def _mpd_expand(found: dict, fields: list[str], name: str, pose, color: str, above: tuple) -> list:
    values = np.array(fields[2:14], dtype=float)
    local = np.eye(4)
    local[:3, 3], local[:3, :3] = values[:3], values[3:].reshape(3, 3)
    child, shade = " ".join(fields[14:]), color if fields[1] == "16" else fields[1]
    if child.lower() in found and child.lower() not in above:
        return _mpd_parts(found, child.lower(), pose @ local, shade, (*above, name))
    return [(shade, pose @ local, child)]


def _fmt_number(value: float) -> str:
    return f"{round(value, 6) + 0.0:.6f}".rstrip("0").rstrip(".")


def flatten_mpd(text: str, title: str) -> str:
    """Exact upstream flatten.flat(): expand embedded files into flat LDraw text."""
    rows = [
        " ".join(["1", shade, *map(_fmt_number, [*pose[:3, 3], *pose[:3, :3].ravel()]), part])
        for shade, pose, part in _mpd_parts(_mpd_files(text))
    ]
    return "\n".join([f"0 {title}", f"0 Name: {title}.ldr", *rows]) + "\n"


# --- Upstream vqa.py logic ---


def format_vqa_prompt(task: dict) -> str:
    """Exact upstream vqa.text() question sheet for one task."""
    return HEADER.format(
        intro=f"You are shown {VIEWS} views of a single LEGO build, photographed from {VIEWS} angles around it.",
        prompt=task["prompt"],
        answer_policy=BINARY,
        questions="\n".join(f"{i}. {q['question']}" for i, q in enumerate(task["questions"], 1)),
        count=len(task["questions"]),
    )


def parse_vqa_reply(task: dict, content: str) -> dict[str, str] | None:
    """Exact upstream vqa.answers() parser."""
    got = {int(m.group(1)): m.group(2).lower() for m in LINE.finditer(content)}
    numbered = list(enumerate((q["key"] for q in task["questions"]), 1))
    if all(n in got for n, _ in numbered):
        return {key: got[n] for n, key in numbered}
    return None


def score_vqa(task: dict, verdicts: dict[str, str]) -> dict[str, float]:
    """Exact upstream vqa.scores(): flat and dependency-gated fraction yes."""
    graph = {q["key"]: q.get("dependencies", []) for q in task["questions"]}

    def passed(key: str, seen: tuple = ()) -> bool:
        return (
            key not in seen
            and verdicts.get(key) == "yes"
            and all(passed(dep, (*seen, key)) for dep in graph.get(key, []))
        )

    return {
        "flat": sum(v == "yes" for v in verdicts.values()) / len(verdicts),
        "gated": sum(map(passed, graph)) / len(graph),
    }


def _resolve_local_model_dir(model_id: str, revision: str, cache_dir: Path | None) -> Path | None:
    """Locate a pre-populated local HF snapshot so read-only cache mounts need zero writes."""
    if cache_dir is None or not cache_dir.is_dir():
        return None
    repo_folder = "models--" + model_id.replace("/", "--")
    candidates = (
        cache_dir / "hub" / repo_folder / "snapshots" / revision,
        cache_dir / repo_folder / "snapshots" / revision,
        cache_dir / revision,
        cache_dir,
    )
    for cand in candidates:
        if (cand / "config.json").is_file():
            return cand
    return None


def run_vqa_judge(task: dict, view_paths: list[Path], model_id: str, revision: str) -> tuple[str, str]:
    """Run upstream vlm.Judge (Gemma 4 31B greedy, enable_thinking=False) on 8 views."""
    import torch
    from PIL import Image
    from transformers import AutoModelForMultimodalLM, AutoProcessor

    cache_env = os.environ.get("BRICKBENCH_HF_CACHE_DIR", "").strip()
    local_dir = _resolve_local_model_dir(model_id, revision, Path(cache_env) if cache_env else None)

    if local_dir is not None:
        source_label = f"local:{local_dir}"
        processor = AutoProcessor.from_pretrained(str(local_dir), padding_side="left", local_files_only=True)
        model = AutoModelForMultimodalLM.from_pretrained(
            str(local_dir), dtype="auto", device_map="auto", local_files_only=True
        )
    else:
        source_label = f"hub:{model_id}@{revision}"
        processor = AutoProcessor.from_pretrained(model_id, revision=revision, padding_side="left")
        model = AutoModelForMultimodalLM.from_pretrained(
            model_id, revision=revision, dtype="auto", device_map="auto"
        )

    images = [Image.open(p).convert("RGB") for p in view_paths[:VIEWS]]
    prompt_text = format_vqa_prompt(task)
    conversations = [
        [
            {
                "role": "user",
                "content": [{"type": "image", "image": img} for img in images]
                + [{"type": "text", "text": prompt_text}],
            }
        ]
    ]
    inputs = processor.apply_chat_template(
        conversations,
        tokenize=True,
        return_dict=True,
        return_tensors="pt",
        add_generation_prompt=True,
        enable_thinking=False,
        processor_kwargs={"padding": True},
    ).to(model.device)
    with torch.inference_mode():
        outputs = model.generate(**inputs, max_new_tokens=2048, do_sample=False)
    decoded = processor.batch_decode(outputs[:, inputs["input_ids"].shape[-1] :], skip_special_tokens=True)
    return decoded[0], source_label


def _write_reward(log_dir: Path, *, reward: float, valid: float, vqa_gated: float, vqa_flat: float) -> None:
    payload = {
        "reward": float(reward),
        "valid": float(valid),
        "vqa_gated": float(vqa_gated),
        "vqa_flat": float(vqa_flat),
    }
    (log_dir / "reward.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _run_verify_subprocess(
    work_dir: Path,
    split: str,
    inventory_path: Path | None,
    staging_dir: Path,
) -> tuple[dict, Path]:
    """Run upstream verify() in an isolated unprivileged `builder` subprocess."""
    sandbox_work = staging_dir / "work"
    out_dir = staging_dir / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    if work_dir.is_dir():
        shutil.copytree(work_dir, sandbox_work, symlinks=False)
    else:
        sandbox_work.mkdir(parents=True, exist_ok=True)

    # Make staging accessible to unprivileged `builder` user without exposing /logs/verifier.
    use_builder = os.geteuid() == 0
    if use_builder:
        import pwd

        pw = pwd.getpwnam("builder")
        os.chmod(staging_dir, 0o755)
        for root, dirs, files in os.walk(staging_dir):
            os.chown(root, pw.pw_uid, pw.pw_gid)
            for d in dirs:
                os.chown(os.path.join(root, d), pw.pw_uid, pw.pw_gid)
            for f in files:
                os.chown(os.path.join(root, f), pw.pw_uid, pw.pw_gid)

    out_json = out_dir / "verification.json"
    rebuilt_mpd = out_dir / "rebuilt.mpd"
    env = {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "HOME": "/home/builder" if use_builder else os.environ.get("HOME", "/tmp"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        "BRICKNET_DATA": os.environ.get("BRICKNET_DATA", "/opt/bricknet"),
        "BRICKNET_CATALOG": os.environ.get("BRICKNET_CATALOG", "v1"),
    }
    if split == "alt-build" and inventory_path is not None:
        env["BRICKAGENT_SET"] = str(inventory_path)

    cmd = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--verify-only",
        str(sandbox_work),
        "--split",
        split,
        "--output",
        str(out_json),
        "--rebuilt-mpd",
        str(rebuilt_mpd),
    ]
    kwargs: dict = {"env": env, "capture_output": True, "text": True, "timeout": 300}
    if use_builder:
        kwargs["user"] = "builder"

    try:
        proc = subprocess.run(cmd, check=False, **kwargs)
    except subprocess.TimeoutExpired as exc:
        return (
            {
                "split": split,
                "valid": False,
                "errors": [f"TimeoutExpired: verify subprocess exceeded {exc.timeout}s"],
            },
            rebuilt_mpd,
        )

    if out_json.is_file():
        report = json.loads(out_json.read_text(encoding="utf-8"))
        return report, rebuilt_mpd

    err_tail = (proc.stderr or proc.stdout or "").strip()[-500:]
    return (
        {
            "split": split,
            "valid": False,
            "errors": [f"verify subprocess exited {proc.returncode} without writing report: {err_tail}"],
        },
        rebuilt_mpd,
    )


def grade(
    *,
    tests_dir: Path = Path("/tests"),
    work_dir: Path = Path("/work"),
    log_dir: Path = Path("/logs/verifier"),
) -> int:
    log_dir.mkdir(parents=True, exist_ok=True)
    task = json.loads((tests_dir / "task.json").read_text(encoding="utf-8"))
    split = task["split"]
    inventory_path = tests_dir / "inventory.json" if split == "alt-build" else None

    with tempfile.TemporaryDirectory(prefix="brickbench-grade-") as tmp:
        staging = Path(tmp)
        report, rebuilt_mpd = _run_verify_subprocess(work_dir, split, inventory_path, staging)
        (log_dir / "verification.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

        if not report.get("valid"):
            print(f"[brickbench] invalid submission ({task['id']}): {report.get('errors')}", flush=True)
            _write_reward(log_dir, reward=0.0, valid=0.0, vqa_gated=0.0, vqa_flat=0.0)
            return 0

        if not rebuilt_mpd.is_file():
            raise RuntimeError("verify passed but rebuilt.mpd was not written")

        # Stage 2: Flatten rebuilt MPD and render 8 views via upstream bricknet-render.
        ldr_path = staging / f"{task['id']}.ldr"
        ldr_text = flatten_mpd(rebuilt_mpd.read_text(encoding="utf-8", errors="replace"), task["id"])
        ldr_path.write_text(ldr_text, encoding="utf-8")

        renders_dir = log_dir / "renders"
        renders_dir.mkdir(parents=True, exist_ok=True)
        render_device = os.environ.get("BRICKBENCH_RENDER_DEVICE", "GPU").strip() or "GPU"
        render_cmd = [
            "bricknet-render",
            str(ldr_path),
            str(renders_dir),
            "--views",
            str(VIEWS),
            "--resolution",
            "1024x1024",
            "--samples",
            "64",
            "--device",
            render_device,
        ]
        print(f"[brickbench] rendering {task['id']}: {' '.join(render_cmd)}", flush=True)
        subprocess.run(render_cmd, check=True)

        view_paths = sorted(renders_dir.glob("*.png"))
        if len(view_paths) < VIEWS:
            raise RuntimeError(f"bricknet-render produced {len(view_paths)} PNGs, expected {VIEWS}")

        # Stage 3: Judge 8 views with Gemma 4 31B using exact upstream VQA prompt and gating.
        model_id = os.environ.get("BRICKBENCH_VLM_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
        revision = os.environ.get("BRICKBENCH_VLM_REVISION", DEFAULT_REVISION).strip() or DEFAULT_REVISION
        print(f"[brickbench] running VQA judge ({model_id}@{revision}) on {len(view_paths)} views", flush=True)
        reply, model_source = run_vqa_judge(task, view_paths, model_id, revision)
        verdicts = parse_vqa_reply(task, reply)

        if verdicts is None:
            vqa_record = {
                "ok": False,
                "task": task["id"],
                "split": split,
                "model": model_id,
                "revision": revision,
                "model_source": model_source,
                "reply": reply,
            }
            (log_dir / "vqa.json").write_text(json.dumps(vqa_record, indent=2) + "\n", encoding="utf-8")
            print(f"[brickbench] VQA judge reply could not be parsed for {task['id']}", file=sys.stderr)
            return 1

        vqa_scores = score_vqa(task, verdicts)
        vqa_record = {
            "ok": True,
            "task": task["id"],
            "split": split,
            "model": model_id,
            "revision": revision,
            "model_source": model_source,
            "verdicts": verdicts,
            "gated": vqa_scores["gated"],
            "flat": vqa_scores["flat"],
            "reply": reply,
        }
        (log_dir / "vqa.json").write_text(json.dumps(vqa_record, indent=2) + "\n", encoding="utf-8")
        _write_reward(
            log_dir,
            reward=vqa_scores["gated"],
            valid=1.0,
            vqa_gated=vqa_scores["gated"],
            vqa_flat=vqa_scores["flat"],
        )
        print(
            f"[brickbench] {task['id']}: valid=1.0 vqa_gated={vqa_scores['gated']:.4f} vqa_flat={vqa_scores['flat']:.4f}",
            flush=True,
        )
        return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", type=Path, default=None)
    parser.add_argument("--split", choices=tuple(LIMITS), default="model")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--rebuilt-mpd", type=Path, default=None)
    args = parser.parse_args(argv)

    if args.verify_only is not None:
        report = verify_workspace(args.verify_only.resolve(), args.split, rebuilt_mpd=args.rebuilt_mpd)
        text = json.dumps(report, indent=2) + "\n"
        if args.output is not None:
            args.output.write_text(text, encoding="utf-8")
        else:
            print(text, end="")
        return int(not report["valid"])

    return grade()


if __name__ == "__main__":
    raise SystemExit(main())
