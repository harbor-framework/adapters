#!/usr/bin/env python3
"""Harbor verifier for one 3DCodeBench text-to-3D instance.

Runs under Blender's bundled Python (`blender-python`) and reproduces the
upstream scoring pipeline of gaoypeng/3dcodebench, using the upstream helper
scripts verbatim from /tests/upstream/:

  1. core/render.py (Blender side, CYCLES, 64 spp, 512 px, 600 s cap)
       status == "OK"  <=>  script ran without exception, >= 1 mesh object
       exists afterwards, and all 4 reference views rendered.
       This is the upstream `executability` metric (metrics/executability.py).
  2. core/export_glb.py (Blender side, 600 s cap) for the agent's script and
     for the hidden reference script.
  3. metrics/shape_chamfer.py functions: 8192 surface points per mesh,
     unit-sphere normalisation, symmetric squared Chamfer, min over 4 yaws.

The agent's script is re-executed from a copy, so a GLB or render the agent
produced itself never counts (same as upstream "bake the .py independently").

Outputs:
  /logs/verifier/reward.txt     executability, 0 or 1 (Harbor reward)
  /logs/verifier/metrics.json   statuses, errors, Chamfer distances, timings
  /logs/verifier/eval/          renders, GLB and Blender logs for inspection
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path

UPSTREAM = Path("/tests/upstream")
REFERENCE_DIR = Path("/tests/reference")
WORKSPACE = Path("/workspace")
VERIFIER_DIR = Path("/logs/verifier")
EVAL_DIR = VERIFIER_DIR / "eval"
BLENDER = shutil.which("blender") or "blender"

# Render settings are the upstream defaults (core/render.py). The upstream
# per-call caps (render 240 s, export 180 s) were set for GPU rendering; on the
# CPU-only Harbor image they time out on valid reference scripts (e.g.
# BasketBase, PalmTree, Bed), so both caps are raised to 600 s. The dataset
# card asks for scripts that finish in < 5 min on one CPU core.
RENDER_TIMEOUT_S = 600
RENDER_ARGS = ["--samples", "64", "--resolution", "512", "--engine", "CYCLES"]
EXPORT_TIMEOUT_S = 600
REFERENCE_EXPORT_TIMEOUT_S = 600
CHAMFER_N_POINTS = 8192
CHAMFER_SEED = 0


def run_blender(helper: str, args: list[str], timeout: int, log_path: Path) -> dict:
    """Run an upstream helper in Blender background mode, mirroring the
    upstream orchestrators' timeout / missing-log handling."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [BLENDER, "--background", "--python", str(UPSTREAM / helper), "--", *args]
    t0 = time.time()
    stdout_path = log_path.parent / f"{log_path.stem}.blender.log"
    try:
        with open(stdout_path, "w") as fh:
            subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, timeout=timeout)
    except subprocess.TimeoutExpired:
        rec = {
            "status": "ERR_TIMEOUT",
            "error": f"Blender subprocess exceeded {timeout}s",
            "latency_s": round(time.time() - t0, 2),
        }
        log_path.write_text(json.dumps(rec, indent=2))
        return rec
    if log_path.exists():
        try:
            return json.loads(log_path.read_text())
        except json.JSONDecodeError as e:
            return {"status": "ERR_BADLOG", "error": f"{type(e).__name__}: {e}"}
    rec = {
        "status": "ERR_NOLOG",
        "error": "Blender exited without writing a log (likely segfault)",
        "latency_s": round(time.time() - t0, 2),
    }
    log_path.write_text(json.dumps(rec, indent=2))
    return rec


def export_glb(script: Path, out_dir: Path, name: str, timeout: int) -> tuple[dict, Path]:
    glb = out_dir / f"{name}.glb"
    rec = run_blender(
        "export_glb.py",
        ["--blender-export", "--script", str(script), "--out-glb", str(glb),
         "--log-path", str(out_dir / "export_log.json")],
        timeout,
        out_dir / "export_log.json",
    )
    return rec, glb


def chamfer(ref_glb: Path, gen_glb: Path) -> dict:
    sys.path.insert(0, str(UPSTREAM))
    import numpy as np
    import shape_chamfer as sc

    rng = np.random.default_rng(CHAMFER_SEED)
    ref_pts = sc.load_mesh_points(ref_glb, CHAMFER_N_POINTS, rng)
    gen_pts = sc.load_mesh_points(gen_glb, CHAMFER_N_POINTS, rng)
    if ref_pts is None:
        return {"chamfer_status": "BAD_REF_MESH"}
    if gen_pts is None:
        return {"chamfer_status": "BAD_GEN_MESH"}
    cd0, cd_min, yaw, cd_yaw = sc.chamfer_with_yaw(
        sc.normalize_unit_sphere(ref_pts), sc.normalize_unit_sphere(gen_pts)
    )
    return {
        "chamfer_status": "OK",
        "cd": cd0,
        "cd_yawmin": cd_min,
        "yaw_argmin": yaw,
        "cd_per_yaw": cd_yaw,
    }


def evaluate(instance: str) -> dict:
    m: dict = {
        "instance": instance,
        "executability": 0,
        "render_status": None,
        "export_status": None,
        "chamfer_status": None,
        "cd": None,
        "cd_yawmin": None,
        "agent_done_sentinel": (WORKSPACE / ".agent_done").is_file(),
    }
    agent_script = WORKSPACE / f"{instance}.py"
    if not agent_script.is_file():
        m["render_status"] = "MISSING"
        m["error"] = f"{agent_script} not found"
        return m

    gen_dir = EVAL_DIR / "generated"
    gen_dir.mkdir(parents=True, exist_ok=True)
    gen_script = gen_dir / f"{instance}.py"
    shutil.copy2(agent_script, gen_script)
    m["code_chars"] = gen_script.stat().st_size

    # 1. executability (upstream render_log.json status)
    renders = gen_dir / "renders"
    rec = run_blender(
        "render.py",
        ["--blender-render", "--script", str(gen_script), "--output-dir", str(renders), *RENDER_ARGS],
        RENDER_TIMEOUT_S,
        renders / "render_log.json",
    )
    m["render_status"] = rec.get("status")
    m["render_error"] = rec.get("error")
    m["n_meshes"] = rec.get("n_meshes")
    m["n_views_rendered"] = rec.get("n_views_rendered")
    m["render_latency_s"] = rec.get("latency_s")
    m["executability"] = int(rec.get("status") == "OK")
    if rec.get("status") == "ERR_TIMEOUT":
        # Export re-runs the same script under the same cap; skip it.
        m["export_status"] = "SKIPPED_RENDER_TIMEOUT"
        return m

    # 2. GLB of the agent's object
    erec, gen_glb = export_glb(gen_script, gen_dir / "glb", instance, EXPORT_TIMEOUT_S)
    m["export_status"] = erec.get("status")
    m["export_error"] = erec.get("error")
    if erec.get("status") != "OK":
        return m

    # 3. GLB of the hidden reference, then Chamfer distance
    ref_dir = EVAL_DIR / "reference"
    rrec, ref_glb = export_glb(
        REFERENCE_DIR / f"{instance}.py", ref_dir, instance, REFERENCE_EXPORT_TIMEOUT_S
    )
    m["reference_export_status"] = rrec.get("status")
    if rrec.get("status") != "OK":
        m["chamfer_status"] = "NO_REF_GLB"
        m["reference_export_error"] = rrec.get("error")
        return m
    m.update(chamfer(ref_glb, gen_glb))
    ref_glb.unlink(missing_ok=True)  # reproducible from tests/; keep logs small
    return m


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instance", required=True)
    args = parser.parse_args()

    VERIFIER_DIR.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    try:
        metrics = evaluate(args.instance)
    except Exception as e:
        # Verifier bug or infrastructure problem, not an agent outcome: record
        # it and write no reward so Harbor reports a failed trial, not a 0.
        metrics = {
            "instance": args.instance,
            "verifier_error": f"{type(e).__name__}: {e}\n{traceback.format_exc()}",
            "verifier_latency_s": round(time.time() - t0, 2),
        }
        (VERIFIER_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2))
        print(metrics["verifier_error"], file=sys.stderr)
        return 1
    metrics["verifier_latency_s"] = round(time.time() - t0, 2)

    (VERIFIER_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2))
    (VERIFIER_DIR / "reward.txt").write_text(f"{metrics['executability']}\n")
    print(json.dumps({k: metrics.get(k) for k in (
        "instance", "executability", "render_status", "export_status",
        "chamfer_status", "cd", "cd_yawmin")}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
