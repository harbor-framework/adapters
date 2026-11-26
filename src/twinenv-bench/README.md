# TwinEnv-Bench Harbor Adapter

Harbor adapter for [**TraceLite-AI/TwinEnv-Bench**](https://huggingface.co/datasets/TraceLite-AI/TwinEnv-Bench) (117 counterfactual OS environment adaptation tasks × 2 paired cells `base` / `target` = **234 Harbor tasks**).

## Quick Start

```bash
# 1. Build the 6 base sandbox images (+ optional tlsbx-mitm:1 for E4.2 read-only MITM tasks)
bash build_images.sh

# 2. Generate all 234 Harbor tasks and dataset.toml
PYTHONPATH=src python3 -m twinenv_bench.main \
  --source-dir /path/to/TwinEnv-Bench \
  --output-dir ./harbor-twinenv-bench

# 3. Lint and verify with Harbor
harbor lint harbor-twinenv-bench/e*-*
harbor run -p harbor-twinenv-bench -a nop -n 8
harbor run -p harbor-twinenv-bench -a oracle -n 8
```

## Verification Summary (Harbor v0.26.0)
- **Lint**: **234 / 234** tasks pass `harbor lint` with 0 schema errors.
- **4-Profile Smoke Test (`nop` / `oracle`)**: **8 / 8** `nop` = `0.0`, **8 / 8** `oracle` = `1.0`.
- **Full 234-Cell Oracle Verification**: **234 / 234 (100.0%, 0 exceptions)** pass across all 5 OS layers (`E1–E5`), 4 runtime profiles (`base_container`, `variant_sandbox`, `host_scheduled`, `host_isolated`), and Docker Compose sidecars (`tlsbx-proxy`, `tlsbx-mitm`, `iptables`, `read_only` volumes, `cap_drop: ALL`, `prlimit`, `fs-casefold`).
