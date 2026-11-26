"""Harbor adapter for TraceLite-AI/TwinEnv-Bench (117 counterfactual tasks, 234 twin cells)."""
from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import stat
import sys
import tarfile
from pathlib import Path
from typing import Any


def _quote_toml(val: str) -> str:
    return json.dumps(val, ensure_ascii=False)


def _needs_runtime_setup(setup_text: str) -> bool:
    """Detect setup scripts that require container runtime (mounts, daemons, iptables, pipes, git repos)."""
    if not setup_text:
        return False
    patterns = [
        r"\bmount\b",
        r"\blosetup\b",
        r"\biptables\b",
        r"\bnohup\b",
        r"\bservice\s+",
        r"\bcrond?\b",
        r"\bmkfifo\b",
        r"\bgit\s+(init|clone)\b",
        r"/mnt/othervol",
        r"python3\s+.*&\s*$",
        r"\bsleep\s+",
    ]
    return any(re.search(p, setup_text, re.MULTILINE) for p in patterns)


def _parse_docker_flags(flags: list[str]) -> dict[str, Any]:
    """Parse docker run flags from cell/variant config into docker-compose service fields."""
    svc: dict[str, Any] = {}
    i = 0
    while i < len(flags):
        fl = flags[i]
        if fl == "--privileged":
            svc["privileged"] = True
            i += 1
        elif fl == "--read-only":
            svc["read_only"] = True
            i += 1
        elif fl == "--tmpfs" and i + 1 < len(flags):
            svc.setdefault("tmpfs", []).append(flags[i + 1])
            i += 2
        elif fl == "--cap-drop" and i + 1 < len(flags):
            svc.setdefault("cap_drop", []).append(flags[i + 1])
            i += 2
        elif fl == "--cap-add" and i + 1 < len(flags):
            svc.setdefault("cap_add", []).append(flags[i + 1])
            i += 2
        elif fl == "--security-opt" and i + 1 < len(flags):
            svc.setdefault("security_opt", []).append(flags[i + 1])
            i += 2
        elif fl == "--dns" and i + 1 < len(flags):
            svc.setdefault("dns", []).append(flags[i + 1])
            i += 2
        elif fl == "--network" and i + 1 < len(flags):
            svc["network_mode"] = flags[i + 1]
            i += 2
        elif fl in ("--memory", "--memory-reservation", "--memory-swap", "--cpus", "--pids-limit", "--mount"):
            # Handled by Harbor [environment] or container defaults
            i += 2
        else:
            i += 1
    return svc


def _yaml_dump_compose(svc: dict[str, Any], sidecar: str | None = None) -> str:
    """Emit a clean minimal docker-compose.yaml for Harbor without external PyYAML dependency."""
    lines = ["services:", "  main:", "    build:", "      context: .", "      dockerfile: Dockerfile"]
    if svc.get("privileged"):
        lines.append("    privileged: true")
    if svc.get("read_only"):
        lines.append("    read_only: true")
        lines.append("    volumes:")
        lines.append("      - workspace_vol:/workspace")
        lines.append("      - logs_vol:/logs")
        lines.append("      - solution_vol:/solution")
        lines.append("      - tests_vol:/tests")
        lines.append("      - stage_vol:/opt/stage")
    elif sidecar == "mitm":
        lines.append("    volumes:")
        lines.append("      - mitm_ca:/mitm_ca:ro")
    if svc.get("network_mode"):
        lines.append(f"    network_mode: {json.dumps(svc['network_mode'])}")
    if sidecar in ("proxy", "mitm"):
        lines.append("    networks:")
        lines.append("      - tlsbx_int")
        dep = "tlsbx-proxy" if sidecar == "proxy" else "tlsbx-mitm"
        lines.append("    depends_on:")
        lines.append(f"      {dep}:")
        lines.append("        condition: service_started")
    for key in ("cap_drop", "cap_add", "security_opt", "tmpfs", "dns"):
        vals = svc.get(key)
        if vals:
            lines.append(f"    {key}:")
            for v in vals:
                lines.append(f"      - {json.dumps(v)}")
    if svc.get("ulimits"):
        lines.append("    ulimits:")
        for uname, uval in svc["ulimits"].items():
            lines.append(f"      {uname}:")
            lines.append(f"        soft: {int(uval)}")
            lines.append(f"        hard: {int(uval)}")
    if svc.get("command"):
        lines.append("    command:")
        for c in svc["command"]:
            lines.append(f"      - {json.dumps(c)}")

    if sidecar == "proxy":
        lines.extend([
            "  tlsbx-proxy:",
            "    image: tlsbx:py3.12",
            "    command:",
            '      - "sh"',
            '      - "-c"',
            '      - "printf \'Port 8888\\nListen 0.0.0.0\\nTimeout 600\\nMaxClients 100\\nAllow 0.0.0.0/0\\nConnectPort 443\\nConnectPort 80\\n\' > /tmp/tp.conf && exec tinyproxy -d -c /tmp/tp.conf"',
            "    networks:",
            "      - tlsbx_int",
            "      - egress_net",
        ])
    elif sidecar == "mitm":
        lines.extend([
            "  tlsbx-mitm:",
            "    image: tlsbx-mitm:1",
            "    command:",
            '      - "sh"',
            '      - "-c"',
            '      - "mitmdump -q -s /addon.py --listen-port 8080 --set block_global=false & for i in $(seq 1 60); do [ -f /root/.mitmproxy/mitmproxy-ca-cert.pem ] && cp /root/.mitmproxy/mitmproxy-ca-cert.pem /mitm_ca/tlsbx-mitm.crt && break; sleep 1; done; wait"',
            "    volumes:",
            "      - mitm_ca:/mitm_ca",
            "    networks:",
            "      - tlsbx_int",
            "      - egress_net",
        ])

    if svc.get("read_only"):
        lines.extend([
            "volumes:",
            "  workspace_vol:",
            "  logs_vol:",
            "  solution_vol:",
            "  tests_vol:",
            "  stage_vol:",
        ])
    elif sidecar == "mitm":
        lines.extend(["volumes:", "  mitm_ca:"])

    if sidecar in ("proxy", "mitm"):
        lines.extend([
            "networks:",
            "  tlsbx_int:",
            "    internal: true",
            "  egress_net:",
        ])
    return "\n".join(lines) + "\n"


def load_variant_map(variants_py: Path) -> dict[str, dict[str, Any]]:
    import importlib.util

    spec = importlib.util.spec_from_file_location("twinenv_variants", str(variants_py))
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    vmap = {v["id"]: v for v in mod.VARIANTS}
    vmap["base"] = mod.BASE
    return vmap


class TwinEnvBenchAdapter:
    """Convert TwinEnv-Bench canonical tasks into Harbor tasks (2 cells per task)."""

    def __init__(
        self,
        source_dir: Path,
        output_dir: Path,
        variants_py: Path | None = None,
    ) -> None:
        self.source_dir = Path(source_dir).resolve()
        self.output_dir = Path(output_dir).resolve()
        self.data_dir = self.source_dir / "data" if (self.source_dir / "data").is_dir() else self.source_dir
        self.tasks_jsonl = self.data_dir / "tasks.jsonl"
        tgz = self.data_dir / "tasks.tar.gz"
        if tgz.is_file():
            extracted_root = self.data_dir / "_tasks_tar"
            if not (extracted_root / "tasks").is_dir():
                extracted_root.mkdir(parents=True, exist_ok=True)
                with tarfile.open(tgz, "r:gz") as tf:
                    tf.extractall(extracted_root)
            self.tasks_root = extracted_root / "tasks"
        else:
            self.tasks_root = self.data_dir / "tasks"
        vpy = variants_py or (self.source_dir / "runtime" / "new" / "sandbox" / "variants.py")
        self.vmap = load_variant_map(vpy) if vpy.is_file() else {}
        self.rows = [json.loads(l) for l in self.tasks_jsonl.read_text().splitlines() if l.strip()]

    def list_task_ids(self) -> list[str]:
        return [r["task_id"] for r in self.rows]

    def _harbor_id(self, task_id: str, cell: str) -> str:
        return f"{task_id.lower().replace('.', '-')}-{cell}"

    def _resolve_cell_spec(self, row: dict[str, Any], cell_name: str, task_dir: Path) -> dict[str, Any]:
        cells = json.loads(row["cells_json"])
        cell = dict(cells[cell_name])
        profile = row["runtime_profile"]

        spec: dict[str, Any] = {
            "image": "envbench-base:1",
            "user": cell.get("user", "root"),
            "env": dict(cell.get("env") or {}),
            "docker_flags": list(cell.get("docker") or []),
            "variant_setup": None,
            "umask": cell.get("umask"),
            "rlimits": dict(cell.get("rlimits") or {}),
            "network_mode": cell.get("network"),
            "custom_dockerfile": cell.get("dockerfile"),
            "sandbox_id": cell.get("sandbox"),
            "sidecar_network": None,
            "mitm": False,
        }

        if profile == "host_isolated":
            spec["image"] = "aea-supp-workspace:revised-20261112"
        elif profile == "variant_sandbox":
            sbx_id = cell["sandbox"]
            base_v = self.vmap["base"]
            v = self.vmap[sbx_id]
            spec["image"] = v.get("image", base_v["image"])
            spec["user"] = v.get("user", base_v.get("user", "root"))
            merged_env = dict(base_v.get("env") or {})
            merged_env.update(v.get("env") or {})
            spec["env"] = merged_env
            spec["docker_flags"] = list(v.get("docker") or [])
            spec["variant_setup"] = v.get("setup")
            spec["sidecar_network"] = v.get("network")
            spec["mitm"] = bool(v.get("mitm"))
            if sbx_id == "net-offline":
                spec["network_mode"] = "none"

        return spec

    def generate_cell(self, row: dict[str, Any], cell_name: str) -> Path:
        task_id = row["task_id"]
        task_dir = self.tasks_root / task_id
        task_meta = json.loads((task_dir / "task.json").read_text())
        harbor_id = self._harbor_id(task_id, cell_name)
        out_task = self.output_dir / harbor_id
        if out_task.exists():
            shutil.rmtree(out_task)
        env_dir = out_task / "environment"
        sol_dir = out_task / "solution"
        tst_dir = out_task / "tests"
        env_dir.mkdir(parents=True)
        sol_dir.mkdir(parents=True)
        tst_dir.mkdir(parents=True)

        spec = self._resolve_cell_spec(row, cell_name, task_dir)

        # 1. instruction.md
        (out_task / "instruction.md").write_text(row["prompt"].strip() + "\n", encoding="utf-8")

        # 2. environment/workspace
        ws_src = task_dir / "workspace"
        if ws_src.is_dir():
            shutil.copytree(ws_src, env_dir / "workspace", symlinks=True)
        else:
            (env_dir / "workspace").mkdir()

        # Check setup.sh & setup_files
        setup_sh = task_dir / "setup.sh"
        setup_text = setup_sh.read_text() if setup_sh.is_file() else ""
        variant_setup = spec["variant_setup"] or ""
        setup_files_src = task_dir / "setup_files"

        task_setup_runtime = _needs_runtime_setup(setup_text)
        variant_setup_runtime = _needs_runtime_setup(variant_setup)
        sidecar = None
        if spec["sandbox_id"] == "net-proxy":
            sidecar = "proxy"
        elif spec["sandbox_id"] == "net-http-readonly":
            sidecar = "mitm"
        need_init_script = task_setup_runtime or variant_setup_runtime or (sidecar == "mitm")

        if setup_files_src.is_dir():
            shutil.copytree(setup_files_src, env_dir / "setup_files", symlinks=True)
        if setup_sh.is_file():
            shutil.copy2(setup_sh, env_dir / "setup.sh")

        # Handle custom dockerfile (1 task in base_container)
        base_image = spec["image"]
        if spec["custom_dockerfile"]:
            custom_df_dir = task_dir / spec["custom_dockerfile"]
            if custom_df_dir.is_dir():
                for item in custom_df_dir.iterdir():
                    dst = env_dir / item.name
                    if item.is_dir():
                        shutil.copytree(item, dst, symlinks=True, dirs_exist_ok=True)
                    else:
                        shutil.copy2(item, dst)
                df_lines = (env_dir / "Dockerfile").read_text().splitlines()
            else:
                df_lines = [f"FROM {base_image}"]
        else:
            df_lines = [f"FROM {base_image}"]

        df_lines.append("WORKDIR /workspace")
        df_lines.append("RUN mkdir -p /workspace /opt/stage /solution /tests /logs/agent /logs/verifier")
        df_lines.append("COPY workspace/ /workspace/")

        # ENV vars (preserve empty string values like TZ="")
        for k, v in spec["env"].items():
            df_lines.append(f"ENV {k}={json.dumps(str(v))}")

        # Build-time setup (runs while build network is open)
        if not task_setup_runtime and setup_files_src.is_dir():
            df_lines.append("COPY setup_files/ /opt/stage/setup_files/")
        if variant_setup and not variant_setup_runtime:
            df_lines.append(f"RUN bash -c {json.dumps(variant_setup)}")
        if setup_sh.is_file() and not task_setup_runtime:
            df_lines.append("COPY setup.sh /opt/stage/setup.sh")
            df_lines.append(f"RUN CELL={cell_name} bash /opt/stage/setup.sh")
        if not task_setup_runtime:
            df_lines.append("RUN rm -rf /opt/stage/* /opt/stage/.[!.]* 2>/dev/null || true")

        if not need_init_script:
            if spec["user"] != "root":
                df_lines.append(f"RUN chown -R {spec['user']} /workspace")
        else:
            # Stage runtime init script to /opt/twinenv_init.sh, executed at container start then self-cleaned
            if task_setup_runtime:
                if setup_files_src.is_dir():
                    df_lines.append("COPY setup_files/ /opt/stage/setup_files/")
                if setup_sh.is_file():
                    df_lines.append("COPY setup.sh /opt/stage/setup.sh")
            init_parts = ["#!/usr/bin/env bash", "set -e"]
            if task_setup_runtime and setup_sh.is_file():
                init_parts.append(f"CELL={cell_name} bash /opt/stage/setup.sh")
            if spec["user"] != "root":
                init_parts.append(f"chown -R {spec['user']} /workspace")
            if variant_setup_runtime and variant_setup:
                init_parts.append(variant_setup)
            if sidecar == "mitm":
                init_parts.append(
                    "for i in $(seq 1 60); do [ -f /mitm_ca/tlsbx-mitm.crt ] && cp /mitm_ca/tlsbx-mitm.crt /usr/local/share/ca-certificates/tlsbx-mitm.crt && update-ca-certificates >/dev/null 2>&1 && break; sleep 1; done"
                )
            init_parts.append("rm -rf /opt/stage/* /opt/stage/.[!.]* /opt/twinenv_init.sh 2>/dev/null || true")
            init_parts.append("exec /bin/sleep infinity")
            init_path = env_dir / "twinenv_init.sh"
            init_path.write_text("\n".join(init_parts) + "\n", encoding="utf-8")
            init_path.chmod(0o755)
            df_lines.append("COPY twinenv_init.sh /opt/twinenv_init.sh")
            df_lines.append("RUN chmod +x /opt/twinenv_init.sh")

        if spec["umask"]:
            mask = str(spec["umask"])
            df_lines.append(
                f"RUN echo 'umask {mask}' >> /etc/profile && echo 'umask {mask}' >> /etc/bash.bashrc"
            )

        (env_dir / "Dockerfile").write_text("\n".join(df_lines) + "\n", encoding="utf-8")

        # 3. environment/docker-compose.yaml if needed
        svc = _parse_docker_flags(spec["docker_flags"])
        if spec["network_mode"] == "none":
            svc["network_mode"] = "none"
        if spec["sandbox_id"] in ("tc-toybox", "tc-busybox") and not need_init_script:
            # toybox sleep does not accept "infinity"; use GNU /bin/sleep
            svc["command"] = ["/bin/sleep", "infinity"]
        if need_init_script:
            svc["command"] = ["/opt/twinenv_init.sh"]

        if svc or sidecar:
            (env_dir / "docker-compose.yaml").write_text(_yaml_dump_compose(svc, sidecar=sidecar), encoding="utf-8")

        # 4. solution/solve.sh (oracle = ref.sh)
        ref_src = task_dir / "solution" / "ref.sh"
        shutil.copy2(ref_src, sol_dir / "ref.sh")
        (sol_dir / "ref.sh").chmod(0o755)
        sol_lines = ["#!/usr/bin/env bash", "set -euo pipefail", "cd /workspace"]
        if spec["umask"]:
            sol_lines.append(f"umask {spec['umask']}")
        if spec["rlimits"]:
            pr_args = " ".join(f"--{k}={int(v)}:{int(v)}" for k, v in spec["rlimits"].items())
            sol_lines.append(f"prlimit {pr_args} -- bash /solution/ref.sh")
        else:
            sol_lines.append("bash /solution/ref.sh")
        solve_sh = sol_dir / "solve.sh"
        solve_sh.write_text("\n".join(sol_lines) + "\n", encoding="utf-8")
        solve_sh.chmod(0o755)

        # 5. tests/test.sh (host-isolated post-termination verifier)
        shutil.copy2(task_dir / "verify.sh", tst_dir / "verify.sh")
        (tst_dir / "verify.sh").chmod(0o755)
        if (task_dir / "judge").is_dir():
            shutil.copytree(task_dir / "judge", tst_dir / "judge", symlinks=True)
        if setup_files_src.is_dir():
            shutil.copytree(setup_files_src, tst_dir / "setup_files", symlinks=True)

        verify_user = task_meta.get("verify_user", "root")
        test_lines = [
            "#!/usr/bin/env bash",
            "set -uo pipefail",
            "mkdir -p /opt/stage /logs/verifier",
            "if [ -d /tests/judge ]; then rm -rf /opt/stage/judge && cp -r /tests/judge /opt/stage/judge; fi",
            "if [ -d /tests/setup_files ]; then rm -rf /opt/stage/setup_files && cp -r /tests/setup_files /opt/stage/setup_files; fi",
            "cd /workspace",
        ]
        if verify_user != "root":
            test_lines.append(
                f"su -s /bin/bash {shlex.quote(verify_user)} -c 'cd /workspace && CELL={cell_name} bash /tests/verify.sh'"
            )
        else:
            test_lines.append(f"CELL={cell_name} bash /tests/verify.sh")
        test_lines.extend([
            "RC=$?",
            "if [ \"$RC\" -eq 0 ]; then",
            "  echo 1 > /logs/verifier/reward.txt",
            "else",
            "  echo 0 > /logs/verifier/reward.txt",
            "fi",
            "exit 0",
        ])
        test_sh = tst_dir / "test.sh"
        test_sh.write_text("\n".join(test_lines) + "\n", encoding="utf-8")
        test_sh.chmod(0o755)

        # 6. task.toml
        keywords = [
            "twinenv-bench",
            "environment-adaptation",
            row["canonical_layer"].lower(),
            row["canonical_group"].lower(),
            row["exposure_regime"],
            cell_name,
        ]
        timeout_sec = int(row.get("timeout_sec") or 1200)
        agent_net_line = 'network_mode = "no-network"\n' if spec["network_mode"] == "none" else ""
        agent_user_line = f'user = {_quote_toml(spec["user"])}\n' if spec["user"] != "root" else ""

        task_toml = f'''schema_version = "1.0"

[task]
name = "tracelite-ai/twinenv-bench__{harbor_id}"
authors = [
  {{ name = "TraceLite AI", email = "contact@tracelite.ai" }},
]
keywords = {json.dumps(keywords)}

[metadata]
source = "TraceLite-AI/TwinEnv-Bench"
pair_id = {_quote_toml(task_id)}
cell = {_quote_toml(cell_name)}
canonical_layer = {_quote_toml(row["canonical_layer"])}
canonical_group = {_quote_toml(row["canonical_group"])}
canonical_dimension = {_quote_toml(row["canonical_dimension"])}
exposure_regime = {_quote_toml(row["exposure_regime"])}
runtime_profile = {_quote_toml(row["runtime_profile"])}

[verifier]
timeout_sec = {int(task_meta.get("verify_timeout", 300))}

[agent]
timeout_sec = {timeout_sec}
{agent_net_line}{agent_user_line}
[environment]
build_timeout_sec = 600
cpus = 2
memory_mb = 4096
storage_mb = 10240
gpus = 0
'''
        (out_task / "task.toml").write_text(task_toml, encoding="utf-8")
        return out_task

    def generate(
        self,
        task_ids: list[str] | None = None,
        cells: tuple[str, ...] = ("base", "target"),
    ) -> list[Path]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        selected = set(task_ids) if task_ids else None
        generated: list[Path] = []
        for row in self.rows:
            if selected and row["task_id"] not in selected:
                continue
            for cell in cells:
                generated.append(self.generate_cell(row, cell))
        return generated
