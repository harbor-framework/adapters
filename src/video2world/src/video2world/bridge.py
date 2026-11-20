"""Public profile checks and final grading in Harbor's separate verifier."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import io
import json
import math
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

MAX_PACKAGE_BYTES = 2 * 1024**3


def package_files(root: Path) -> list[Path]:
    if root.is_symlink() or not root.is_dir():
        raise ValueError(f"submission artifact must be a directory: {root}")
    files = sorted(root.rglob("*"))
    size = 0
    for path in files:
        if path.is_symlink() or not (path.is_dir() or path.is_file()):
            raise ValueError(f"submission contains a symlink or special file: {path}")
        if path.is_file():
            size += path.stat().st_size
        if size > MAX_PACKAGE_BYTES:
            raise ValueError("submission exceeds the 2 GiB transport limit")
    return files


def pack(root: Path) -> bytes:
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:gz") as archive:
        for path in package_files(root):
            archive.add(path, arcname=str(path.relative_to(root)), recursive=False)
    return stream.getvalue()


def unpack(payload: bytes, root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
        members = archive.getmembers()
        size = 0
        seen = set()
        for member in members:
            path = Path(member.name)
            if (
                path.is_absolute()
                or ".." in path.parts
                or not path.parts
                or member.name in seen
            ):
                raise ValueError(f"invalid archive path: {member.name}")
            seen.add(member.name)
            if not (member.isfile() or member.isdir()):
                raise ValueError(f"archive link or special file: {member.name}")
            size += member.size
            if size > MAX_PACKAGE_BYTES:
                raise ValueError("archive exceeds the 2 GiB transport limit")
        # Only regular files/directories with relative paths passed the checks above.
        archive.extractall(root, members=members, filter="data")


def write_reward(report: dict, out: Path) -> None:
    if report.get("readiness") != "ready":
        raise RuntimeError(
            f"upstream score is blocked; inspect {out}/report/summary.json"
        )
    score = report.get("v2w_score")
    if (
        type(score) not in (int, float)
        or not math.isfinite(score)
        or not 0 <= score <= 100
    ):
        raise ValueError("ready upstream report has an invalid V2WScore")
    (out / "reward.txt").write_text(f"{score / 100:.17g}\n")


def request(url: str, package: Path) -> dict:
    payload = pack(package)
    if len(payload) > MAX_PACKAGE_BYTES:
        raise ValueError("compressed submission exceeds the 2 GiB transport limit")
    headers = {"Content-Type": "application/gzip"}
    req = urllib.request.Request(url + "/check", data=payload, headers=headers)
    with urllib.request.urlopen(req, timeout=5550) as response:
        return json.loads(response.read())


def grade(args) -> None:
    config = json.loads(args.config.read_text())
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    for name in ("reward.txt", "reward.json"):
        (out / name).unlink(missing_ok=True)
    preflight(args.root, args.data, config)
    row = config["configuration"]
    (out / "identity.json").write_text(
        json.dumps(
            {
                "family": row["family"],
                "sample": row["sample"],
                "upstream_revision": config["upstream_revision"],
                "manifest_sha256": config["manifest_sha256"],
            },
            indent=2,
        )
        + "\n"
    )
    # The artifact handoff must succeed before a missing protocol can be scored as
    # an agent failure. A missing artifact is an infrastructure error, not zero.
    package_files(args.package)
    package = out / "submission"
    shutil.copytree(args.package, package)
    evaluate(row, package, out)
    report = json.loads((out / "report/summary.json").read_text())
    write_reward(report, out)


def evaluate(configuration: dict, package: Path, work: Path) -> None:
    from v2w import benchmark, paths, runner, scoring

    config = benchmark.Configuration(
        configuration["family"], configuration["sample"], configuration["metric_family"]
    )
    exp = runner.Experiment(work / "upstream/experiment")
    directory = exp.dir(config)
    directory.mkdir(parents=True)
    package.rename(directory / "pkg")
    runner.dump(
        directory / "agent.json",
        {"package": (directory / "pkg/protocol.json").is_file()},
    )
    if not (directory / "pkg/protocol.json").is_file():
        # Upstream's defined missing-submission failure, retained in the denominator.
        exp.evaluate(config, retry=False)
    else:
        tool, module, extra = benchmark.EVALUATORS[config.evaluator]
        ev = directory / "eval"
        ev.mkdir()
        cmd = [
            paths.tool(tool),
            "-m",
            module,
            "--run",
            str(directory / "pkg"),
            "--sample",
            str(config.sample_dir),
            "--out",
            str(ev / "eval.json"),
            *extra,
        ]
        (work / "command.json").write_text(json.dumps(cmd) + "\n")
        try:
            with (ev / "eval.log").open("w") as log:
                subprocess.run(
                    cmd,
                    cwd=paths.REPO,
                    env=paths.env(CUDA_VISIBLE_DEVICES=0),
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    timeout=runner.EVAL_TIMEOUT,
                    check=True,
                )
            result = json.loads((ev / "eval.json").read_text())
            if not isinstance(result, dict):
                raise TypeError("upstream eval.json must contain an object")
            infra = runner.infra_error(ev)
            if infra and not result.get("build"):
                raise RuntimeError(f"upstream infrastructure error: {infra}")
        except (
            OSError,
            ValueError,
            TypeError,
            RuntimeError,
            subprocess.SubprocessError,
        ) as exc:
            if (ev / "eval.json").exists():
                (ev / "eval.json").rename(ev / "eval.command-output.json")
            runner.dump(
                ev / "eval.json",
                {
                    "sample": config.sample,
                    "build": None,
                    "error_kind": "evaluator",
                    "error": f"{type(exc).__name__}: {exc}; see eval.log",
                },
            )
    exp.metrics(config)
    record = json.loads((directory / "metrics.json").read_text())
    (work / "metrics.json").write_text(json.dumps(record, indent=2) + "\n")
    score_config = scoring.load_config()
    scope = scoring.make_scope([configuration], score_config)
    report = scoring.score(
        {(config.family, config.sample): record}, scope, score_config
    )
    scoring.write_report(report, work / "report")


def preflight(root: Path, data: Path, config: dict) -> None:
    sys.path.insert(0, str(root))
    os.environ["V2W_DATA"] = str(data)
    manifest = data / "manifest.json"
    if hashlib.sha256(manifest.read_bytes()).hexdigest() != config["manifest_sha256"]:
        raise ValueError("data manifest does not match the pinned release")
    rows = json.loads(manifest.read_text())["samples"]
    if config["configuration"] not in rows:
        raise ValueError("evaluator configuration differs from the pinned manifest")
    for relative, digest in config["source_files"].items():
        if hashlib.sha256((root / relative).read_bytes()).hexdigest() != digest:
            raise ValueError(f"upstream changed after task generation: {relative}")
    # Enforce upstream's exact wheel pins before accepting any package.
    for requirement in config["requirements"]:
        if "==" in requirement:
            name, expected = requirement.split("==")
            actual = importlib.metadata.version(name)
            if actual != expected:
                raise ValueError(f"runtime requires {requirement}, found {actual}")
    for tool in ("python", "twin_python", "isaac_python"):
        if tool in config["tools"]:
            interpreter = config["tools"][tool]
            if not Path(interpreter).is_file() or not os.access(interpreter, os.X_OK):
                raise ValueError(
                    f"{tool} is not executable in the runtime: {interpreter}"
                )
    evaluator = config["configuration"]["metric_family"].get("evaluator")
    if evaluator == "fb":
        # These upstream rig/library reads are unconditional, including for Push-T.
        importlib.import_module("v2w.tracks.furniture.sim")
        library = importlib.import_module("video2sim.bench.bridge_env")
        library.library_info()
        from v2w import paths

        sample = config["configuration"]["sample"]
        scene = json.loads(
            (data / "samples" / sample / "hidden/scene_gt.json").read_text()
        )
        for entity in scene["objects"] + scene["props"]:
            if entity.get("kind") == "mesh":
                recorded = Path(entity.get("mesh_path") or entity["collision_path"])
                if not recorded.is_file():
                    raise FileNotFoundError(
                        f"evaluator-only GT mesh required at {recorded}; release path: "
                        f"{paths.resolve(recorded)}; configure a read-only runtime mount "
                        "at the recorded path"
                    )
    if evaluator == "robodojo_native_task":
        source = config["tools"]["robodojo_source"]
        revision = subprocess.check_output(
            ["git", "--git-dir", str(Path(source) / ".git"), "rev-parse", "HEAD"],
            text=True,
        ).strip()
        if not revision.startswith("25691aa"):
            raise ValueError("RoboDojo must be checked out at 25691aa")


def serve(args) -> None:
    config = json.loads(args.config.read_text())
    preflight(args.root, args.data, config)
    from v2w import benchmark
    from v2w.agents import checks

    row = config["configuration"]
    c = benchmark.Configuration(row["family"], row["sample"], row["metric_family"])

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path != "/check":
                self.send_error(404)
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= MAX_PACKAGE_BYTES:
                    raise ValueError("invalid request size (maximum 2 GiB)")
                with tempfile.TemporaryDirectory(
                    prefix="v2w-check-", dir=args.work
                ) as tmp:
                    pkg = Path(tmp) / "pkg"
                    unpack(self.rfile.read(size), pkg)
                    result = {"errors": checks.errors(c.profile, pkg, c.sample_dir)}
                payload = json.dumps(result).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            except (
                OSError,
                ValueError,
                KeyError,
                TypeError,
                RuntimeError,
                subprocess.SubprocessError,
                tarfile.TarError,
            ) as exc:
                self.send_error(500, f"{type(exc).__name__}: {exc}")

    args.work.mkdir(parents=True, exist_ok=True)
    HTTPServer(("0.0.0.0", args.port), Handler).serve_forever()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    server = subs.add_parser("serve")
    server.add_argument("--root", type=Path, default=Path("/opt/video2world"))
    server.add_argument("--data", type=Path, default=Path("/data"))
    server.add_argument("--config", type=Path, default=Path("/adapter/config.json"))
    server.add_argument("--work", type=Path, default=Path("/work"))
    server.add_argument("--port", type=int, default=8080)
    check = subs.add_parser("check")
    check.add_argument("--task", type=Path, required=True)
    check.add_argument("package", type=Path, nargs="?")
    check.add_argument("--url", default="http://evaluator:8080")
    verifier = subs.add_parser("grade")
    verifier.add_argument("--package", type=Path, required=True)
    verifier.add_argument("--root", type=Path, default=Path("/opt/video2world"))
    verifier.add_argument("--data", type=Path, default=Path("/data"))
    verifier.add_argument("--config", type=Path, required=True)
    verifier.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "serve":
        serve(args)
    elif args.command == "grade":
        grade(args)
    else:
        spec = json.loads((args.task / "task.json").read_text())
        errors = request(args.url, args.package or Path(spec["out"]))["errors"]
        for error in errors:
            print("[FAIL] " + error)
        print("OK" if not errors else f"{len(errors)} error(s)")
        raise SystemExit(bool(errors))


if __name__ == "__main__":
    main()
