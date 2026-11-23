"""Record what a trial ran on in /logs/verifier/environment.json.

test.sh runs this as root with `python3 -I` in the verifier's sandbox, after it has received the
agent's files and before the judge and the evaluation. It reads what the sandbox reports about
itself, what the image and the verifier's files pin, and the manifest that collect.sh wrote in the
agent's sandbox. The agent's directories are only listed, never read, and a name taken from them
must match a strict pattern. No credential is recorded: only the environment variables selected
below are copied. The record cannot change a trial's outcome, so every probe is allowed to fail.
"""

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from importlib import metadata
from pathlib import Path

SAMPLES = Path("/opt/inference_eval/baselines/samples")
QUALITY = Path("/opt/inference_eval/baselines/quality")
EVAL_HUB = Path("/opt/ib_eval_hf/hub")
AGENT_HUB = Path("/home/agent/hf_cache/hub")
AGENT_SITE = Path("/home/agent/.local/lib/python3.10/site-packages")
# Written by root in the agent's sandbox; the agent's files are in the parts next to it.
HANDOFF_MANIFEST = Path("/var/lib/ib_handoff/manifest.json")
NVIDIA_SMI = ("/usr/bin/nvidia-smi", "/usr/local/nvidia/bin/nvidia-smi", "/usr/lib/nvidia/current/nvidia-smi")
NODE_MODULES = ("/usr/lib/node_modules", "/usr/local/lib/node_modules")
JUDGE_CLI = "@anthropic-ai/claude-code"
AGENT_CLIS = (JUDGE_CLI, "@openai/codex", "@google/gemini-cli", "opencode-ai")
# Identifiers that a provider sets in its sandboxes. None of them is a credential.
PROVIDER_ENV = (
    "MODAL_CLOUD_PROVIDER",
    "MODAL_REGION",
    "MODAL_IMAGE_ID",
    "MODAL_TASK_ID",
    "MODAL_ENVIRONMENT",
    "DAYTONA_SANDBOX_ID",
    "DAYTONA_SANDBOX_SNAPSHOT",
)
TASK_ENV = ("NUM_HOURS", "HOST", "PORT")
SECRET = re.compile(r"KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL", re.IGNORECASE)
COMMIT = re.compile(r"[0-9a-f]{40}")
DIST_INFO = re.compile(r"([A-Za-z0-9_.]+)-([A-Za-z0-9_.+!]+)\.dist-info")
# The agent decides how many entries its directories have, so a listing reads only this many.
MAX_ENTRIES = 5000


def probe(function, *args):
    try:
        return function(*args)
    except Exception as error:  # noqa: BLE001 - the record must not fail the verifier
        return {"error": f"{type(error).__name__}: {error}"[:300]}


def section(**probes) -> dict:
    return {name: probe(function) for name, function in probes.items()}


def run(command: list[str]) -> str:
    return subprocess.run(command, capture_output=True, text=True, timeout=60, check=True).stdout


def search(pattern: str, path: str) -> str | None:
    match = re.search(pattern, Path(path).read_text(), re.MULTILINE)
    return match[1] if match else None


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def tree_sha256(root: Path) -> dict:
    """Hash the regular files below a directory that only root can write."""
    files = sorted(path for path in root.rglob("*") if path.is_file() and not path.is_symlink())
    digest = hashlib.sha256()
    for path in files:
        digest.update(f"{sha256(path)}  {path.relative_to(root)}\n".encode())
    return {"files": len(files), "sha256": digest.hexdigest()}


def gpus() -> dict:
    binary = next(path for path in NVIDIA_SMI if os.access(path, os.X_OK))
    names = ("index", "name", "memory_total_mib", "driver_version", "vbios_version")
    rows = run([binary, "--query-gpu=index,name,memory.total,driver_version,vbios_version", "--format=csv,noheader,nounits"])
    cuda = re.search(r"CUDA Version:\s*([0-9.]+)", run([binary]))
    return {
        "devices": [dict(zip(names, row.split(", "))) for row in rows.splitlines() if row.strip()],
        "driver_cuda_version": cuda[1] if cuda else None,
    }


def cgroup(name: str) -> str | None:
    path = Path("/sys/fs/cgroup") / name
    return path.read_text().strip() if path.is_file() else None


def disks() -> dict:
    return {
        path: {"total": usage.total >> 20, "free": usage.free >> 20}
        for path in ("/", "/home/agent", "/tmp")
        for usage in [shutil.disk_usage(path)]
    }


def dpkg() -> dict:
    packages = run(["/usr/bin/dpkg-query", "-W", "-f", "${Package}=${Version}\n"])
    return {"packages": len(packages.splitlines()), "sha256": hashlib.sha256(packages.encode()).hexdigest()}


def python_packages() -> dict:
    found = {dist.metadata["Name"]: dist.version for dist in metadata.distributions() if dist.metadata["Name"]}
    return dict(sorted(found.items()))


def agent_clis() -> dict:
    found = {}
    for name in AGENT_CLIS:
        for root in NODE_MODULES:
            manifest = Path(root) / name / "package.json"
            if manifest.is_file():
                found[name] = json.loads(manifest.read_text())["version"]
    return found


def model_dir(hub: Path) -> Path:
    return hub / ("models--" + os.environ["INFERENCE_BENCH_BASE_MODEL"].replace("/", "--"))


def evaluator_model() -> dict:
    """The tokenizer and configuration files that the evaluator loads; only root can write them."""
    root = model_dir(EVAL_HUB)
    revision = (root / "refs" / "main").read_text().strip()
    snapshot = root / "snapshots" / revision
    # The cache names a blob after its git or LFS object id, so a link's target is a content hash.
    return {
        "revision": revision,
        "files": {
            str(path.relative_to(snapshot)): os.path.basename(os.readlink(path))
            for path in sorted(snapshot.rglob("*"))
            if path.is_symlink()
        },
    }


def names(directory: Path) -> list[str]:
    """List at most MAX_ENTRIES names in a directory that the agent controls; nothing is read."""
    with os.scandir(directory) as entries:
        return [entry.name for _, entry in zip(range(MAX_ENTRIES), entries)]


def agent_model_cache() -> dict:
    """The revisions in the agent's cache, which holds the weights."""
    snapshots = model_dir(AGENT_HUB) / "snapshots"
    return {"snapshots": sorted(name for name in names(snapshots) if COMMIT.fullmatch(name))[:20]}


def server_python_packages() -> dict:
    """What the agent installed for its server, from the names in its user site directory."""
    found = dict(match.groups() for name in names(AGENT_SITE) if (match := DIST_INFO.fullmatch(name)))
    return dict(sorted(found.items()))


def handoff() -> dict:
    """What collect.sh handed over from the agent's sandbox."""
    manifest = json.loads(HANDOFF_MANIFEST.read_text())
    model = manifest.get("model") or {}
    return {
        "packed_at_unix": manifest.get("packed_at_unix"),
        "parts": manifest.get("parts"),
        "stream_bytes": manifest.get("stream_bytes"),
        "entries": manifest.get("entries"),
        "tmp_targets": len(manifest.get("tmp_targets", [])),
        "model_files_left_out": len(model.get("left_out", [])),
        "model_bytes_left_out": sum(blob["size"] for blob in model.get("left_out", [])),
        "model_files_changed": model.get("changed", []),
        "model_file_links_and_copies": len(model.get("files", [])),
    }


def same_hardware(verifier_gpus: dict, agent_sandbox: dict) -> dict:
    """Whether the agent tuned its server on the GPUs and driver that measure it."""
    agent = agent_sandbox["gpus"]
    here = verifier_gpus["devices"]
    return {
        field: [gpu[field] for gpu in agent] == [gpu[field] for gpu in here]
        for field in ("name", "memory_total_mib", "driver_version")
    }


def expected_gpu(record: dict) -> dict:
    """Whether each sandbox had a GPU of a type that the task asks for (None if unknown)."""
    types = sorted({gpu_type.rstrip("!") for gpu_type in record["task"]["gpu_types"]})
    found: dict = {"types": types}
    for sandbox, devices in (
        ("verifier", lambda: record["gpus"]["devices"]),
        ("agent_sandbox", lambda: record["agent_sandbox"]["gpus"]),
    ):
        try:
            names = [gpu["name"] for gpu in devices()]
        except (KeyError, TypeError):
            found[sandbox] = None
            continue
        found[sandbox] = bool(names) and all(any(gpu_type in name for gpu_type in types) for name in names)
    return found


def gpu_warnings(record: dict) -> list[str]:
    """What test-stdout.txt should say about the GPUs; the trial is graded either way."""
    warnings = []
    agent, here = record["agent_sandbox"].get("gpus"), record["gpus"].get("devices")
    same = record["same_hardware_as_agent_sandbox"]
    if "error" not in same and not all(same.values()):
        warnings.append(f"the agent's sandbox had {agent}, and this one has {here}")
    expected = record["expected_gpu"]
    if "error" not in expected:
        wanted = " or ".join(expected["types"])
        if expected["verifier"] is False:
            warnings.append(f"this sandbox's GPU is not {wanted}: {here}")
        if expected["agent_sandbox"] is False:
            warnings.append(f"the agent's sandbox's GPU was not {wanted}: {agent}")
    return warnings


def samples() -> dict:
    return {
        str(path.relative_to(SAMPLES)): sha256(path)
        for path in sorted(SAMPLES.rglob("samples.jsonl"))
        if not path.is_symlink()
    }


def quality_reference() -> dict:
    return {
        path.name: {"sha256": sha256(path), "mmlu_pro": json.loads(path.read_text())["datasets"]["mmlu_pro"]}
        for path in sorted(QUALITY.glob("*.json"))
    }


def main() -> None:
    env = os.environ
    record = {
        "recorded_at_unix": int(time.time()),
        "task": probe(lambda: json.loads(Path("/tests/manifest.json").read_text())),
        "environment_variables": {
            name: value
            for name, value in sorted(env.items())
            if (name.startswith("INFERENCE_BENCH_") or name in TASK_ENV) and not SECRET.search(name)
        },
        "provider": {name: env[name] for name in PROVIDER_ENV if name in env},
        "timing": section(
            budget_started_at_unix=lambda: json.loads(HANDOFF_MANIFEST.read_text())["budget_started_at_unix"],
            evaluation_deadline_unix=lambda: int(env["EVAL_DEADLINE"]),
            server_wait_s=lambda: env.get("INFERENCE_BENCH_SERVER_WAIT_S"),
        ),
        "judge": section(
            cli=lambda: JUDGE_CLI,
            cli_version=lambda: agent_clis().get(JUDGE_CLI),
            model=lambda: env.get("JUDGE_MODEL"),
            attempts=lambda: env.get("JUDGE_ATTEMPTS"),
            timeout=lambda: env.get("JUDGE_TIMEOUT"),
        ),
        "gpus": probe(gpus),
        "machine": section(
            platform=platform.platform,
            os=lambda: search(r'^PRETTY_NAME="?([^"\n]+)', "/etc/os-release"),
            cpu_model=lambda: search(r"^model name\s*:\s*(.+)$", "/proc/cpuinfo"),
            cpus_online=os.cpu_count,
            cpus_usable=lambda: len(os.sched_getaffinity(0)),
            cgroup_cpu_max=lambda: cgroup("cpu.max"),
            memory_total_mib=lambda: int(search(r"^MemTotal:\s*(\d+) kB$", "/proc/meminfo")) // 1024,
            cgroup_memory_max=lambda: cgroup("memory.max"),
            disk_mib=disks,
        ),
        "image": section(
            python=lambda: sys.version.split()[0],
            cuda_toolkit=lambda: json.loads(Path("/usr/local/cuda/version.json").read_text())["cuda"]["version"],
            constraints_sha256=lambda: sha256(Path("/opt/inferencebench/constraints.txt")),
            dpkg=dpkg,
            agent_clis=agent_clis,
            python_packages=python_packages,
        ),
        "verifier": {"environment_mode": "separate"},
        "handoff": probe(handoff),
        # The agent ran in another sandbox, which may not have had the same GPU or driver.
        "agent_sandbox": probe(lambda: json.loads(HANDOFF_MANIFEST.read_text())["agent_sandbox"]),
        "evaluator_model": probe(evaluator_model),
        "agent_model_cache": probe(agent_model_cache),
        "server_python_packages": probe(server_python_packages),
        "data": section(samples_sha256=samples, quality_reference=quality_reference),
        "verifier_files": probe(tree_sha256, Path("/tests")),
    }
    record["same_hardware_as_agent_sandbox"] = probe(same_hardware, record["gpus"], record["agent_sandbox"])
    record["expected_gpu"] = probe(expected_gpu, record)
    warnings = probe(gpu_warnings, record)
    for warning in warnings if isinstance(warnings, list) else []:
        print(f"[environment] WARNING: {warning}")
    Path(sys.argv[1]).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"[environment] recorded in {sys.argv[1]}")


if __name__ == "__main__":
    main()
