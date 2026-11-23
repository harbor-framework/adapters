# Proposed GSM8K parity run

Both sides use one independent Chat Completions request with identical settings, no system message and no tools. The user message contains the pinned question followed by the shared completion-format instruction. The Harbor agent removes the task's file-writing wrapper before making that request. The original runner applies OpenAI's pinned scorer to the full completion. The Harbor agent preserves its own completion, extracts the first answer with the pinned extractor, and puts it in `/app/output/answer.txt` for the independent verifier. Record the shared prompt and transport in the experiment notes. The original repository's example checkpoint sampler supports a calculator, so this proposed comparison requires agreement on the shared no-tools protocol.

The eight-task sanity cohort is committed in `parity-smoke-ids.txt`. The proposed scored cohort is the full official test split, 1,319 tasks. Execute both sanity runs, one complete pair, then two additional complete pairs. Keep source rows, model revision, sampling, budget, and tooling fixed. Use a unique output directory and job name for each repetition.

From the adapters repository root, prepare the exact inputs.

```bash
mkdir -p runs/gsm8k-parity
revision=3101c7d5072418e28b9008a6636bde82a006892c
upstream="https://raw.githubusercontent.com/openai/grade-school-math/$revision/grade_school_math"
curl -fsS "$upstream/data/test.jsonl" -o runs/gsm8k-parity/test.jsonl
curl -fsS "$upstream/dataset.py" -o runs/gsm8k-parity/dataset.py
ids="$(paste -sd, src/gsm8k/parity-smoke-ids.txt)"
uv run --project src/gsm8k --locked gsm8k --split parity \
  --source runs/gsm8k-parity/test.jsonl --task-ids "$ids" \
  --output-dir datasets/gsm8k-parity-smoke
```

Create `runs/gsm8k-parity/profile.json` with the approved `model`, `temperature`, `max_completion_tokens` and `timeout_seconds`. Allow time for the answer write within the task's 60-second agent deadline. Provide `GSM8K_PARITY_BASE_URL` ending at the Chat Completions API prefix and `GSM8K_PARITY_API_KEY` in the host environment. Keep both sides on the same endpoint. The runner checks the returned model revision and records the raw completion, request SHA-256, finish reason and available usage. Credentials stay in the environment.

```bash
uv run --project src/gsm8k --locked python -m gsm8k.parity \
  --source runs/gsm8k-parity/test.jsonl --scorer runs/gsm8k-parity/dataset.py \
  --profile runs/gsm8k-parity/profile.json --task-ids "$ids" \
  --output runs/gsm8k-parity/original-sanity.jsonl
uv run --project src/gsm8k --locked harbor run -c src/gsm8k/parity-config.example.yaml
```

For the full test cohort, generate with `--split test` and omit `--task-ids` from the original runner. Point the Harbor config at the complete test directory. Compare prompt hashes and match source rows before scoring. Calculate each run from the full cohort. Keep model errors and verifier errors separately from scored responses. Compute mean ± sample SEM and compare the two raw score ranges. Fill in the official parity JSON and README table after scores and real PR URLs exist.
