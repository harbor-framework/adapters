# AgentDojo parity

The fixed subset contains 20 tasks: 10 clean user tasks and 10 attacked pairs,
stratified across the four suites using the adapter's seed-42 hash selection.
Sanity uses one clean and one attacked task from every suite (eight per side).
The formal experiment completed three independent runs per side on 2026-11-26.
A separate Codex 0.118.0 Harbor run on the 20 tasks checks standard-agent
generalization. All 120 formal trials and 20 generalization trials completed
without infrastructure errors. Full results and limitations are in the adapter
README. The [native runner fork](https://github.com/CatherineYin1213/agentdojo/tree/d0b7461b60d359b9be8699650fcac2e5c0c3a204/harbor_parity) and [dataset PR](https://github.com/harbor-framework/harbor-datasets/pull/313) are published. [Official artifact PR #318](https://huggingface.co/datasets/harborframework/parity-experiments/discussions/318) links the complete [sanitized evidence at a pinned revision](https://huggingface.co/datasets/Catherine1213/agentdojo-parity-experiments/tree/b866de430b5e256cce9adcd029c6d264abd2eedf/adapters/agentdojo). The shared repository file-count limit prevents uploading there, so this contributor-owned mirror holds the files. All 24 public files were downloaded and hash-verified; aggregate recomputation matches the recorded results.

Both parity arms use agentdojo 0.1.35, benchmark v1.2.2, the
`important_instructions_no_model_name` attack and `deepseek-v4.1-flash`.
The original arm directly calls `TaskSuite.run_task_with_pipeline`. The Harbor
agent uses the same `AgentPipeline`, `OpenAILLM`, `ToolsExecutor`, three outer
attempts and 15-iteration tool loop, with MCP transporting tool calls to the
isolated environment. Sampling parameters retain the upstream defaults. Both
sides use the same dependency image, one CPU, 2 GB RAM and a 900-second timeout.

Only upstream system/user prompts and suite tools are sent to the parity model.
The Harbor adapter's general MCP instructions remain available to standard
agents; the matching custom agent resolves the corresponding upstream prompt.
The native tool order and JSON schemas are preserved. FastMCP inlines schema
references, so the client checks semantic equivalence and supplies the original
schema to the model. Tool-error metadata preserves upstream error-message
encoding without changing visible tool text.

The trusted Harbor host finalizes the pipeline's last answer and function stack
through a loopback-only sidecar endpoint. This preserves upstream scoring when
the last iteration contains unexecuted calls or the pipeline uses outer retries.
The model cannot access this endpoint. Normal agents continue to use
`submit_answer` and the existing verifier collect hook.

## Reproduction

Use uv, Docker and a separately installed Harbor. The initial preparation used
Harbor 0.27.0 at `cf4bd0043f4e3a91847edf1b799343caf74cf182`.
From the adapter package directory:

```bash
docker build -t agentdojo-parity:0.1.35 parity
uv run --script parity/run.py --workspace /path/to/experiment prepare \
  --image agentdojo-parity:0.1.35
uv run --script parity/run.py --workspace /path/to/experiment run \
  --side oracle --round 1 --env-file /path/to/.env --harbor /path/to/harbor
docker run --rm -v "$PWD/parity:/check:ro" \
  -v /path/to/experiment/tasks:/tasks:ro agentdojo-parity:0.1.35 \
  python /check/check_fidelity.py /tasks
```

The dotenv file contains `API_KEY`; credentials enter subprocess environments,
not command arguments or saved configs. `--ca-bundle` may inject a local TLS
trust bundle into prepared task builds; the common image must also trust it.
Never publish local certificates or credentials.

After the oracle and offline differential check pass, run each side:

```bash
uv run --script parity/run.py --workspace /path/to/experiment run \
  --side original --round sanity --env-file /path/to/.env --harbor /path/to/harbor
uv run --script parity/run.py --workspace /path/to/experiment run \
  --side harbor --round sanity --env-file /path/to/.env --harbor /path/to/harbor
python parity/aggregate.py --workspace /path/to/experiment --rounds sanity
```

Inspect both sides, then repeat with round `1`, inspect again, and run rounds
`2` and `3`. `continue_runs.py` can adopt the two running sanity launcher PIDs
using `--sanity-pids ORIGINAL_PID HARBOR_PID`, with the same `--workspace`,
`--env-file` and `--harbor` arguments. It validates coverage, transport/model
success and identical initial model requests before advancing each stage. It
then runs the separate Codex generalization stage. It never overwrites or
silently retries attempts. Keep failed setup attempts and their explanation.

```bash
python parity/aggregate.py --workspace /path/to/experiment --rounds 1 2 3
```

Report clean utility, utility under attack and targeted ASR separately, with raw
run means and sample SEM. Lower targeted ASR is better. Score disagreement is
reported without selectively rerunning tasks. The offline differential test
freezes dynamic wall-clock fields only while comparing the two transports;
actual experiments retain upstream's live timestamps. Runtime checks and oracle
success are not completed parity evidence. The local result entries have been
checked against the saved trials; publication links identify the submitted PRs and the immutable artifact mirror.
The mirror is published and verified; the official repository upload remains
blocked by its file-count limit, and dataset registry publication is pending.
