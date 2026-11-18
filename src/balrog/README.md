# BALROG Adapter

## Overview

This adapter generates **255 fixed text-only episodes across all six BALROG environments**, covering the 58 task types in the pinned upstream configuration. Task families, seeds and native action budgets are fixed before evaluation. This is a reproducible selection of upstream episodes, not an official fixed upstream test set.

This is a WIP submission for feedback on the implementation and three unresolved benchmark issues. Model parity has not run, provider credentials have not been provisioned for these experiments, and `parity_experiment.json` is intentionally `[]`. The baseline has 239 full-score oracles and 16 diagnostic references. NetHack scoring, a MiniHack Boxoban action budget and Crafter replay nondeterminism need maintainer review; reference-policy work also remains. This does not satisfy the guide's complete-oracle milestone or establish Ready for Review status.

## What is BALROG?

[BALROG](https://github.com/balrog-ai/BALROG) evaluates language and vision-language agents through interactive games. This adapter preserves the text observations, native instructions, action handling, stopping rules and progression metric of its pinned text-only configuration.

| Environment | Task types | Fixed seeds per type | Episodes | Native action budget |
|-------------|------------|----------------------|----------|----------------------|
| BabyAI | 5 | 0–9 | 50 | 64 or 128 |
| Baba Is AI | 40 | 0–2 | 120 | 100 |
| TextWorld | 3 | 0–9 | 30 | 80 |
| Crafter | 1 | 0–9 | 10 | 2,000 |
| NetHack / NLE | 1 | 0–4 | 5 | 100,000; native no-progress timeout 150 |
| MiniHack | 8 | 0–4 | 40 | 100 |
| Total | 58 | Predetermined | 255 | Environment-specific |

Each environment retains its original progression metric. Crafter and NetHack award fractional progress; TextWorld can also award partial progress at its native limit. Raw step rewards are recorded separately and never replace progression. BALROG's overall metric gives each of the six environment means weight `1/6`. A flat mean across 255 Harbor trials is not that overall metric.

The source pins are BALROG `b7afe79e3e4265811cfa985ed7c95c4d1a11e3f5`, Minigrid `cf73dd148e51276bd675a37e3bfb0bf2b42329b2`, Baba Is AI `40ae1b29dbc67f2ecea06cc161ed5ca51719e5e3`, TextWorld `1d56f4765e7b28f04a68eff0bce5a6fe6ecd1a9f`, MiniHack `3ecb6da4eadcac7a4dbc5f8e801ccf636e34d7ec`, and the additional asset revisions recorded in `src/balrog/fixtures/runtime_sources.json`. `suite_scope.json` fixes the original task families, source revisions and budgets. The per-environment manifests record every selected episode and reference status; BabyAI retains the filename `manifest.json`.

BabyAI covers `goto`, `pickup`, `open`, `putnext` and `pick_up_seq_go_to` under `BabyAI-MixedTrainLocal-v0/`, with the original `num_dists: 0`. Upstream normally samples fresh seeds. The frozen seeds here allow native and Harbor runs to encounter identical instances; other seeds and image/VLM evaluation are outside this adaptation.

## Adapter Features

- Stable names such as `balrog/babyai-goto-seed-0` and `balrog/babaisai-two-room-make-wall-win-seed-2`. Episode manifests freeze initial-observation hashes and budgets, plus missions where the environment provides them.
- A separate game service owns the simulator, assets and action history. Agents use `balrog observe` and `balrog act "ACTION"`; reading observations does not advance the game. There is no public reset or scoring endpoint.
- Oracle and diagnostic trajectories use the same public action endpoint. `solution/reference_status.json` distinguishes complete oracles from partial or zero-score diagnostics. A Harbor run using the `oracle` agent does not itself establish a full-score oracle.
- The verifier authenticates to the service, finalizes the episode and attempts independent replay in a fresh native environment. It writes native progression to `/logs/verifier/reward.txt`. Replay must match for five environments. Crafter's original simulator can diverge despite identical seeds and actions; only that known divergence permits the isolated live game's score, explicitly marked `replay_verified: false` and `scoring_mode: authoritative_native_state`, with a divergence diagnostic. Network, schema, simulator and initial-state failures still produce no reward file.
- Source archives and asset hashes are checked before generation. The agent's running filesystem exposes the upstream agent/prompt/client code and public configuration. Private episode data, game state, level assets and solutions are not copied into the agent container. There is no shared game filesystem or mounted Docker socket.

The `balrog-native` Harbor bridge reuses the upstream `AgentFactory`, `naive` agent, prompt builder and API client. The original-side runner invokes the unmodified upstream `Evaluator.run_episode`; the Harbor side obtains the same native instructions and observations over HTTP. Harbor shell instructions are not added to model prompts. The bridge obtains the full task ID from the game service, so truncated Harbor trial directory names cannot alter episode identity. Raw model prompts, completions, token usage and trajectory artifacts are retained. Only the `naive` text-only agent has been validated by the offline integration tests; CoT and robust variants are rejected.

## Generated Task Structure

```text
balrog-six-games/
├── babyai-goto-seed-0/
│   ├── task.toml
│   ├── instruction.md
│   ├── environment/
│   │   ├── Dockerfile
│   │   ├── Dockerfile.game
│   │   ├── docker-compose.yaml
│   │   ├── episode.json
│   │   ├── game_server.py
│   │   ├── play.py
│   │   ├── requirements-agent.lock
│   │   └── vendor/                 # Required pinned source/asset archives
│   ├── solution/
│   │   ├── solve.sh
│   │   ├── replay_oracle.py
│   │   ├── oracle_actions.json     # May contain a diagnostic reference
│   │   └── reference_status.json
│   └── tests/
│       ├── test.sh
│       └── verifier.py
├── babaisai-two-room-make-wall-win-seed-0/
├── textworld-treasure-hunter-seed-0/
└── ... 252 other fixed episodes
```

Each environment receives its own game Dockerfile and required archives. TextWorld also receives `requirements-game.lock`. Generation creates a fresh verifier token for each task; frozen episodes, IDs and source archives remain stable. This local verification token is unrelated to model-provider credentials. The legacy BabyAI-only generation path omits `reference_status.json` because its 50 references are all complete oracles.

## Run Evaluation / Harness

Registry execution is unavailable: no adaptation has been published to the registry. After local generation, run from the adapters repository root:

```bash
# One environment's complete reference run.
harbor run -p datasets/balrog-textworld -a oracle --ek auto_mounting=false -o jobs --job-name textworld-reference -n 2
uv run --project src/balrog python src/balrog/scripts/check_suite_reference.py --dataset datasets/balrog-textworld --job jobs/textworld-reference --output jobs/textworld-reference-check.json

# All six environments, including partial/zero-score diagnostic references.
harbor run -c src/balrog/run_balrog.yaml

# Independent no-interaction control for the original BabyAI smoke episode.
harbor run -p datasets/balrog-babyai/babyai-goto-seed-0 -a nop --ek auto_mounting=false -o jobs --job-name babyai-nop -n 1
```

Use fresh job names for every attempt. `check_suite_reference.py` checks exact task coverage, job/trial completion and identity, exceptions, reward validity, agreement between Harbor rewards, reward files and native progression, and independent replay. If frozen native transitions are present, their entire sequence must match. Diagnostics without those transitions are explicitly labeled as server replay plus native final-score checks. Fractional scores remain fractional; partial references are not counted as full oracles. For cross-host audits of Harbor 0.26 job timestamps, use `--naive-utc-offset=-08:00` with the original job host's actual offset when its timestamps lack a timezone.

Completed local reference validation:

| Environment | Native/reference evidence | Complete Harbor reference evidence |
|-------------|---------------------------|------------------------------------|
| BabyAI | 50/50 expert trajectories; fresh replay matched | 50/50 reward 1, zero exceptions; all 411 native transitions matched |
| Baba Is AI | 120/120 search oracles; two fresh Linux native replays per case matched | 120/120 reward 1, zero exceptions; all 1,522 transitions passed strict full-scope checks |
| TextWorld | 30/30 validated native walkthroughs | 30/30 reward 1, zero exceptions; strict full-scope reference checks passed |
| Crafter | All 10 diagnostic traces score `2/22` | 10/10 completed at `2/22`; zero full-score oracles |
| NetHack / NLE | Five fixed diagnostic cases; no full-score oracle | 5/5 completed, zero exceptions; seed 1 scores `0.0153922691`, the other four score 0 |
| MiniHack | 39 full oracles; Hard Boxoban seed 0 is a 100-action diagnostic | Corrected 40/40 cases completed, zero exceptions; 39 reward 1, one reward 0; mean `0.975` |
| Model parity | Not run | Not run |

Across the complete per-environment reference jobs, **255/255 tasks completed with zero infrastructure errors: 239 full-score oracles and 16 diagnostic references**. The diagnostics are ten Crafter, five NetHack and one MiniHack task. These counts do not represent model accuracy or completed parity.

A separate, unapproved MiniHack budget proposal also completed a real Harbor run: **40/40 reward 1**, with all 1,531 native transitions and independent replays checked. It changes the ten Boxoban budgets to 200 while retaining 100 for the other 30 cases. The original fixtures remain unchanged, so this adds **zero** oracles to the 239 above. Adoption requires an agreed upstream correction and matching settings on both parity sides; see [`docs/minihack_seed_and_budget_review.md`](docs/minihack_seed_and_budget_review.md).

A separate Crafter reference prototype attained native and Harbor reward 1 on seed 6 in 725 actions. It uses a custom trusted-host controller with private read-only state, and fresh replay still diverges. This is one research success, not the standard oracle workflow or reliable ten-seed coverage; it also adds zero to the baseline count. See [`docs/crafter_scoring_review.md`](docs/crafter_scoring_review.md).

The committed [validation index](validation/README.md) links the [255-case baseline summary](validation/baseline.json), [saved validator reports](validation/validator_reports.json), and [source/runtime provenance](validation/provenance.json). These are summaries of saved local artifacts, not fresh reviewer reproduction. Full raw Harbor jobs, local research controllers and game assets are not included or uploaded. The [MiniHack proposal](validation/proposals/minihack_200.json) and [private Crafter seed-6 diagnostic](validation/diagnostics/crafter_private_seed6.json) are recorded separately and do not increase baseline oracle coverage.

The separate long Crafter Harbor diagnostic also completed without errors: 180 actions, native reward `2/22`, and the actual protected scoring path reported `replay_verified: false`, `scoring_mode: authoritative_native_state`, with first divergence at step 152. The [scoring review](docs/crafter_scoring_review.md) explains this disclosed replay policy. It is not a full-score oracle or an extra task in the 255-case scope.

The earlier BabyAI-only validation used Harbor 0.26.0 with Linux Docker. Its separate seed-0 oracle scored 1 in three actions; a fresh no-op control scored 0 with no actions. `scripts/check_oracle.py --job JOB --split full` remains the strict checker for that 50-episode scope. Oracle agreement is not model parity.

All five additional environments have a passing zero-action Harbor control. The first combined job produced four zero scores and exposed MiniHack's missing initial `get_stats()` field. The adapter now reads the actual native `BaseProgress` initial value without taking an extra action; a separate retry completed with reward 0 and zero exceptions. The failed attempt remains in the local attempt history rather than being relabeled as a passing run. All 40 MiniHack initial states also passed native zero-action/replay checks. These controls are separate from the 255 reference episodes; see the [initial-score explanation](docs/minihack_seed_and_budget_review.md#native-initial-score-serialization).

An independent reset-order audit passed all 210 fixed cases in BabyAI, Baba Is AI, TextWorld and Crafter. It used the original evaluator's `make_env → seed → reset` order from two distinct constructor RNG states, then checked initial hashes, all 3,133 reference transitions, native progression and fresh service replay. Crafter's references are short partial traces; this does not establish deterministic long-trajectory replay. NetHack and MiniHack are outside that 210-case audit.

Offline generator, artifact and statistics tests use fixtures and synthetic artifacts:

```bash
uv run --project src/balrog python -m unittest discover -s src/balrog/tests -v
```

Runtime tests use Python 3.10 for upstream games and a separate Python 3.12 Harbor environment for the bridge and ATIF validation; see `tests/runtime/README.txt`. Those tests use fake model clients. On Docker Desktop for Windows, `auto_mounting=false` lets the pre-agent healthcheck enforce root-owned verifier output permissions, and Harbor retrieves logs after verification. Set `$env:PYTHONUTF8 = "1"` in PowerShell.

Current offline checks passed 53 unit tests with one Windows symlink-creation skip (54 total), plus 44 runtime tests across six groups. These include six Crafter failure-policy tests, eight suite-verification tests and the fake-client agent comparison. Wheel/sdist builds and six project-CLI generation checks also passed; those packaging checks do not rerun Docker gameplay. See the [submission checks](validation/submission_checks.json) for counts and the [validation index](validation/README.md) for the evidence scope. No paid model API was called.

## Usage: Create Task Directories

The following commands assume sibling `BALROG`, `minigrid-source` and `harbor-index-adapters` checkouts. From `harbor-index-adapters/src/balrog`, prepare the additional pinned archives and generate all cases:

```bash
uv sync
uv run python scripts/prepare_babaisai_sources.py --assets-dir ../../../benchmark-assets
uv run python scripts/prepare_textworld_sources.py --assets-dir ../../../benchmark-assets
uv run python scripts/prepare_nle_sources.py --output-dir ../../../benchmark-assets
uv run balrog --environments all --split full --output-dir ../../datasets/balrog-six-games --benchmark-source ../../../BALROG --minigrid-source ../../../minigrid-source --assets-dir ../../../benchmark-assets
```

Initial source preparation needs Git and network access; none of these commands calls a model. Use `--environments babyai`, `babaisai`, `textworld`, `crafter`, `nle`, or `minihack` to generate individual environments. Omitting the flag retains the BabyAI default. Do not drop unsuccessful or unresolved references from a generated split.

| Split | Selection within the requested environments |
|-------|---------------------------------------------|
| `full` | All predetermined cases; 255 with `--environments all` |
| `parity` | The same complete frozen cases; selection does not imply parity was run |
| `sanity` | Seed 0 for every task family; 58 with `--environments all` |

`--task-ids` selects within the split; `--limit` then takes the first N selected cases in manifest order. `--limit 0` generates nothing. Existing task directories require `--overwrite`; all destinations are preflighted and output paths through symlinks or junctions are rejected. Generation archives the pinned Git commits rather than working-tree changes and checks additional source/asset SHA256 values before writing tasks.

For example, generate a separate TextWorld dataset for the reference command above, or the BabyAI sanity split:

```bash
uv run balrog --environments textworld --output-dir ../../datasets/balrog-textworld --benchmark-source ../../../BALROG --assets-dir ../../../benchmark-assets
uv run balrog --environments babyai --split sanity --output-dir ../../datasets/balrog-babyai-sanity --benchmark-source ../../../BALROG --minigrid-source ../../../minigrid-source
```

An interpreter containing Harbor 0.26.0 can prepare an unpublished `dataset.toml` from the adapters repository root:

```bash
HARBOR_PYTHON src/balrog/scripts/write_dataset_manifest.py --dataset datasets/balrog-six-games --environments all --name balrog/six-games
```

Replace `HARBOR_PYTHON` with that interpreter's executable path. The script checks exact split coverage and task names, then computes Harbor task digests. This does not publish or register the dataset. Regenerate the manifest after changing generated tasks.

## Comparison with Original Benchmark (Parity)

**No live model parity has been run.** `parity_experiment.json` remains `[]`; metadata records zero parity tasks, zero registry tasks and `$0` parity cost. No API key is required for the generation and reference validation above.

| Agent | Model | Metric | Runs | Dataset Size | Original (mean ± SEM) | Harbor (mean ± SEM) |
|-------|-------|--------|------|--------------|-----------------------|---------------------|
| Not run | Not confirmed | Native progression; equal environment weights overall | 0 | 0 | N/A | N/A |

The six-environment proposal is recorded in [`parity/plan.proposed.json`](parity/plan.proposed.json) and remains **PROPOSED_NOT_APPROVED_NOT_RUN**. The primary comparison uses upstream `naive` on both sides with proposed model `gpt-4o-mini-2024-07-18` through 2077ai; that model's provider availability is unconfirmed. It proposes paired sanity checks, one complete run on each side, then two additional paired runs: `255 × 3 × 2 = 1,530` formal episodes plus `58 × 2 = 116` sanity episodes, totaling 1,646. Task seeds are episodes within a run, not independent full benchmark runs. Exact settings, credentials, cost limits and the run plan still require confirmation. Daytona has not been validated; the tested platform is Docker Compose. The standard CLI-agent evaluation required by the guide's custom-agent scenario is also pending implementation and execution; its agent, model and scope are not included in those 1,646 episodes.

The shared public settings template is [`parity/settings.example.json`](parity/settings.example.json). Its exact model ID is a deliberate placeholder. The proposed settings are not approval to run them. Before live experiments, freeze the same supported agent, model ID, decoding parameters, provider endpoint and history settings on both sides. Set model-call limits per environment so they do not truncate native budgets; the original 128-call BabyAI example is insufficient for Crafter or NetHack. Provider credentials belong in the process environment or ignored `.env.local`, never public settings or artifacts.

From the adapters repository root, these commands only inspect a planned BabyAI sanity selection; the other five environments use `--environment NAME`, their own generated dataset and environment directory:

```bash
uv run --project src/balrog python src/balrog/scripts/run_native.py --environment babyai --environment-dir datasets/balrog-babyai/babyai-goto-seed-0/environment --settings src/balrog/parity/settings.example.json --output-dir parity-runs/babyai/native-sanity --split sanity --dry-run
uv run --project src/balrog python src/balrog/scripts/run_harbor.py --environment babyai --dataset datasets/balrog-babyai-sanity --settings src/balrog/parity/settings.example.json --jobs-dir parity-runs/babyai/harbor --job-name sanity --split sanity --dry-run
```

`--dry-run` neither builds containers nor calls a model. After an agreed plan and credentials are available, use the confirmed settings file, remove `--dry-run`, and give the Harbor launcher `--harbor-python HARBOR_PYTHON`. Run the same sanity selection on both sides before full runs. Use fresh output/job names; failures and previous attempts must remain visible. The launchers preserve native budgets, reject reused output locations and require exact dataset coverage.

For each environment, analyze at least two complete paired runs with its corresponding manifest. This BabyAI example uses three pairs:

```bash
uv run --project src/balrog python src/balrog/scripts/analyze_parity.py --manifest src/balrog/src/balrog/fixtures/manifest.json --split parity --pair parity-runs/babyai/native-1 parity-runs/babyai/harbor/full-1 --pair parity-runs/babyai/native-2 parity-runs/babyai/harbor/full-2 --pair parity-runs/babyai/native-3 parity-runs/babyai/harbor/full-3 --output parity-runs/babyai/analysis.json
```

The analyzer checks complete runs, raw model logs, initial prompt agreement, settings/source/SDK provenance, trusted scores and native batch completion. It reports mean progression and **sample SEM across full runs**, plus run-score range overlap. Fractional progression is never binarized. Then pass one analysis per environment to `scripts/analyze_suite_parity.py` using six `--analysis PATH` arguments. It requires each packaged full manifest's exact IDs and SHA256, matching runner code and model SDK versions, then computes each suite run's equal-weight mean across the six environments before calculating the across-run SEM. Preserve the same run-index pairing across all six analyses.

These scripts produce local analysis artifacts, not formal approval. An original-benchmark parity fork, dataset publication and Hugging Face parity-artifact upload remain pending. Formal `parity_experiment.json` entries and publication links will be added only after real experiments and the corresponding submissions exist.

## Notes & Caveats

- Full-score oracle gaps remain visible. Crafter's ten current references score `2/22`. NetHack's pinned `Progress.update` checks only `Xp:*` and `Dlvl:*` achievement entries; the largest value reachable through those lookups is approximately `0.8067964442444019`, and the ascension entry with value 1 is not used. The adapter preserves this scorer without rescaling or synthetic wins. See [`docs/nle_scoring_review.md`](docs/nle_scoring_review.md); any scoring fix or exception to the full-oracle requirement needs maintainer agreement.
- TextWorld runs the original compiled games and metadata with recorded hashes. Its 80-step native budget remains unchanged even where an original prompt says 25 or 40. Cooking seeds 1 and 8 use shorter valid action tapes that remove redundant walkthrough commands; provenance retains the original and selected tapes. Partial progression at native timeout is preserved.
- Baba's original YOU-break behavior resets the puzzle and embeds PIL/lambda memory addresses in the returned text. Only those two known address positions are normalized in audit hashes. Model-facing text, reset semantics, actions, rewards and state remain unchanged; arbitrary hexadecimal text is not removed. Oracles do not exploit the reset shortcut.
- Crafter seeds are fixed at construction because its inherited `gym.seed()` does not reseed the world generator. Native and Harbor runs use identical constructor kwargs. However, the upstream world's sets contain objects hashed by identity, so identical random choices can select different creatures when set order differs. Long native-only replays have reproduced this divergence. The adapter does not sort or patch those sets. Crafter's explicitly disclosed authoritative-state scoring path needs maintainer review; its short reference replay successes do not prove determinism. See [`docs/crafter_scoring_review.md`](docs/crafter_scoring_review.md).
- MiniHack retains original Boxoban level assets, the 100-action budget and reward-based progression. Global RNGs are seeded after environment construction and immediately before reset, matching the upstream evaluator. Correcting that order changed all ten frozen Boxoban instances; their earlier oracle results are superseded by the corrected 39-oracle/one-diagnostic validation. For Hard Boxoban seed 0, exhaustive search found no solution within 100 moves and an exact minimum of 104 in the stated static Sokoban model. The unchanged native environment truncates its first 100 actions at progression 0. This is not a successful 104-step native episode. The task remains selected without a replacement seed or extended budget; its full-oracle requirement needs maintainer handling. See [`docs/minihack_seed_and_budget_review.md`](docs/minihack_seed_and_budget_review.md).
- The shared SDK lock aligns model clients on both sides. The pinned upstream OpenAI wrapper does not forward its `client.timeout` setting to the SDK; documented process/Harbor timeouts provide outer limits. No one-sided client patch changes native behavior.
- Game dependency reproducibility still needs work: source revisions and selected direct packages are pinned, but not every game's transitive dependency resolution is fully locked. Saved runtime versions describe the local runs; complete per-game locks and clean-build checks remain required before formal parity.
- The game and verifier receive a local result token; model agents do not. Verifier output directories are root-owned. Source preparation and container builds require network access for pinned public inputs; reference and offline tests need no model credentials. This is not evidence of isolation on an untested platform.
- The original one-episode BabyAI fixtures and `scripts/check_smoke.py` remain for historical reproduction. Multi-environment reference checks use `check_suite_reference.py`; the BabyAI full-oracle checker remains available for its 50-case scope.
- Empty parity results, incomplete oracle coverage, unresolved exception handling, untested Daytona execution and unpublished artifacts prevent a Ready for Review claim. The submission validator rejects the intentionally empty parity array; this is an outstanding requirement, not a passing acceptance check. A Draft/WIP PR requests feedback and does not waive those requirements.
- The submission validator also warns that `test.sh` does not contain a direct reward-file write, because it invokes `verifier.py`; that verifier writes `/logs/verifier/reward.txt` only after a valid protected result. A separate adapter-name warning follows from the empty parity array. These warnings are disclosed alongside the actual runtime evidence, rather than presented as a clean validator pass.

## Installation / Prerequisites

Install Git, [uv](https://docs.astral.sh/uv/), Docker with Linux containers and Compose, and Harbor 0.26.0. The generator requires Python 3.12+; game and model-agent runtimes use pinned Python 3.10 Linux images. From the parent workspace:

```bash
git clone https://github.com/balrog-ai/BALROG.git BALROG
git -C BALROG checkout b7afe79e3e4265811cfa985ed7c95c4d1a11e3f5
git clone https://github.com/BartekCupial/Minigrid.git minigrid-source
git -C minigrid-source checkout cf73dd148e51276bd675a37e3bfb0bf2b42329b2
uv tool install harbor==0.26.0
cd harbor-index-adapters/src/balrog
uv sync
```

The archive preparation scripts fetch the other pinned repositories/assets. The generator has no third-party Python runtime dependencies. Model launchers and dataset-manifest generation use a separate interpreter with Harbor installed. Do not install upstream BALROG into the generator environment: both packages are named `balrog`; upstream code is loaded separately in the runtime images. Initial builds may be substantial, especially TextWorld's native components.

## Troubleshooting

- **Docker unavailable:** start the daemon and check `docker info` and `docker compose version`. Windows must use Linux containers.
- **Windows encoding or verifier permissions:** enable `PYTHONUTF8=1` and use `auto_mounting=false`. A failed verifier ownership healthcheck is an infrastructure issue.
- **Source or asset mismatch:** check source commits and `runtime_sources.json` hashes, then rerun the matching preparation script. Generation does not silently change checkouts or accept a different asset archive.
- **Wrong task/split:** sanity means seed 0 for each selected family, totaling 58 only when all environments are selected. Use separate directories for full and sanity model runs.
- **Existing output:** use `--overwrite` only for generated tasks; use new evaluation job/output names to retain previous evidence. Regenerate task digests after changing tasks.
- **Startup/replay failure:** inspect game and verifier logs and confirm source/dependency pins. A missing reward file is an infrastructure error, not a zero-score task.
- **Unexpected partial oracle score:** inspect `solution/reference_status.json`. The ten Crafter, five NetHack and Hard Boxoban seed-0 diagnostic references are intentionally not complete oracles.
- **Model launcher refusal:** replace the placeholder only with the agreed exact model ID, configure credentials, and check native budgets against process and model-call limits. A dry-run does not test provider availability or quota.
- **Harbor import error:** select the interpreter that actually contains Harbor with `--harbor-python`; the generator environment is independent.

## Citation

```bibtex
@article{paglieri2024balrog,
  title={Benchmarking Agentic LLM and VLM Reasoning On Games},
  author={Paglieri, Davide and Cupia{\l}, Bart{\l}omiej and Coward, Sam and Piterbarg, Ulyana and Wo{\l}czyk, Maciej and Khan, Akbir and Pignatelli, Eduardo and Kuci{\'n}ski, {\L}ukasz and Pinto, Lerrel and Fergus, Rob and Foerster, Jakob Nicolaus and Parker-Holder, Jack and Rockt{\"a}schel, Tim},
  journal={arXiv preprint arXiv:2411.13543},
  year={2024}
}
```

## Authors & Contributions

BALROG and the BabyAI/Minigrid, Baba Is AI, TextWorld, Crafter, NetHack/NLE and MiniHack projects retain credit for their original implementations and assets. Generated tasks attribute the benchmark authors. Adapter: QYechang (`qiyechang@gmail.com`), covering fixed-case generation, container integration, reference planning/replay, verification and parity tooling. BabyAI uses its native expert; Baba and MiniHack use native-action search/navigation solutions; TextWorld uses validated walkthroughs; Crafter and NetHack currently provide diagnostics. No live model-parity contribution is claimed before those experiments are completed.
