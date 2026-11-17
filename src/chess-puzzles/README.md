# Chess Puzzles → Harbor Adapter

## Overview

Converts all 100 Epoch AI Chess Puzzles into Harbor tasks. This WIP implements
the CLI file-answer variant and passes the full local Docker oracle. Custom-agent
implementation and real-model parity are pending.

Source: [epoch-research/chess-puzzles-mirror](https://github.com/epoch-research/chess-puzzles-mirror/tree/2c9416aac2a6b0731a3680eadfff3735fdaad396),
pinned to public benchmark **2.0.1**, commit
`2c9416aac2a6b0731a3680eadfff3735fdaad396`. The CSV is verified with SHA-256
before generation. No puzzles are excluded.

## What is Chess Puzzles?

Each puzzle supplies a FEN position and asks for the single best next move.
The public upstream task uses Inspect's `qa_agent`, whose only tool is
`submit_answer`, and scores accuracy with Inspect `exact()`. Released gold moves
are in the upstream CSV's `target` column.

## Adapter Features

- Standard-library task generation and verifier; no chess engine or GPU needed.
- Stable IDs `chess-puzzles-001` through `chess-puzzles-100` in CSV row order.
- Original question plus a clearly disclosed answer-file handoff.
- Lightweight Inspect 0.3.273 exact normalization, retaining its full MIT notice.
- Oracle writes released gold; targets stay in `tests/` and `solution/`, outside
  the Docker image build context.
- Temporary task staging, overwrite protection and rejection of stale selections.

## Generated Task Structure

```text
datasets/chess-puzzles/
├── chess-puzzles-001/
│   ├── instruction.md
│   ├── task.toml
│   ├── environment/Dockerfile
│   ├── solution/solve.sh
│   └── tests/
│       ├── test.sh
│       ├── grade.py
│       ├── scoring.py
│       └── record.json
├── ...
└── generation_manifest.json
```

Adapter code belongs at `src/chess-puzzles/` in the adapters repository.
Generated datasets, caches and full job logs are ignored and published separately.

## Run Evaluation / Harness

Registry publication is pending; use local paths for this WIP. All commands below
run from the adapter package directory (`src/chess-puzzles/`). Harbor is an external
dependency; `uvx` selects the recorded runtime without changing a global install.

```bash
# Single-task oracle
uvx --from harbor==0.25.0 harbor run -p datasets/chess-puzzles/chess-puzzles-001 -a oracle

# Full 100-task oracle (YAML selects oracle and four concurrent trials)
uvx --from harbor==0.25.0 harbor run -c run_chess-puzzles.yaml
```

No model API key is needed for oracle. Its expected result is 100 trials, zero
exceptions and mean reward 1.000. Results are saved under the printed `jobs/` path.

## Usage: Create Task Directories

```bash
cd src/chess-puzzles
uv sync --locked --no-editable
uv run --locked --no-editable chess-puzzles --output-dir datasets/chess-puzzles
```

`--output-dir` defaults to `datasets/chess-puzzles` relative to the working directory.
Other flags: `--limit`, `--task-ids` (e.g. `7` or `chess-puzzles-007`), `--overwrite`,
`--data-path` for a verified offline CSV, and `--cache-dir`. Use a fresh output
directory when changing the selected task set. Answers are downloaded and inserted
into the oracle scripts during generation, not hardcoded in the source template.

## Comparison with Original Benchmark (Parity)

| Agent | Model | Metric | Number of Runs | Dataset Size | Original (mean ± SEM) | Harbor (mean ± SEM) |
|---|---|---|---|---|---|---|
| Pending | Pending | accuracy | 0 | 100 | Not run | Not run |

`parity_experiment.json` is intentionally empty. The planned Scenario 3 path must
implement the public upstream `qa_agent` in Harbor, including its submission tool,
continuation, compaction and forced-final-answer behavior. This WIP's CLI prompt
and terminal tools do not reproduce those conditions; CLI results must be reported
separately. The original-side reference, from a checkout of the pinned upstream:

```bash
inspect eval bench/task/chess_puzzles --model PROVIDER/MODEL \
  -T max_output_tokens=APPROVED_BUDGET \
  -T compaction_threshold_tokens=APPROVED_THRESHOLD
# Harbor-side matched custom-agent command: pending implementation.
```

Coordinate model, settings, task selection and budget with the Harbor team before
paid runs. Follow the symmetric 5–10-task pilot, full-run and repeated-run sequence.
At least two runs per side (three preferred), sample SEM and overlapping run-score
ranges are required. Oracle success does not establish parity.

## Notes & Caveats

Local oracle on 2026-11-16: **100/100**, **0 exceptions**, **0 retries**, mean
reward **1.000**, approximately **2m47s**, using Harbor 0.25.0 and Docker Desktop
on macOS with the unmodified `python:3.12-slim-bookworm` task image.
See [screenshot](validation/oracle-2026-11-16.png) and
[summary with task checksums](validation/oracle-summary.json).

- The instruction appends `/app/answer.txt` submission and closed-book constraints.
  These tool restrictions are instructional; no engine-access enforcement is claimed.
- Scoring follows 2.0.1 normalized exact matching, not raw UCI equality or 2.1.0
  SAN parsing. Case, punctuation, whitespace and articles follow pinned Inspect.
- The 1,800-second task timeout is an infrastructure limit, not the original
  token budget or continuation policy.
- No upstream LICENSE is present at the selected snapshot. Resolve source/data
  reuse permission before dataset publication. Upstream data is downloaded at
  generation time, not committed in this adapter package.
- No real-model runs, registry publication or completed parity are claimed.
  The full submission validator therefore retains missing-parity findings.

## Installation / Prerequisites

Python 3.13+, uv, and Docker Desktop running. The generator has no third-party
runtime dependencies; development dependencies are recorded in `uv.lock`.
First generation and container-image download require network access. A GPU,
Stockfish and model credentials are unnecessary for oracle.

```bash
# After generation, run all tests using the checksum-verified local cache.
CHESS_PUZZLES_CSV=.cache/chess-puzzles/puzzles-2c9416aac2a6.csv \
  uv run --locked --no-editable pytest -q
```

## Troubleshooting

- `Task exists`: reuse the generated tasks, or regenerate the same set with
  `--overwrite`. Changing the selection requires a fresh directory.
- Missing task path: use the directory printed by generation; do not mix
  `datasets/chess-smoke` with `datasets/chess-puzzles`.
- Docker connection error: start Docker Desktop and check `docker info`.
- Missing answer: valid zero reward with `missing_answer` status. A verifier
  crash instead removes stale reward and exits nonzero; inspect its trial logs.
- Checksum mismatch: restore the pinned CSV, rather than updating the expected hash.
- macOS editable-import issue: retain `--no-editable` in the uv commands.

## Citation

```bibtex
@misc{epochai_chess_puzzles,
  title={Chess Puzzles},
  author={{Epoch AI}},
  url={https://github.com/epoch-research/chess-puzzles-mirror}
}
```

## Authors & Contributions

Yuxuan Tang (tangalantt@gmail.com): adapter contributor.
Original benchmark: Epoch AI. The Inspect-derived scorer retains its MIT notice.
