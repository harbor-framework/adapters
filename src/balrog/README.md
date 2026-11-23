# BALROG Adapter

## Overview

This adapter generates **255 fixed text-only episodes across all six BALROG environments**, covering the 58 task types in the pinned upstream configuration. Task families, seeds and native action budgets are fixed before evaluation. This is a reproducible selection of upstream episodes, not an official fixed upstream test set.

This is a WIP submission for feedback on the implementation and three unresolved benchmark issues. Model parity has not run, provider credentials have not been provisioned for these experiments, and `parity_experiment.json` is intentionally `[]`. The full Docker rerun after separate-verifier migration completed all 255 tasks with zero exceptions or retries, confirming 239 full-score oracles and 16 diagnostic references. A separate privileged Crafter V45 reference achieved 40/40 native completions and 10/10 full-score Harbor trials with saved-result regrades; it has not replaced the canonical fixtures. NetHack scoring, a MiniHack Boxoban action budget and Crafter's privileged oracle and replay exception need maintainer review. This does not satisfy the guide's complete-oracle milestone or establish Ready for Review status.

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
- A collect hook inside the trusted game service authenticates locally, finalizes the episode and attempts independent replay in a fresh native environment. It exports `/var/lib/balrog/result.json`; Harbor collects this artifact explicitly from `service = "game"` before stopping the original environment. A separate verifier container checks the saved evidence and frozen task identity, then writes native progression to `/logs/verifier/reward.txt`. The verifier does not contact a live game or receive the result token.
- Replay must match for five environments. Crafter's original simulator can diverge despite identical seeds and actions; only that known divergence permits the isolated live game's score, explicitly marked `replay_verified: false` and `scoring_mode: authoritative_native_state`, with a divergence diagnostic. The migration preserves these native scoring and replay rules. Missing artifacts, invalid schemas, task-identity mismatches and simulator or initial-state failures produce no reward file.
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
│   │   ├── export_result.py
│   │   ├── play.py
│   │   ├── requirements-agent.lock
│   │   └── vendor/                 # Required pinned source/asset archives
│   ├── solution/
│   │   ├── solve.sh
│   │   ├── replay_oracle.py
│   │   ├── oracle_actions.json     # May contain a diagnostic reference
│   │   └── reference_status.json
│   └── tests/
│       ├── Dockerfile             # Dedicated verifier image
│       ├── task_config.json       # Frozen expected episode identity
│       ├── test.sh
│       └── verifier.py
├── babaisai-two-room-make-wall-win-seed-0/
├── textworld-treasure-hunter-seed-0/
└── ... 252 other fixed episodes
```

Each environment receives its own game Dockerfile, source archives, hash-checked `requirements-game.lock`, exact `apt-game.lock`, `runtime-lock.json` and `runtime_guard.py`. The guard checks source archives, the full installed package inventory and the Python/Linux target. All generated tasks set `[verifier] environment_mode = "separate"` and bundle their grading code in `tests/Dockerfile`. Generation creates a fresh game-result token for each task, provided only to the game service; frozen episodes, IDs and source archives remain stable. This local token is unrelated to model-provider credentials. The legacy BabyAI-only generation path omits `reference_status.json` because its 50 references are all complete oracles. See [separate verification and artifact retention](docs/separate_verifier.md) for the transfer contract and regrading requirements.

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

Latest reference status, with the canonical run and additional experiments distinguished:

| Environment | Canonical separate-verifier references | Additional evidence / remaining requirement |
|-------------|----------------------------------------|---------------------------------------------|
| BabyAI | **50/50** reward 1 | Expert trajectories and fresh replay verified |
| Baba Is AI | **120/120** reward 1 | Search trajectories and fresh replay verified |
| TextWorld | **30/30** reward 1 | Native walkthroughs and fresh replay verified |
| MiniHack | **39/40** reward 1 | One upstream 100-action case needs 104 moves; separate 200-action proposal passes 40/40 |
| Crafter | Ten original diagnostics at `2/22` | **V45: 40/40 native games and 10/10 Harbor games at full score**, plus ten matching saved-result regrades; privileged oracle/fallback acceptance and integration pending |
| NetHack / NLE | Five partial/zero-score diagnostics | AutoAscend v2: five exact native replays, no ascension; scoring limitation and winning-policy gap remain |
| Model parity | Not run | Proposed matched experiment and separate standard-agent evaluation below |

The archived pre-migration evidence remains in [validation/](validation/README.md). Those jobs used the shared verifier and also recorded 239 full-score references plus 16 diagnostics; they are historical evidence, not additional trials of the migrated implementation.

Full post-migration Docker validation on Harbor **0.26.0** completed **255/255 tasks with zero exceptions and zero retries**: 239 full-score oracles and 16 diagnostic references. Every trial used a separate verifier and successfully collected its protected result from the game service. All 255 fresh replays passed, all scores matched the frozen references, and the task/source snapshots were unchanged. The existing Crafter fallback was not needed in this run. See the [full validation report](docs/separate_verifier_full_validation.md) and [255-task evidence summary](docs/separate_verifier_full_validation.json). These new results are recorded separately from the historical baseline above and do not constitute model parity or complete full-score oracle coverage.

Separate representative checks on `babyai-goto-seed-0` scored **1.0** with its three-action reference solution and **0.0** with 64 legal `turn left` actions. Both trials completed without exceptions, used separate verifier environments, and collected the result successfully from the game service. A verifier-only regrade of the correct trial also scored **1.0**, without rerunning the agent. See the [migration validation](docs/separate_verifier.md#validation-status) and [representative evidence summary](docs/separate_verifier_validation.json).

Additional research evidence is recorded separately from that canonical run:

- **Crafter V45:** one frozen privileged policy completed 40/40 native games at 22/22 achievements within the original 2,000-action limit. Ten fresh Harbor trials, seeds 0–9, scored 1.0 in separate verifiers; ten saved-artifact-only regrades also scored 1.0. These use the disclosed authoritative-native-state scoring path after fresh-game replay divergence. Saved-result regrading does not establish deterministic gameplay replay. The private-state controller and its research task variant are not the default oracle or model interface; maintainer acceptance and production integration remain pending. See the [V45 report](docs/crafter_v45_validation.md).
- **NLE AutoAscend v2:** the wield-confirmation fix allowed all five seeds to continue without controller errors under a 10,000-action research cap. All 49,451 accepted actions matched fresh native-process replays; no run descended below depth 1 or ascended. Mean native progression was 0.0337761488; seed 4 starved. No v2 Harbor replay was performed, and the scoring patch remains unapplied. See the [bounded validation report](docs/nle_autoascend_v2_validation.md).

A separate, unapproved MiniHack budget proposal also completed a real Harbor run: **40/40 reward 1**, with all 1,531 native transitions and independent replays checked. It changes the ten Boxoban budgets to 200 while retaining 100 for the other 30 cases. The original fixtures remain unchanged, so this adds **zero** oracles to the 239 above. Adoption requires an agreed upstream correction and matching settings on both parity sides; see [`docs/minihack_seed_and_budget_review.md`](docs/minihack_seed_and_budget_review.md).

The original MiniHack gap is an **upstream-budget constraint, not an adapter-induced failure**. For `minihack-boxoban-hard-v0-seed-0`, independent A* and exhaustive single-action BFS both establish a 104-move minimum under the validated legal movement rules; BFS exhausts 796,766 states reachable within 100 moves without a goal. The unmodified native game and Harbor both truncate at the original 100-action limit with progression 0. [BALROG PR #70](https://github.com/balrog-ai/BALROG/pull/70) proposes the budget remedy; it is not merged or applied here.

A separate Crafter reference prototype attained native and Harbor reward 1 on seed 6 in 725 actions. It uses a custom trusted-host controller with private read-only state, and fresh replay still diverges. This is one research success, not the standard oracle workflow or reliable ten-seed coverage; it also adds zero to the baseline count. See [`docs/crafter_scoring_review.md`](docs/crafter_scoring_review.md).

The committed [validation index](validation/README.md) links the [255-case baseline summary](validation/baseline.json), [saved validator reports](validation/validator_reports.json), and [source/runtime provenance](validation/provenance.json). These are summaries of saved local artifacts, not fresh reviewer reproduction. Full raw Harbor jobs, local research controllers and game assets are not included or uploaded. The [MiniHack proposal](validation/proposals/minihack_200.json) and [private Crafter seed-6 diagnostic](validation/diagnostics/crafter_private_seed6.json) are recorded separately and do not increase baseline oracle coverage.

After the verifier migration, audit that unchanged historical bundle with `python scripts/build_validation_bundle.py --check --historical`. It checks bundle integrity, fixtures and scores, and reports the changed source hashes. The strict `--check` continues to require the old review snapshot; neither command turns the historical results into validation of the migrated runtime.

The separate long Crafter Harbor diagnostic also completed without errors: 180 actions, native reward `2/22`, and the actual protected scoring path reported `replay_verified: false`, `scoring_mode: authoritative_native_state`, with first divergence at step 152. The [scoring review](docs/crafter_scoring_review.md) explains this disclosed replay policy. It is not a full-score oracle or an extra task in the 255-case scope.

The earlier BabyAI-only validation used Harbor 0.26.0 with Linux Docker. Its separate seed-0 oracle scored 1 in three actions; a fresh no-op control scored 0 with no actions. `scripts/check_oracle.py --job JOB --split full` remains the strict checker for that 50-episode scope. Oracle agreement is not model parity.

All five additional environments have a passing zero-action Harbor control. The first combined job produced four zero scores and exposed MiniHack's missing initial `get_stats()` field. The adapter now reads the actual native `BaseProgress` initial value without taking an extra action; a separate retry completed with reward 0 and zero exceptions. The failed attempt remains in the local attempt history rather than being relabeled as a passing run. All 40 MiniHack initial states also passed native zero-action/replay checks. These controls are separate from the 255 reference episodes; see the [initial-score explanation](docs/minihack_seed_and_budget_review.md#native-initial-score-serialization).

An independent reset-order audit passed all 210 fixed cases in BabyAI, Baba Is AI, TextWorld and Crafter. It used the original evaluator's `make_env → seed → reset` order from two distinct constructor RNG states, then checked initial hashes, all 3,133 reference transitions, native progression and fresh service replay. Crafter's references are short partial traces; this does not establish deterministic long-trajectory replay. NetHack and MiniHack are outside that 210-case audit.

Offline generator, artifact and statistics tests use fixtures and synthetic artifacts:

```bash
PYTHONPATH=src/balrog/src HARBOR_PYTHON -m unittest discover -s src/balrog/tests -v
```

Use the hash-locked Harbor interpreter described below for `HARBOR_PYTHON`. In PowerShell, set `$env:PYTHONPATH = "src/balrog/src"` and `$env:PYTHONUTF8 = "1"` first, then invoke that interpreter with `-m unittest discover -s src/balrog/tests -v`. Runtime tests use Python 3.10 for upstream games and a separate Python 3.12 Harbor environment for the bridge and ATIF validation; see `tests/runtime/README.txt`. Those tests use fake model clients. On Docker Desktop for Windows, `auto_mounting=false` lets the pre-agent healthcheck enforce root-owned verifier output permissions, and Harbor retrieves logs after verification.

The saved pre-migration checks passed 53 unit tests with one Windows symlink-creation skip (54 total), plus 44 runtime tests across six groups. These include six Crafter failure-policy tests, eight suite-verification tests and the fake-client agent comparison. Wheel/sdist builds and six project-CLI generation checks also passed; those packaging checks do not rerun Docker gameplay. See the [submission checks](validation/submission_checks.json) for counts and the [validation index](validation/README.md) for the evidence scope. No paid model API was called.

The 2026-11-21 PR update reran the current offline suite: **69 passed and one Windows symlink-permission skip** (70 total), including the separate-verifier and historical-evidence checks. The historical bundle integrity check also passed with `--check --historical`, explicitly reporting source drift. The structural validator still reports 29 passing checks, the empty-parity error and two disclosed warnings.

The 2026-11-22 [no-key parity preparation](docs/parity_preparation.md) passed **100 tests with one Windows skip**, 24 launcher dry-runs, eight clean image builds and all 255 frozen initial-state checks. Ten fresh references on **Harbor 0.27.0** matched their scores and replays with zero exceptions: eight full scores plus the original Crafter `2/22` and NLE `0` diagnostics. A separate 64-left-turn BabyAI control scored 0; its correct reference scored 1. Docker and Daytona launch paths are implemented on both sides, but actual Daytona execution and real-model parity remain untested.

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

The pinned Harbor 0.27.0 interpreter can prepare an unpublished `dataset.toml` from the adapters repository root:

```bash
HARBOR_PYTHON src/balrog/scripts/write_dataset_manifest.py --dataset datasets/balrog-six-games --environments all --name balrog/six-games
```

Replace `HARBOR_PYTHON` with that interpreter's executable path. The script checks exact split coverage and task names, then computes Harbor task digests. This does not publish or register the dataset. Regenerate the manifest after changing generated tasks.

## Comparison with Original Benchmark (Parity)

**No live model parity has been run.** `parity_experiment.json` remains `[]`; metadata records zero parity tasks, zero registry tasks and `$0` parity cost. No API key is required for the generation and reference validation above.

| Agent | Model | Metric | Runs | Dataset Size | Original (mean ± SEM) | Harbor (mean ± SEM) |
|-------|-------|--------|------|--------------|-----------------------|---------------------|
| Not run | Not confirmed | Native progression; equal environment weights overall | 0 | 0 | N/A | N/A |

The six-environment [parity proposal](parity/proposal.md) and [machine-readable plan](parity/plan.proposed.json) remain **PROPOSED_NOT_APPROVED_NOT_RUN**. The primary comparison uses upstream `naive` on both sides with proposed model `gpt-4o-mini-2024-07-18` through 2077ai; that model's provider availability is unconfirmed. It proposes 10 fixed sanity tasks spanning all six environments, one complete run on each side, then two additional paired runs: `255 × 3 × 2 = 1,530` formal episodes plus `10 × 2 = 20` sanity episodes, totaling **1,550**. Task seeds are episodes within a run, not independent full benchmark runs. Exact settings, credentials, cost limits and the run plan still require confirmation. Daytona and its service isolation have not been tested remotely; completed reference evidence uses Docker Compose. The [offline preparation guide](docs/parity_preparation.md) covers explicit ten-task selection, launch configuration and dependency locks. Live launchers require an explicit per-environment timeout; 1,800 seconds is only a proposed diagnostic limit, particularly for NLE's unchanged 100,000-action allowance. Formal deadlines must be agreed from measured latency.

For the additional standard-agent requirement, propose **Claude Code 2.1.322 + `claude-haiku-4-5-20251001`**: ten smoke tasks followed by all 58 seed-0 task families over three Harbor-only runs (**184 additional episodes**). This is separately reported subset generalization, not another matched parity experiment. The official release/model references and selection are in the proposal; 2077ai availability, Anthropic Messages/tool-use compatibility, effective CLI settings and budget remain unconfirmed. No standard-agent experiment has run. The two proposals total 1,734 scheduled episodes if both are approved, excluding retained failures or extra diagnostics.

The shared public settings template is [`parity/settings.example.json`](parity/settings.example.json). Its exact model ID is a deliberate placeholder. The proposed settings are not approval to run them. Before live experiments, freeze the same supported agent, model ID, decoding parameters, provider endpoint and history settings on both sides. Set model-call limits per environment so they do not truncate native budgets; the original 128-call BabyAI example is insufficient for Crafter or NetHack. Provider credentials belong in the process environment or ignored `.env.local`, never public settings or artifacts.

First install the hash-locked host harness with `uv venv --python 3.12 .venv-parity` and `uv pip sync --python .venv-parity/Scripts/python.exe --require-hashes src/balrog/parity/requirements-harbor.lock` on Windows (use `.venv-parity/bin/python` on Linux). Run the scripts with that interpreter, referred to below as `HARBOR_PYTHON`. The generator's dependency-free `uv` project alone does not install Harbor.

From the adapters repository root, generate all ten tasks in six per-environment directories, then inspect a planned BabyAI launch:

```bash
HARBOR_PYTHON src/balrog/scripts/prepare_parity.py --output-dir parity-runs/prepared-sanity --benchmark-source ../BALROG --minigrid-source ../minigrid-source --assets-dir ../benchmark-assets
HARBOR_PYTHON src/balrog/scripts/run_native.py --environment babyai --environment-dir parity-runs/prepared-sanity/datasets/babyai/babyai-goto-seed-0/environment --settings src/balrog/parity/settings.proposed.json --selection-plan src/balrog/parity/plan.proposed.json --output-dir parity-runs/babyai/native-sanity --split sanity --dry-run
HARBOR_PYTHON src/balrog/scripts/run_harbor.py --environment babyai --dataset parity-runs/prepared-sanity/datasets/babyai --settings src/balrog/parity/settings.proposed.json --selection-plan src/balrog/parity/plan.proposed.json --jobs-dir parity-runs/babyai/harbor --job-name sanity --split sanity --dry-run
```

`HARBOR_PYTHON` denotes an executable path, not a literal command. Replace `../benchmark-assets` with the directory containing the verified source archives. Both dry-runs validate the selection and settings without reading credentials, building containers, creating run directories or calling a model. With `--selection-plan`, sanity means the exact proposed ten cases globally (two BabyAI cases above); without it, the legacy sanity split remains all 58 seed-0 families. A per-environment JSON list is also supported through `--task-ids-file`.

Both launchers accept `--environment-type docker|daytona` (default Docker). For Daytona, the host lock includes its SDK; provide `DAYTONA_API_KEY` in the launching process environment when real execution is approved. The native path stages the same game image, code and inputs, runs the original evaluator, verifies the runtime before inference and collects artifacts before cleanup even on failure. Its cloud lifecycle is tested with fake providers; remote execution remains untested.

After confirmation and platform preflight, use the agreed settings and explicit `--episode-timeout SECONDS`, then remove `--dry-run`. The Harbor interpreter must match the one used for validation. Both sides apply the same per-episode execution deadline; Harbor allows an additional 120 seconds for artifact collection. Run the same sanity selection on both sides before full runs. Use fresh output/job names; failures and previous attempts must remain visible. The launchers preserve native budgets, reject reused output locations and require exact dataset coverage. A configuration preview does not establish a matched Daytona experiment.

Retain complete job directories, including original submissions/action records, model and agent logs, trusted game result artifacts, grading results and artifact manifests, together with the generated tasks and source/runtime provenance. For future parity uploads, include these in the Hugging Face experiment fork after removing credentials. The separate verifier can regrade collected game evidence without rerunning the agent; old logs alone do not establish that the required evidence is available. See [artifact retention and regrading](docs/separate_verifier.md#artifact-retention-and-regrading).

For each environment, analyze the three planned complete paired runs with its corresponding manifest. This BabyAI example uses three pairs:

```bash
uv run --project src/balrog python src/balrog/scripts/analyze_parity.py --manifest src/balrog/src/balrog/fixtures/manifest.json --split parity --pair parity-runs/babyai/native-1 parity-runs/babyai/harbor/full-1 --pair parity-runs/babyai/native-2 parity-runs/babyai/harbor/full-2 --pair parity-runs/babyai/native-3 parity-runs/babyai/harbor/full-3 --output parity-runs/babyai/analysis.json
```

The analyzer checks complete runs, raw model logs, initial prompt agreement, settings/source/SDK provenance, trusted scores and native batch completion. It reports mean progression and **sample SEM across full runs**, plus run-score range overlap. Fractional progression is never binarized. Then pass one analysis per environment to `scripts/analyze_suite_parity.py` using six `--analysis PATH` arguments. It requires each packaged full manifest's exact IDs and SHA256, matching runner code and model SDK versions, then computes each suite run's equal-weight mean across the six environments before calculating the across-run SEM. Preserve the same run-index pairing across all six analyses.

These scripts produce local analysis artifacts, not formal approval. An original-benchmark parity fork, dataset publication and Hugging Face parity-artifact upload remain pending. Formal `parity_experiment.json` entries and publication links will be added only after real experiments and the corresponding submissions exist.

## Notes & Caveats

- Full-score oracle gaps remain visible. Crafter's ten canonical fixtures still score `2/22`; the separate V45 privileged reference has not been promoted into them. NetHack's pinned `Progress.update` checks only `Xp:*` and `Dlvl:*` achievement entries; the largest value reachable through those lookups is approximately `0.8067964442444019`, and the ascension entry with value 1 is not used. The adapter preserves this scorer without rescaling or synthetic wins. See [`docs/nle_scoring_review.md`](docs/nle_scoring_review.md); any scoring fix or exception to the full-oracle requirement needs maintainer agreement.
- TextWorld runs the original compiled games and metadata with recorded hashes. Its 80-step native budget remains unchanged even where an original prompt says 25 or 40. Cooking seeds 1 and 8 use shorter valid action tapes that remove redundant walkthrough commands; provenance retains the original and selected tapes. Partial progression at native timeout is preserved.
- Baba's original YOU-break behavior resets the puzzle and embeds PIL/lambda memory addresses in the returned text. Only those two known address positions are normalized in audit hashes. Model-facing text, reset semantics, actions, rewards and state remain unchanged; arbitrary hexadecimal text is not removed. Oracles do not exploit the reset shortcut.
- Crafter seeds are fixed at construction because its inherited `gym.seed()` does not reseed the world generator. Native and Harbor runs use identical constructor kwargs. However, the upstream world's sets contain objects hashed by identity, so identical random choices can select different creatures when set order differs. Long native-only replays have reproduced this divergence. The adapter does not sort or patch those sets. Crafter's explicitly disclosed authoritative-state scoring path needs maintainer review; its short reference replay successes do not prove determinism. See [`docs/crafter_scoring_review.md`](docs/crafter_scoring_review.md).
- MiniHack retains original Boxoban level assets, the 100-action budget and reward-based progression. Global RNGs are seeded after environment construction and immediately before reset, matching the upstream evaluator. Correcting that order changed all ten frozen Boxoban instances; their earlier oracle results are superseded by the corrected 39-oracle/one-diagnostic validation. For Hard Boxoban seed 0, exhaustive search found no solution within 100 moves and an exact minimum of 104 in the stated static Sokoban model. The unchanged native environment truncates its first 100 actions at progression 0. This is not a successful 104-step native episode. The task remains selected without a replacement seed or extended budget; its full-oracle requirement needs maintainer handling. See [`docs/minihack_seed_and_budget_review.md`](docs/minihack_seed_and_budget_review.md).
- The shared SDK lock aligns model clients on both sides. The pinned upstream OpenAI wrapper does not forward its `client.timeout` setting to the SDK; documented process/Harbor timeouts provide outer limits. No one-sided client patch changes native behavior.
- All six games have complete Python dependency versions and artifact hashes, Debian package versions from a dated snapshot, pinned source archives and a digest-pinned base image. Installation disables dependency resolution and isolated build dependency fetching; the runtime guard rejects package or OS drift. These locks target CPython 3.10 on Linux x86_64. Source builds are version-locked, not claimed to produce byte-identical wheels. See the [preparation report](docs/parity_preparation.md) for clean-build evidence and the disclosed Baba Is AI metadata correction.
- Only the game service receives the local result token. Its collect hook uses that token to export finalized evidence, which Harbor transfers to the dedicated verifier; model agents cannot write the game artifact or access the verifier's reward directory. Source preparation and container builds require network access for pinned public inputs; reference and offline tests need no model credentials. This is not evidence of isolation on an untested platform.
- The original one-episode BabyAI fixtures and `scripts/check_smoke.py` remain for historical reproduction. Multi-environment reference checks use `check_suite_reference.py`; the BabyAI full-oracle checker remains available for its 50-case scope.
- Empty parity results, incomplete oracle coverage, unresolved exception handling, untested Daytona execution and unpublished artifacts prevent a Ready for Review claim. The submission validator rejects the intentionally empty parity array; this is an outstanding requirement, not a passing acceptance check. A Draft/WIP PR requests feedback and does not waive those requirements.
- The submission validator also warns that `test.sh` does not contain a direct reward-file write, because it invokes `verifier.py`; that verifier writes `/logs/verifier/reward.txt` only after a valid protected result. A separate adapter-name warning follows from the empty parity array. These warnings are disclosed alongside the actual runtime evidence, rather than presented as a clean validator pass.

## Installation / Prerequisites

Install Git, [uv](https://docs.astral.sh/uv/), Docker with Linux containers and Compose, and the hash-locked Harbor 0.27.0 host harness described above. The generator requires Python 3.12+; game and model-agent runtimes use pinned Python 3.10 Linux x86_64 images. Historical 255-task results retain their Harbor 0.26.0 provenance. From the parent workspace:

```bash
git clone https://github.com/balrog-ai/BALROG.git BALROG
git -C BALROG checkout b7afe79e3e4265811cfa985ed7c95c4d1a11e3f5
git clone https://github.com/BartekCupial/Minigrid.git minigrid-source
git -C minigrid-source checkout cf73dd148e51276bd675a37e3bfb0bf2b42329b2
cd harbor-index-adapters
uv venv --python 3.12 .venv-parity
# Linux path below; use .venv-parity/Scripts/python.exe on Windows.
uv pip sync --python .venv-parity/bin/python --require-hashes src/balrog/parity/requirements-harbor.lock
cd src/balrog
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
- **Missing collected result:** inspect the collect-hook log and artifact manifest. `/var/lib/balrog/result.json` must have been collected successfully from `service = "game"`. Harbor may only warn when collection fails; the verifier deliberately fails without a valid artifact. Regenerate old tasks to obtain the new configuration, exporter and verifier image together.
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
