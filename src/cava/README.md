## CAVA → Harbor Adapter

## Overview

CAVA (Comprehensive Assessment of Voice Assistants) evaluates the capabilities a voice assistant needs end to end: function calling from spoken requests, instruction following, deception reasoning in multi-party conversations, safety under spoken jailbreaks, and knowledge QA. This adapter packages the **pipeline (transcript) variant** of five CAVA subtasks with deterministic upstream scorers. Each task gives the agent exactly what the LLM stage of CAVA's OpenAI pipeline sees: the pipeline preamble, the ASR transcript of the audio wrapped in `[BEGIN AUDIO] ... [END AUDIO]`, and the CAVA task prompt.

- **Dataset size:** 3,671 tasks (one per CAVA record):

  | Subtask | Tasks | Source data | Metric (reward per task) |
  |---|---|---|---|
  | `deception_detection` | 151 | `data/Werewolf/werewolf.jsonl` + `mikesun26card/werewolf_audio_dataset` | accuracy (werewolf named, or `None`) |
  | `jeopardy` | 1,000 | `WillHeld/CartesiaJeopardy` (`combined`) | PEDANT correctness |
  | `multimodal_instruction_following` | 1,000 | `SALT-NLP/MultiModalInstructionFollowing` (first 1,000, as in the run script) | IFEval instruction adherence |
  | `function_calling` | 1,000 | STOP test audio, the 1,000 records of CAVA's committed prediction files | function-call count match |
  | `jailbreak` | 520 | `WillHeld/AudioJailbreakPersuasive` (`train`) | refusal (1 = refused); ASR = 1 − mean |

- **Provenance:** [SALT-NLP/CAVA](https://github.com/SALT-NLP/CAVA) at commit `1af23b1` (no license file in the repository), [blog post](https://talkarena.org/cava). Hugging Face datasets are pinned by revision in `prepare/prepare_manifests.py`.
- **Main modifications for adaptation:** the audio is replaced by its pipeline transcript (`gpt-4o-mini-transcribe`, last 1,500 s, as in `process_with_openai_pipeline`), precomputed once and shipped in the tasks so both parity sides read identical text. Answers go to `/app/answer.txt`; function calls are made with a `call_function` CLI that returns CAVA's `MOCK_RESPONSE(<name>)`. Subtasks that need speech output, an unpublished judge, or wall-clock latency are not included (see Notes & Caveats).

## What is CAVA?

CAVA ([repo](https://github.com/SALT-NLP/CAVA), [blog](https://talkarena.org/cava)) is a benchmark from Stanford SALT for large audio models and speech pipelines across six voice-assistant domains: turn taking, instruction following, function calling, tone awareness, safety, and latency. Its harness (`src/cava/inference.py`) runs a model or an STT → LLM → TTS pipeline over each task's audio, and `process_record` scores each response with a task-specific rule: exact label match, PEDANT for Jeopardy answers, the IFEval checkers for system-prompt instructions, a TOP-parse to function-call comparison for STOP, and a refusal word list for jailbreaks. Each subtask reports its mean score (%).

## Adapter Features

- Task text is generated from the same code path as upstream: prompts copied from `src/cava/config.py`, pipeline messages from `process_with_openai_pipeline` (`src/cava/subtasks.py`).
- Pinned data preparation (`prepare/prepare_manifests.py`): HF revisions pinned, transcripts cached by audio sha256, audio/label alignment checked for Werewolf, missing transcripts and wrong record counts rejected. The audio goes through upstream's decode → 16-bit WAV → `librosa.load(sr=16000)` → last 1500 s chain, so the uploaded bytes are identical to upstream's (checked on Jeopardy and STOP records).
- **Separate verifier sandbox** (`environment_mode = "separate"`, `network_mode = "no-network"`): the declared artifacts `/app/answer.txt` and `/app/function_calls.jsonl` cross over (plus Harbor's implicit `/logs/artifacts` dir, which the scorer never reads). The verifier image bakes in the scorer dependencies at the versions CAVA used (qa-metrics 0.2.32, nltk 3.9.1, scikit-learn 1.3.2, IFEval at `0c495b2`), the nltk data, and the PEDANT models pinned to `zli12321/pedant_models@03519c72` and sha256-checked. `scoring/offline.py` disables every runtime download, and seeds langdetect, so grading is offline and deterministic.
- `scoring/` vendors CAVA's `function_calling.py` and `utils.py` verbatim, and `cava_score.py` ports `process_record`'s scoring branches. Re-scoring CAVA's committed prediction files with it reproduces the scores recomputed from those files exactly (see Parity).
- Function calling: `/app/functions.json` holds CAVA's 62 tool schemas; `call_function <name> '<json args>'` logs the call under any name and prints the mock response, as the upstream tool loop records and answers each tool call. Unlike upstream, where the harness records the calls the model made, the log is a file in the agent's sandbox, so a terminal agent can edit it before finishing (see Notes & Caveats).
- **Agent network: LLM API hosts only** (`[agent] network_mode = "allowlist"`, `api.openai.com`, `api.anthropic.com`; add others with `harbor run --allow-agent-host`, e.g. `app-us.ppapi.ai` for the parity API). The source datasets (and CAVA's committed prediction files) carry the reference answers, and the upstream pipeline has no browsing. Agent installation still runs on the public baseline network. Harbor restores the baseline network right after `agent.run()` returns, before it collects the artifacts and stops the sandbox, so a background process left by the agent has a short public-network window; closing it would need a Harbor-side change (or a non-public baseline with the agent preinstalled).
- Oracle solutions for every task, checked with the verifier's scorer (`prepare/validate_oracles.py`): gold label / prefixed answer / refusal sentence; the gold TOP parse turned into calls (children before parents); rule-built responses that satisfy each MMIF instruction (`prepare/mmif_oracle.py`).
- Parity agent `cava.pipeline_agent:CavaPipelineAgent` reproducing the LLM stage of `process_with_openai_pipeline` (temperature 0, `tool_choice="required"` then `"auto"`, the loop stops once 10 or more calls are recorded, checked before each batch, so a batch can overshoot ten; same retries and backoff).

## Generated Task Structure

```
cava/
├── {subtask}-{item_id}/           # e.g. deception-detection-0007, function-calling-test-0-alarm-...
│   ├── task.toml                  # schema 1.3, separate verifier, artifacts answer.txt + function_calls.jsonl
│   ├── instruction.md             # pipeline messages + where to write the answer
│   ├── environment/
│   │   ├── Dockerfile             # python:3.12-slim + call_function
│   │   ├── task.json              # exact pipeline messages (used by the parity agent)
│   │   ├── functions.json         # tool schemas (function_calling) or []
│   │   └── call_function
│   ├── solution/
│   │   └── solve.sh               # oracle answer (+ oracle function calls)
│   └── tests/
│       ├── Dockerfile             # pinned scorer deps, nltk data, PEDANT models
│       ├── test.sh
│       ├── score_task.py          # reads /app/answer.txt, writes reward
│       ├── cava_score.py          # port of process_record scoring
│       ├── offline.py
│       ├── upstream_function_calling.py
│       ├── upstream_utils.py
│       └── record.json            # the CAVA record (labels, kwargs, gold parse)
```

Adapter code:

```
src/cava/
├── README.md
├── adapter_metadata.json
├── parity_experiment.json
├── pyproject.toml
├── run_cava.yaml
├── prepare/                       # data preparation (not needed to generate tasks)
│   ├── prepare_manifests.py
│   ├── make_parity_ids.py
│   ├── fetch_scorer_resources.py
│   ├── mmif_oracle.py
│   └── validate_oracles.py
├── parity/
│   ├── summarize.py               # per-subtask scores (mean ± SEM) from Harbor job dirs
│   └── docker_negatives.py        # Harbor reward vs scorer on oracle/empty/wrong submissions
└── src/cava/
    ├── adapter.py
    ├── main.py
    ├── subtasks.py
    ├── pipeline_agent.py
    ├── manifests/                 # <subtask>.jsonl: record, transcript, oracle
    ├── data/                      # functions.json, parity_ids.json
    ├── scoring/
    └── task-template/
```

## Run Evaluation / Harness

### Running with Datasets Registry

```bash
# Use oracle agent (reference solution)
uv run harbor run -d cava/cava

# Use your specified agent and model
uv run harbor run -d cava/cava -a <agent_name> -m "<model_name>"
```

### Using Job Configurations

```bash
# From src/cava, after generating ../../datasets/cava
uv run harbor run -c run_cava.yaml                              # oracle
uv run harbor run -p ../../datasets/cava -a codex -m "openai/gpt-5-mini"
uv run harbor run -p ../../datasets/cava -a cava.pipeline_agent:CavaPipelineAgent -m "openai/gpt-4o"
uv run harbor job resume -p /path/to/jobs/directory
```

### Running Individual Trial

```bash
uv run harbor trial start -p ../../datasets/cava/<task_id>
uv run harbor trial start -p ../../datasets/cava/<task_id> -a <agent_name> -m "<model_name>"
```

## Usage: Create Task Directories

```bash
cd src/cava
uv sync
uv run cava --output-dir ../../datasets/cava
uv run cava --split parity --output-dir ../../datasets/cava-parity   # parity subset only
```

Available flags:
- `--output-dir` — directory to write generated tasks (defaults to `datasets/cava` at the repo root)
- `--limit` — generate only the first N tasks
- `--overwrite` — overwrite existing tasks
- `--task-ids` — only generate these task ids
- `--subtasks` — subset of the five subtasks
- `--split` — `full` (default) or `parity` (the subset in `data/parity_ids.json`)
- `--manifest-dir` — read manifests from another directory

The tasks are generated from the manifests in `src/cava/manifests/` (one `<subtask>.jsonl` per subtask, with each record, its transcript, and its oracle answer). They are built once with `prepare/prepare_manifests.py` and committed, so `uv run cava` needs no audio, API key or network. They were built on 2026-10-13 (1,522 audio minutes; every record has a non-empty transcript).

Rebuilding the manifests (needs `OPENAI_API_KEY` for the transcripts, a CAVA checkout, and the extracted STOP dataset for function calling):

```bash
# the two extras are resolved separately (numpy 2 for pyarrow vs the scorer's numpy<2)
uv sync --extra prepare
ARGS="--cava-repo /path/to/CAVA --out src/cava/manifests --cache-dir /path/to/cache --stop-root /path/to/stop_data"
uv run python prepare/prepare_manifests.py $ARGS --asr measure   # audio minutes + cost bound, no API calls
uv run python prepare/prepare_manifests.py $ARGS --max-usd 8     # needs OPENAI_API_KEY; all 3,671 records cost $4.04
uv sync --extra score
uv run python prepare/fetch_scorer_resources.py   # nltk data + pinned PEDANT models (offline.py blocks downloads)
uv run python prepare/validate_oracles.py --manifests src/cava/manifests   # every oracle must score 1
```

## Comparison with Original Benchmark (Parity)

Parity has not been run yet; the plan below needs sign-off from the adapters team.

**Docker checks (done, no LLM).**

- Oracle: all 3,671 tasks reach reward 1 under `harbor run -a oracle` (Docker 29.1.3, Harbor 0.24.0, 0 exceptions): deception 151/151, Jeopardy 1000/1000, MMIF 1000/1000, function calling 1000/1000, jailbreak 520/520. One trial was interrupted mid-verifier by a manual stop, left no reward and no exception, and reached reward 1 when re-run alone.
- Negatives: `parity/docker_negatives.py` runs 96 variant tasks (6 seeded records per subtask; oracle, empty and wrong answers, plus no-call and extra-call submissions for function calling) through `harbor run`. Every Harbor reward equals the vendored scorer's score for the same submission (96/96). Wrong answers score 0 except where the upstream scorer accepts them: 4/6 Jeopardy "What is a banana?" (PEDANT, see Notes), 1/6 function calling whose single `get_weather` call matches the gold count, and 1/6 MMIF "ok".

**Scorer check (done).** Re-scoring the prediction files committed to CAVA@1af23b1 with `scoring/cava_score.py` gives exactly the scores recomputed from those files with upstream's `process_record` logic. The published table differs slightly: deception 14.5% there vs 22/151 = 14.57% here, audio function calling 24% vs 24.1%; the published Jeopardy number is a latency win rate, not the correctness shown here, and MMIF is left out because its upstream scoring is random (see Notes & Caveats).

| Subtask | System | Score |
|---|---|---|
| function_calling | pipeline (gpt-4o-mini-transcribe → gpt-4o) | 27.0% (270/1000) |
| function_calling | gpt-4o-audio-preview | 24.1% (241/1000) |
| deception_detection | pipeline | 14.6% (22/151) |
| jailbreak (ASR) | pipeline / gpt-4o-audio-preview / gemini-2.0-flash-exp | 79.0% / 68.3% / 79.2% |
| jeopardy (PEDANT correctness) | pipeline / gpt-4o-audio-preview / gemini-2.0-flash-live | 96.9% / 97.1% / 94.0% |

**Agent parity (planned, Scenario 3).**

| Agent | Model | Metric | Number of Runs | Dataset Size | Original Benchmark Performance | Harbor Adapter Performance |
|-------|-------|--------|----------------|--------------|--------------------------------|----------------------------|
| cava-pipeline@1.0.0 | gpt-4o | per-subtask score (%) | 3 | 551 (parity subset) | TBD | TBD |

The original side runs a fork of CAVA@1af23b1 (to be published before parity; link will go in `original_parity_repo`) with these changes: (1) records and transcripts come from `src/cava/manifests/<subtask>.jsonl`, restricted to `data/parity_ids.json`, so both sides see the same records (Werewolf audio source, the committed STOP set) and the same text, and the STT step returns the manifest transcript instead of calling the API; (2) the MMIF kwargs are merged and (3) langdetect is seeded, exactly as in `scoring/` here; (4) the Jeopardy TTS call is skipped while its speech-output prompt is kept (scoring reads only the text, the Harbor side has no TTS, and upstream a failed TTS call leaves the result wrapped as `(text, False)`, on which the output processor's `.strip()` raises); (5) scoring uses the verifier's pinned scorer stack (same package versions, PEDANT model hashes and nltk data). Each run uses a different `--cache-seed`, so every run makes fresh LLM calls instead of hitting the disk cache; `--disable-cache` must not be used, because the pipeline's `(text, success)` return value is only unwrapped by the cache decorator. Both sides use the same dated model snapshot (to be fixed before the runs; `gpt-4o` is a moving alias) and the same `openai` SDK version. The Harbor side runs `CavaPipelineAgent`; both sides use the same model, 3 runs each. The parity subset (`data/parity_ids.json`, `prepare/make_parity_ids.py`, seed 20261011) is all 151 deception items plus 100 seeded items from each other subtask. A standard terminal agent (codex) is also run on Harbor to show the tasks work for general agents.

```bash
# Original side: CAVA fork (cached transcripts, parity ids, MMIF kwargs fix), per run r in 1..3
for task in deception_detection jeopardy multimodal_instruction_following function_calling jailbreak; do
  python src/cava/inference.py --task $task --cache-seed parity-run-$r \
    --models pipeline_gpt-4o_gpt-4o-mini-tts_gpt-4o-mini-transcribe
done
# Harbor side (from src/cava)
uv run cava --split parity --output-dir ../../datasets/cava-parity
uv run harbor run -p ../../datasets/cava-parity -a cava.pipeline_agent:CavaPipelineAgent -m openai/gpt-4o
# per-subtask scores (Harbor's own job mean mixes the five metrics), runs = job dirs
uv run python parity/summarize.py --split parity jobs/<run1> jobs/<run2> jobs/<run3>
```

## Notes & Caveats

- **Transcript variant, not audio.** Agents read the pipeline transcript, so scores measure CAVA's STT → LLM pipeline setting, not end-to-end audio models. Following the MMAU adapter precedent, the transcript step is fixed and shared by both parity sides.
- **Subtasks not included.** `tone_aware_reply`: the LLM-judge code is not public ([CAVA issue #36](https://github.com/SALT-NLP/CAVA/issues/36)), and the repo fallback is exact string match. `pronunciation_*`: needs speech output and an audio judge. Jeopardy **latency win-rate**: defined by wall-clock latency against other systems; only the PEDANT correctness part is used. `next_speaker`, `speaker_diarization`, `emotion` (gated `WillHeld/EmoCF`), `deception_vote_prediction`, `transcription`, `jailbreak_base`: not in this version.
- **Jeopardy is near saturation, and its scorer is lenient (upstream behavior, kept).** Correctness is 94–97% for all published systems. PEDANT (`qa-metrics` 0.2.32, called as in upstream `utils.get_pedant_score`) also accepts many answers that only share the Jeopardy phrasing: over the 1,000 records, the constant answer "What is a banana?" scores 76.6% (766), "What is it?" 71.9%, and "Who is he?" 27.0%, while "banana" scores 0%. The adapter keeps upstream's scorer so that scores stay comparable with CAVA and parity measures the same quantity; read Jeopardy scores against this constant-answer baseline.
- **Constant-answer baselines** (upstream scorers, all records; useful floors for reading scores): deception "None" 11.9% (18/151; the committed pipeline predictions score 22/151 = 14.6%); Jeopardy "What is a banana?" 76.6%; instruction following "OK." 38.9% (many single instructions, such as lowercase or no-comma rules, are met by any short reply); function calling with no calls 0%; jailbreak with a constant refusal 100% refusal, i.e. 0% ASR (refusing everything is the intended optimum of that subtask).
- **Upstream nondeterminism: unseeded langdetect (fixed symmetrically).** IFEval's language checks call `langdetect.detect`, which is random unless seeded; a short response to a `response_language` item passed 293 of 300 identical scoring calls. `scoring/offline.py` sets `DetectorFactory.seed = 0`.
- **Upstream bug: MMIF scoring is random for 516/1000 items (fixed symmetrically).** CAVA appends one dict per kwarg to `kwargs`, but IFEval reads only `kwargs[0]` for the single instruction. For `number_sentences`, `number_words`, and `letter_frequency`, the missing `relation`/`letter` are re-drawn at random on every scoring call. The adapter (and the parity fork) merge the kwargs into one dict.
- **Upstream data mismatch: Werewolf audio vs labels.** `run_werewolf_tasks.sh` downloads `WillHeld/werewolf`, but `data/Werewolf/werewolf.jsonl` was built from `mikesun26card/werewolf_audio_dataset`. The adapter uses the latter and checks player names, voting outcome and end roles row by row.
- **Function calling uses the 1,000 STOP records of the committed pipeline and audio prediction files at `1af23b1`** (identical in both), not a re-sample. The metric is upstream's: the per-function call counts must match the gold parse; arguments and call order are not checked.
- **Gold intents without a declared function.** 547 of the 1,000 STOP gold parses contain an intent that has no schema among the 62 declared functions (`get_time` 252, `get_contact` 176, `get_todo` 112, `get_recurring_date_time` 109, `get_location_home`/`_work`/`_school` 55, `get_event_attendee` 2). `function_counts_match` requires every intent to be called the right number of times, so those records can only be solved by calling an undeclared name. Upstream's tool loop records whatever name the API returns without checking it (`inference.py` `process_with_openai_pipeline`), and `call_function` does the same, so the oracle can reach every record. In practice the committed gpt-4o pipeline predictions never use an undeclared name (0 of 1,143 calls), so these records are effectively unsolvable for API tool calling; a terminal agent could call such a name, which upstream's code would also have recorded.
- **Function-call log for terminal agents.** Upstream grades the calls the model emitted through the API, so extra or wrong calls count. Here `call_function` appends to `/app/function_calls.jsonl` in the agent's sandbox and the verifier grades that file, so a terminal agent can delete or rewrite calls before finishing, or write the file without calling. Terminal-agent scores are therefore a function-call-list prediction, not the upstream tool-loop setting. The parity agent writes exactly the calls the model emitted.
- **Aggregation.** Each subtask is a separate metric (accuracy, PEDANT correctness, instruction adherence, call-count match, refusal). Harbor's job-level mean over a combined dataset mixes them and is not a CAVA number; use `parity/summarize.py`, which groups trials by subtask, checks the denominators, reports jailbreak as ASR, and treats a trial without a reward as an infrastructure failure (it stops, or with `--allow-missing` reports the trial and leaves it out of the denominator) rather than a zero.
- **Response cache.** Upstream caches API responses on disk (`diskcache`, 30 days) keyed on audio, prompt and model, so repeated runs would return copies; the parity fork passes a different `--cache-seed` per run.
- **PEDANT downloads.** qa-metrics re-downloads its models from the mutable `main` branch on every init and fetches nltk data at import. The verifier bakes in the pinned models instead (identical to `main` as of 2026-10-11) and blocks downloads.

## Installation / Prerequisites

- Docker installed and running.
- Harbor installed and working (see main repository README).
- Python environment with dependencies:
  ```bash
  cd src/cava
  uv sync
  ```
- API keys for the agents/models you run (e.g. `OPENAI_API_KEY`).
- Rebuilding manifests only: a CAVA checkout, `OPENAI_API_KEY`, and the 1,000 STOP test wavs. They can be pulled out of the 51 GB tarball without storing it: list `./stop/<filename after stop_data/stop/>` for each record in a members file, then `curl -sS https://dl.fbaipublicfiles.com/stop/stop.tar.gz | tar -xz -T members.txt`.

## Troubleshooting

- `RuntimeError: PEDANT model ... has sha256 ...`: the verifier image has unexpected PEDANT models; rebuild it (`force_build: true`).
- `LookupError` from nltk in the verifier: an nltk resource is missing from the image; the Dockerfile smoke test should catch this at build time.
- `function_calling` tasks with reward 0 and an empty `function_calls` list in `/logs/verifier/grading_details.json`: the agent never ran `call_function`.

## Citation

```bibtex
@misc{cava2025,
  title = {CAVA: Comprehensive Assessment of Voice Assistants},
  author = {Held, Will and Ryan, Michael J. and Shrivastava, Aditya and Khan, Ali Sartaz and Ziems, Caleb and Li, Ella and Bartelds, Martijn and Sun, Michael and Li, Tan and Gan, Woody and Yang, Diyi},
  year = {2025},
  url = {https://talkarena.org/cava},
  howpublished = {\url{https://github.com/SALT-NLP/CAVA}},
  note = {A benchmark for evaluating large audio models (LAMs) capabilities across six domains: turn taking, instruction following, function calling, tone awareness, safety, and latency}
}
```

## Authors & Contributions

This adapter is developed and maintained by [Zineng Tang](mailto:terran@berkeley.edu).

**Issues and Contributions:**
- Submit Issues and Pull Requests to the main repository
- Follow the project's coding style and commit guidelines

## Acknowledgement

> API inference compute for running parity tests is generously supported by [2077AI](https://www.2077ai.com/) (https://www.2077ai.com/).
