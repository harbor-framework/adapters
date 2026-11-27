# /// script
# requires-python = ">=3.12"
# dependencies = ["agentdojo==0.1.35", "toml==0.10.2"]
# ///
"""Prepare and run independent native/Harbor AgentDojo parity trials."""

import argparse
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

import toml
from agentdojo.functions_runtime import FunctionsRuntime

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "src"))
from agentdojo_adapter.adapter import AgentDojoAdapter, select_parity_subset


def save(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n")


def environment(env_file):
    env = dict(os.environ)
    for line in env_file.read_text().splitlines():
        name, sep, value = line.strip().removeprefix("export ").partition("=")
        if sep and name.strip() == "API_KEY":
            env["API_KEY"] = shlex.split(value, comments=True)[0]
    if not env.get("API_KEY"):
        raise ValueError("API_KEY is required")
    env.update(API_BASE="https://app.ppapi.ai/v1", OPENAI_API_KEY=env["API_KEY"],
               UV_SYSTEM_CERTS="1", PYTHONPATH=str(PACKAGE / "parity"))
    for key in ("ORACLE_MODE", "CODEX_AUTH_JSON_PATH", "CODEX_FORCE_AUTH_JSON", "CODEX_API_KEY"):
        env.pop(key, None)
    return env


def prepare(args):
    root = args.workspace.resolve()
    root.mkdir(parents=True, exist_ok=True)
    tasks = root / "tasks"
    if tasks.exists():
        raise ValueError("Tasks exist; use a fresh workspace")
    image = json.loads(subprocess.check_output(["docker", "image", "inspect", args.image], text=True))[0]["Id"]
    adapter = AgentDojoAdapter(tasks, split="parity")
    adapter.run()
    records = select_parity_subset(adapter._records(None))
    assert len(records) == 20
    native_configs = root / "native-configs"
    native_configs.mkdir()
    sanity = []
    for suite in sorted(adapter.suites):
        for split in ("user", "attack"):
            sanity.append(min(r.local_id for r in records if r.suite_name == suite and r.split == split))
    for record in records:
        task = tasks / record.local_id
        config = json.loads((task / "environment/runtime-server/task_config.json").read_text())
        config["system_message"] = adapter.system_message
        save(native_configs / f"{record.local_id}.json", config)
        suite = adapter.suites[record.suite_name]
        runtime = FunctionsRuntime(suite.tools)
        save(task / "environment/agent-input.json", {
            "system_message": adapter.system_message,
            "prompt": suite.get_user_task_by_id(record.user_task_id).PROMPT,
            "tool_order": [f.name for f in runtime.functions.values()],
            "tool_definitions": {f.name: {"description": f.description,
                                         "parameters": f.parameters.model_json_schema()}
                                 for f in runtime.functions.values()},
        })
        cfg = toml.loads((task / "task.toml").read_text())
        cfg["environment"]["docker_image"] = image
        (task / "task.toml").write_text(toml.dumps(cfg))
        if args.ca_bundle:
            for df in task.rglob("Dockerfile"):
                shutil.copy2(args.ca_bundle, df.parent / "local-trust.pem")
                lines = df.read_text().splitlines()
                pos = next(i + 1 for i, line in enumerate(lines) if line.startswith("FROM "))
                lines[pos:pos] = [
                    "COPY local-trust.pem /usr/local/share/local-trust.pem",
                    "RUN cp /usr/local/share/local-trust.pem /etc/ssl/certs/ca-certificates.crt",
                    "ENV SSL_CERT_FILE=/usr/local/share/local-trust.pem REQUESTS_CA_BUNDLE=/usr/local/share/local-trust.pem",
                ]
                df.write_text("\n".join(lines) + "\n")
    save(root / "manifest.json", {
        "task_ids": sorted(r.local_id for r in records), "sanity_ids": sanity,
        "image_id": image, "agentdojo_version": "0.1.35", "benchmark_version": "v1.2.2",
        "model": "deepseek-v4.1-flash", "attack": adapter.attack_name,
        "outer_attempts": 3, "tool_loop_max_iters": 15, "timeout_sec": 900,
        "instruction_sha256": {p.name: hashlib.sha256((p / "instruction.md").read_bytes()).hexdigest() for p in tasks.iterdir()},
    })
    print(f"Prepared {len(records)} tasks; {len(sanity)} sanity tasks")


def native_trial(root, output, task_id, manifest, env):
    trial = output / task_id
    trial.mkdir()
    container = "dojo-native-" + uuid.uuid4().hex[:12]
    started = time.time()
    try:
        subprocess.run(["docker", "run", "-d", "--name", container, "--cpus", "1", "--memory", "2g",
                        manifest["image_id"], "sleep", "infinity"], check=True, stdout=subprocess.DEVNULL)
        for src, target in [(PACKAGE / "parity/pipeline.py", "/app/pipeline.py"),
                            (root / "native-configs" / f"{task_id}.json", "/app/config.json")]:
            subprocess.run(["docker", "cp", str(src), container + ":" + target], check=True, stdout=subprocess.DEVNULL)
        with (trial / "pipeline.log").open("w") as log:
            subprocess.run(["docker", "exec", "-e", "API_KEY", "-e", "API_BASE", container,
                            "python", "/app/pipeline.py", "--mode", "native", "--config", "/app/config.json",
                            "--output", "/logs/agent"], env=env, stdout=log, stderr=subprocess.STDOUT,
                           check=True, timeout=900)
    finally:
        subprocess.run(["docker", "cp", container + ":/logs/agent/.", str(trial)], capture_output=True, check=False)
        subprocess.run(["docker", "rm", "-f", container], capture_output=True, check=False)
        save(trial / "timing.json", {"duration_sec": time.time() - started})
    result = json.loads((trial / "result.json").read_text())
    if result["status"] != "completed":
        raise ValueError(f"Native trial failed: {task_id}")


def run(args):
    root = args.workspace.resolve()
    manifest = json.loads((root / "manifest.json").read_text())
    ids = manifest["sanity_ids"] if args.round == "sanity" else manifest["task_ids"]
    output = root / "runs" / args.round / args.side
    output.mkdir(parents=True)  # Refuse previous attempts.
    save(output / "task-ids.json", ids)
    env = environment(args.env_file)
    if args.side == "original":
        for task_id in ids:
            native_trial(root, output, task_id, manifest, env)
    else:
        if args.side == "oracle":
            agent = {"name": "oracle"}
        elif args.side == "codex":
            agent = {"name": "codex", "model_name": "openai/" + manifest["model"],
                     "base_url": env["API_BASE"], "model_api_key_name": "API_KEY",
                     "kwargs": {"version": "0.118.0", "reasoning_effort": "high", "web_search": "disabled",
                                "config": {"model_provider": "parity_gateway", "web_search": "disabled",
                                           "model_providers": {"parity_gateway": {"name": "Parity Gateway",
                                               "base_url": env["API_BASE"], "env_key": "OPENAI_API_KEY", "wire_api": "responses"}}}}}
        else:
            agent = {"import_path": "harbor_agent:AgentDojoPipelineAgent",
                     "model_name": manifest["model"],
                     "kwargs": {"inputs_dir": str(root / "tasks")},
                     "env": {"API_KEY": "${API_KEY}", "API_BASE": env["API_BASE"]}}
        config = {"job_name": "job", "jobs_dir": str(output), "n_attempts": 1,
                  "orchestrator": {"type": "local", "n_concurrent_trials": 1, "retry": {"max_retries": 0}},
                  "environment": {"type": "docker", "force_build": False, "delete": True},
                  "agents": [agent], "datasets": [{"path": str(root / "tasks"), "task_names": ids}]}
        save(output / "config.json", config)
        with (output / "harbor.log").open("w") as log:
            subprocess.run([str(args.harbor), "run", "-c", str(output / "config.json"), "-y"],
                           env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
        result = json.loads((output / "job/result.json").read_text())
        if result["stats"]["n_errored_trials"] or result["stats"]["n_completed_trials"] != len(ids):
            raise RuntimeError("Incomplete Harbor job; inspect logs before proceeding")
        if args.side == "oracle":
            for f in (output / "job").glob("*/result.json"):
                assert json.loads(f.read_text())["verifier_result"]["rewards"]["utility"] == 1
    save(output / "completed.json", {"status": "completed", "task_count": len(ids)})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--image", required=True)
    prep.add_argument("--ca-bundle", type=Path)
    execute = sub.add_parser("run")
    execute.add_argument("--side", choices=["original", "harbor", "oracle", "codex"], required=True)
    execute.add_argument("--round", choices=["sanity", "1", "2", "3", "generalization"], required=True)
    execute.add_argument("--env-file", type=Path, required=True)
    execute.add_argument("--harbor", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args)
    else:
        run(args)
