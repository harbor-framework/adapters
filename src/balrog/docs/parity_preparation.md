# Offline preparation for BALROG parity

Prepared on 2026-11-22. **No model API calls, Daytona sandboxes or paid experiments were started.** The [proposal](../parity/proposal.md) remains unapproved and `parity_experiment.json` remains `[]`. Reference checks below use frozen action sequences; they are not model sanity results.

## Exact ten-task selection

`--selection-plan parity/plan.proposed.json` selects these tasks on both sides, in their original manifest order. The helper verifies all six manifest hashes, all 255 case IDs and native budgets before extracting the sanity subset. It rejects unknown or duplicated IDs, wrong-environment selections and source drift. Without an explicit selector, `--split sanity` retains the existing 58 seed-0 families.

| Environment | Exact task ID | Native action allowance | Coverage |
|---|---|---:|---|
| BabyAI | `babyai-goto-seed-0` | 64 | Navigation |
| BabyAI | `babyai-putnext-seed-0` | 128 | Object manipulation |
| Baba Is AI | `babaisai-make-win-seed-0` | 100 | Rule construction |
| Baba Is AI | `babaisai-two-room-make-you-make-win-seed-0` | 100 | Multi-room rules |
| TextWorld | `textworld-treasure-hunter-seed-0` | 80 | Text navigation |
| TextWorld | `textworld-the-cooking-game-seed-0` | 80 | Multi-step text interaction |
| Crafter | `crafter-default-seed-0` | 2,000 | Survival and crafting |
| NLE | `nle-nethackchallenge-v0-seed-0` | 100,000 | Long-horizon native game |
| MiniHack | `minihack-mazewalk-9x9-v0-seed-0` | 100 | Maze navigation |
| MiniHack | `minihack-quest-easy-v0-seed-0` | 100 | Quest interaction |

These ten cases total 102,752 allowed native actions per side. Selection does not imply they will exhaust the allowance or that their reference solutions score one. All 255 original cases remain in the formal proposal, including the difficult Boxoban case omitted from this small coverage check.

`scripts/prepare_parity.py` generates six per-environment directories, validates Docker and Daytona Harbor job previews, and records every generated file's SHA256, settings/manifest hashes and the full native image build context. It refuses to overwrite an earlier preparation. No credential file is read, and no container or model is launched by that command. See the [README commands](../README.md#comparison-with-original-benchmark-parity) for invocation from a Git checkout; project-level parity scripts are not distributed in the generator wheel.

## Host harness and launch configuration

The candidate harness is **Harbor 0.27.0 with its Daytona extra**, pinned with its transitive dependencies and artifact hashes in [requirements-harbor.lock](../parity/requirements-harbor.lock). Install it in a separate Python 3.12 environment using `uv pip sync --require-hashes`. The universal lock has 149 entries; 148 apply to the tested Windows host, including Daytona SDK 0.233.0. The original 117-package Docker reference host is unchanged; the Daytona environment adds 31 packages without changing those versions. The prior 255-task migration report continues to describe Harbor 0.26.0, not a rerun on the new version.

The launchers use Harbor's actual `JobConfig` and the valid `python -m harbor.cli.main` entry point. Concurrency is a top-level setting, initially one for the model proposal, and automatic job retries are zero. Upstream client retries retain their own unchanged semantics. A live launch requires an explicit positive `--episode-timeout`; previews may leave it unset. Native execution and Harbor remote execution use the same deadline T. Harbor's outer agent timeout is T+120 seconds to allow final artifact collection. This grace period does not extend the native action budget or model execution deadline.

Both launchers accept `--environment-type docker|daytona --dry-run`. Harbor uses `auto_mounting=false`; protected results come from the game service and grading runs in a separate verifier. The native Daytona path runs the original `native_batch.py` / `Evaluator.run_episode` in a derived game image. It changes startup/user metadata to match native Docker execution, uploads the same hashed code and inputs, and verifies the complete runtime inventory before model execution. Its remote batch ceiling is N×T+120 seconds and host polling ceiling is N×T+150; each episode still has the same T as Docker. Build/setup, collection and cleanup also have explicit host deadlines.

**Daytona previews and fake-provider tests do not establish remote execution.** Source inspection confirms that Harbor 0.27 supports Compose services, game-side collection and a separate verifier. The SDK forwards the native custom Dockerfile without a client-side package rewrite, but hosted backend behavior remains untested. Real preflight must confirm exact runtime inventory, image building, networking, permissions, artifact transfer and deletion. If cloud additions change the locked runtime, diagnose them rather than weakening the guard. Cleanup records say attempted, not that remote deletion is verified.

Both launchers support `--task-ids-file` for a per-environment JSON list and record selection, settings and runner hashes. The native launcher also records its full build context. The preparation receipt binds every generated task file; the Harbor launcher records task identity/configuration hashes, and Harbor records its task checksum during execution. Dry-run validates even when the supplied credential file does not exist; it creates no runtime output. Live attempts use new output/job names so failed runs remain available for diagnosis.

## Runtime dependency locks

Each game has a complete Python package inventory, exact artifact URLs and SHA256 values, an exact Debian package inventory and explicit installation additions. The Python base is pinned by image digest. Apt uses a dated Debian snapshot rather than changing mirrors. Runtime guards check the CPython/Linux x86_64 target, full Python build string, archive hashes, installed package versions and all OS package versions, then run `pip check`.

Python installation uses `--require-hashes --no-deps --no-build-isolation`. Locked wheels are installed before source distributions so builds use the pinned build tools and headers. The agent and all six games share the same 41 SDK/build-package artifact URLs and hashes. Source builds are version-locked; this is not a claim that locally built wheels are byte-identical. Other operating systems and CPU architectures are not covered by these game locks.

Baba Is AI declares `opencv-python`, while the validated runtime uses `opencv-python-headless==4.10.0.84`. The build applies a narrowly checked dependency-metadata correction to Baba's installed `METADATA` and updates its `RECORD`. It verifies the expected original declaration, preserves all OpenCV file bytes, records their hashes and fails if the expected metadata differs. No game code, action rule, observation or scorer is patched by this correction.

## Validation evidence

The machine-readable [preparation validation report](parity_preparation_validation.json) distinguishes completed local checks from any remaining infrastructure checks. It records image/input hashes so later experiments can be tied to the reviewed versions. Raw local logs and generated task snapshots are retained separately; no public artifact upload is claimed.

- The complete host test run passed 100 tests, with one Windows symlink test skipped (101 total). It includes launcher selection, malformed settings, runtime-lock tampering, metadata repair, separate-verifier failure controls and ten native Daytona lifecycle tests. Fake HTTP tests used local loopback, not a model service.
- All 24 public dry-run combinations passed: native and Harbor, each with Docker and Daytona, for six environments. Every path selected the expected 2/2/2/1/1/2 cases with no credential file and no runtime directory creation.
- Offline wheel/sdist checks confirmed all 54 package resources, including every runtime lock and the guard, match the source. An isolated wheel import read all 255 cases and staged all six sets of locks.
- All eight images built without cache and passed `pip check`. All 255 frozen initial states matched. Six native reference checks covered 163 exact transitions with unchanged scores and verified replay.
- Ten fresh Harbor 0.27 reference tasks completed with zero exceptions or retries. All scores and replays matched: eight scored 1, Crafter scored 2/22 and NLE scored 0. These two diagnostics remain diagnostics. All ten protected artifacts were collected from the game service and graded in separate verifiers.
- The same BabyAI task scored 1 for its three-action reference and 0 for a separate 64-left-turn control, with the game and grader unchanged. Both replayed successfully.
- The current native producer ran inside a `--network none` container with a loopback scripted HTTP server. Its untouched output passed the Daytona result validator: score 1, three actions and three local SDK requests. This checks current file formats; it is not model parity or remote execution.

Infrastructure failures and retries are retained separately from completed game checks. Docker Desktop's engine stopped during two initial image builds; a scoped recovery restored it, after which remaining builds and reference jobs ran sequentially. The first reference attempt failed during Docker preflight before any trial started. No incomplete attempt is reported as a passing run.

## Remaining execution gates

Wait for the maintainer's response on the original oracle limitations, the proposed agent/model, stage scope and resource limits, then obtain 2077ai and Daytona credentials privately. Confirm the exact dated model and gateway behavior. Validate both sides and correct/wrong/saved-result grading controls on the agreed platform. Freeze the reviewed commit, task snapshots, images, effective prompts/settings and measured per-environment deadlines before scaling.

The supplementary Claude Code/model proposal still needs its protocol and effective CLI configuration confirmed and independently validated. These preparations do not promote V45, apply the pending NLE scoring patch, change the MiniHack budget or resolve the original oracle exceptions.
