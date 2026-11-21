# SuperGPQA parity report — 2026-11-21

## Result

**600/600 formal results are complete:** the same 100 questions, three independent
passes per side. Sample-wise accuracy is **45.3333 ± 0.8819%** on the original
side and **44.6667 ± 0.6667%** on Harbor (mean ± sample SEM across the three runs).
The observed ranges, **44–47%** and **44–46%**, overlap and satisfy the primary
matching criterion in the Harbor adapter guide. The Harbor-minus-original mean
difference is **−0.6667 percentage points**.

This is matched direct-API parity on a fixed subset; the experiment does not
establish results on all 26,529 questions or compatibility with CLI agents.
The model alias and execution-order departures below remain review considerations.

| Run | Original correct / 100 | Harbor correct / 100 |
|---|---:|---:|
| 1 | 44 | 46 |
| 2 | 45 | 44 |
| 3 | 47 | 44 |

SEM is the sample standard deviation of the three run scores divided by √3.
It describes run variability conditional on these 100 questions. The acceptance
check uses observed min–max run ranges, not overlap of SEM intervals.

## Experiment configuration

| Item | Recorded value |
|---|---|
| Agent | `supergpqa-direct@0.1.0` on both sides |
| Inference code revision | [`fdef3d1469a9ebf213082e9cf2c67b73989115a1`](https://github.com/jialen2/adapters/tree/fdef3d1469a9ebf213082e9cf2c67b73989115a1/src/supergpqa) |
| Requested model | `gpt-6-luna`, as suggested in reviewer feedback |
| Returned model | `gpt-6-luna-2026-09-22`, checked on all 600 formal replies |
| Endpoint | `https://app.ppapi.ai/v1` (2077ai / PP API) |
| Prompt and tools | Zero-shot; single user message; closed-book; no model-accessible tools |
| API parameters | `reasoning_effort=none`, `temperature=0`, `max_completion_tokens=2048`, `stream=false` |
| Transport | Python stdlib urllib; Python 3.13.18; certificate verification enabled |
| Timeouts | 300-second HTTP socket timeout; Harbor agent 600 seconds, verifier 30 seconds |
| Runtime | Harbor 0.25.0; source `ff2a1ef48070a8df374669138e4d4db79b77f013`; Docker 29.9.3; Lima 2.3.0; Linux aarch64 |
| Concurrency | Four workers per active side; at most eight API requests after the user-requested overlap |
| Formal time span (UTC) | 2026-11-21T15:47:52.127405+00:00 to 2026-11-21T20:28:22.228002+00:00 |

The original side is the standalone runner in `parity.py`. It compiles the
unchanged prompt-rendering and parser function bodies from the checksum-verified
upstream checkout using `parity_upstream.py`; unused pandas/Excel modules are
not imported. It is not the full upstream `infer.py` pipeline. The Harbor side
uses the same client and a `BaseAgent` wrapper that uploads the unmodified API
reply to `/app/answer.txt`; Harbor then runs the real task verifier in Docker.
The shared file-output/closed-book suffix and CRLF/CR-to-LF normalization are
applied to both sides. There is no LLM judge.

A dated request to `gpt-6-luna-2026-09-22` returned HTTP 503, while the alias worked.
Consequently, requests use the alias and reject replies whose returned model ID
differs from the recorded dated version. This guard is not a provider guarantee
that an alias is immutable. Returned `system_fingerprint` values are null.

## Selected questions

The pinned upstream revision is `e31e8bf3e7089aef808be5ddecafd4538dee6e41`.
`--split parity --parity-size 100 --seed 42` uses proportional allocation over
(discipline, field, subfield, difficulty), with largest-remainder quotas and
SHA-256-ranked UUIDs within strata. The retained `manifest.json` fixes the IDs.
The subset is **100/26,529 (0.3769%)**, following the team's
suggestion to use around 100 questions. It contains eight of the thirteen
disciplines; the small allocation does not cover every taxonomy stratum.

| Discipline | Questions |
|---|---:|
| Engineering | 25 |
| Science | 50 |
| History | 4 |
| Medicine | 9 |
| Literature and Arts | 5 |
| Agronomy | 2 |
| Economics | 3 |
| Law | 2 |

Difficulty counts: easy 13, middle 52, hard 35. Macro metrics below average only
the categories represented in this fixed subset.

## Full metric comparison

All values are percentages; uncertainty is sample SEM across three runs.

| Metric | Original mean ± SEM | Harbor mean ± SEM | Run ranges overlap |
|---|---:|---:|---|
| Sample-wise accuracy | 45.3333 ± 0.8819 | 44.6667 ± 0.6667 | Yes |
| Discipline macro accuracy | 37.8750 ± 3.0958 | 39.8287 ± 1.6178 | Yes |
| Field macro accuracy | 47.7875 ± 1.0888 | 46.0837 ± 0.6747 | Yes |
| Subfield macro accuracy | 44.3651 ± 1.0317 | 44.4444 ± 0.6919 | Yes |
| Accuracy: hard | 37.1429 ± 1.6496 | 36.1905 ± 0.9524 | Yes |
| Accuracy: middle | 55.7692 ± 1.1103 | 54.4872 ± 0.6410 | Yes |
| Accuracy: easy | 25.6410 ± 6.7840 | 28.2051 ± 2.5641 | Yes |

Raw run arrays for all metrics are in `parity_experiment.json` and `analysis.json`.

## Paired outcomes and sanity diagnosis

| Run | Both correct | Both incorrect | Original only correct | Harbor only correct |
|---|---:|---:|---:|---:|
| 1 | 40 | 50 | 4 | 6 |
| 2 | 37 | 48 | 8 | 7 |
| 3 | 37 | 46 | 10 | 7 |

Across the 300 paired instances, original-only successes total 22 and Harbor-only
successes total 20. This is descriptive evidence; no formal equivalence test is claimed.

The 300-second configuration's eight-question sanity check scored 5/8 on the
original side and 2/8 on Harbor. Investigation found identical request bodies,
client fingerprints and prompt-token counts in all eight pairs. Replaying all
16 saved responses through both scoring paths gave identical rewards. API
response JSON and saved text also matched. Seven pairs used different reported
prefill replicas; this is an observation, not proof of the cause of variability.

Three sanity examples are preserved in `diagnostics/sanity-debug.json`:

- Carbon diffusion: Harbor omitted the density conversion and then selected a
  different option; the difference was already present in the API response.
- Approximating e: gold D is 2.7181, whereas Harbor chose G = 2.7183, closer to e.
  Every supplied option is within the stated 0.001 tolerance, so the wording
  does not identify a unique mathematically acceptable option. The gold was kept.
- Integral: Harbor reversed a logarithm ratio without compensating its sign and
  omitted the required `Answer:` line. Both parsers returned `miss`; manually
  interpreting its selected B still disagrees with the gold and derivative check.

Gold labels, parser behavior, question wording and the selected UUIDs were never
changed to improve agreement. `temperature=0` did not produce identical replies.

## Execution history and transport failures

1. A single alias compatibility request succeeded. A separate dated-ID routing
   probe failed with HTTP 503. Neither is a formal result.
2. The first paired eight-question calibration used a 120-second timeout and
   scored 4/8 versus 3/8. A 119.7-second call motivated the symmetric 300-second
   timeout, a fresh manifest/configuration revision and a new paired sanity check.
3. Formal original run 1 completed before Harbor run 1. At the user's request,
   original run 2 then overlapped Harbor run 1; original run 3 later overlapped
   Harbor run 2. Harbor run 3 began after Harbor run 2 completed. This **departs
   from the guide's strictly paired ramp-up order** and is recorded for review.
4. Interrupted native Harbor trials were archived. Completed API replies were
   reused only to finish the same side/run/task's file handoff and verifier.
   Those recoveries did not issue duplicate model requests for completed replies.
5. Failed transport attempts were retained separately and explicitly retried
   with unchanged prompts, settings and timeout. Later recovery isolated such
   failures so one timeout did not block unrelated remaining questions.

The deduplicated request ledger contains **667 observed model-request attempts**:
**633 completed responses** (600 formal, 16 final-configuration sanity, 16 earlier
calibration, 1 alias probe) and **34 failures** (32 timeouts, one HTTP 400, one
dated-ID HTTP 503). Auth/model-list connectivity probes are not inference calls
and are outside this ledger. Copied checkpoint snapshots count once by
(fingerprint, start time). No received formal answer was retried based on its
score, and transport failures were not silently assigned reward zero.

The 600 selected final calls consumed 220,284 prompt tokens and
66,071 completion tokens; recorded reasoning tokens were zero.
**Billed USD is unavailable.** Timed-out calls may have been billed without
returning usage, so these token totals are not a complete billing statement.

Successful API latency: mean 50.63s, median
23.39s, maximum 288.14s. Provider-reported internal
service timings were much smaller on some slow replies. TCP and readiness
observations did not establish a definitive root cause; the evidence is consistent
with delays outside the reported model-service stage. No configuration was
changed solely to obtain a better score.

## Integrity and Oracle evidence

The offline audit checks each side/run has exactly the same 100 unique UUIDs,
all 600 effective request bodies match per UUID, all model IDs pass the dated
response guard, saved text equals raw API content, every score replays, and all
300 selected native Harbor trials have valid rewards and no exception.
Failed/replaced native attempts remain in the separate recovery archive.

The full-bank Oracle independently passed **26,529/26,529**, mean reward 1.000,
zero final exceptions and exact coverage. `oracle/full-bank-evidence.tar.gz`
contains the retained native logs/configs; its screenshot is a rendering of the
saved Harbor terminal output. Oracle does not invoke an evaluation model.

## Reproduction and artifacts

- [Source and both-side runner](https://github.com/jialen2/adapters/tree/fdef3d1469a9ebf213082e9cf2c67b73989115a1/src/supergpqa)
- [GitHub evidence release](https://github.com/jialen2/adapters/releases/tag/supergpqa-parity-2026-11-21)
- [Download the complete evidence bundle](https://github.com/jialen2/adapters/releases/download/supergpqa-parity-2026-11-21/SuperGPQA-parity-evidence-2026-11-21.tar.gz)
- [Hugging Face evidence PR #293](https://huggingface.co/datasets/harborframework/parity-experiments/discussions/293): created, but artifact push was rejected because the shared repository exceeds its 1,000,000-file limit (1,348,025 files after the proposed push). The 46-file payload is available in the GitHub evidence bundle; HF upload requires the repository owners to resolve the limit.
- Dataset registration: pending; namespace/tag request remains `m-a-p/supergpqa`
  with `v1.0` and `parity`. This report does not publish the task bank.

From the adapters repository root with this adapter and Harbor installed:

```bash
# Recompute the report without model calls, after extracting the six run archives.
PYTHONPATH=src/supergpqa/src python src/supergpqa/scripts/summarize_parity.py \
  --experiment-dir /path/to/reconstructed-experiment \
  --output-dir /path/to/recomputed-report

# Re-run the matched experiment with a fresh output directory and provisioned key.
# Set SUPERGPQA_BASE_URL=https://app.ppapi.ai/v1 and SUPERGPQA_API_KEY in the environment.
PYTHONPATH=src/supergpqa/src python -m supergpqa.parity \
  --upstream-repo /path/to/pinned/SuperGPQA \
  --output-dir /path/to/new-experiment --execute --concurrency 4
```

The default runner reproduces the strictly paired schedule. The actual
user-requested parallel scheduling/recovery controllers are preserved in the
artifact bundle, without credentials. Reproduction may produce different model
answers; raw responses and the exact experiment revisions are retained for audit.

The bundle follows the guide's `adapters/supergpqa/` layout, including
`original_parity/`, `harbor_parity/`, `oracle/` and `results_collection/`. The six
formal runs and recovery history are separate compressed archives to preserve
native logs while limiting file counts. `SHA256SUMS` covers the upload payload.
The GitHub report and evidence release are available independently of the blocked HF upload.
Dataset registry publication remains tracked separately.
