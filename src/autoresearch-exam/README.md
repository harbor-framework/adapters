# AutoResearchExam → Harbor Adapter

## Overview

This adapter converts the 29 [AutoResearchExam](https://benchmarks.bespokelabs.ai/autoresearchexam/)
(ARE) v1.0 tasks into ARE v1.1 Harbor tasks that run with any Harbor agent. The output matches
the published [ARE v1.1](https://github.com/bespokelabsai/AutoResearchExam/tree/v1.1) tasks,
except for the instruction and the oracle script described under Notes & Caveats.

## What is AutoResearchExam?

ARE measures how well an agent does open-ended research. Each task gives the agent a research
problem, data and a 24 hour budget. The agent submits solutions as it goes. Each
submission is scored on a validation split the agent can see and on a private test split it
cannot. Tasks cover model training, algorithms and optimization, data curation, systems
efficiency, evaluation and robustness, AI safety and interpretability. 22 tasks need only CPUs
and 7 need an NVIDIA GPU.

The leaderboard uses v1.0 with the official
[AutoResearchExam-Terminus](https://github.com/bespokelabsai/AutoResearchExam-Terminus) harness,
which runs the research loop as a custom Harbor trial.

## Adapter Features

- Moves the research loop from the harness into the task, so no custom agent or trial is needed.
- Adds a `grader` sidecar with an `are` MCP server (`submit`, `result`, `status`). It scores
  each submission on the validation split and returns the score to the agent.
- Adds a `test-grader` sidecar on a private network the agent cannot reach. It scores the same
  submission on the test split.
- Reuses each task's own environment, data and grading code unchanged. Test-only files are
  removed from the validation grader's filesystem. In 2 tasks both splits come from one
  root-only file, as in v1.0.
- A separate, offline verifier scores the run from the grader's ledger.

## Generated Task Structure

```
autoresearch-exam/<task-id>/
├── README.md                  # task card, unchanged from v1.0
├── task.toml                  # ARE v1.1 settings merged over the v1.0 task.toml
├── instruction.md             # task instruction + research protocol
├── environment/
│   ├── Dockerfile             # agent image, unchanged from v1.0
│   ├── .dockerignore          # keeps the grader context out of the agent image
│   ├── docker-compose.yaml    # main + grader + test-grader
│   └── are-grader-ctx/        # v1.0 tests/ + the grader server
├── solution/solve.sh          # plumbing check (see Notes & Caveats)
└── tests/                     # final verifier: scores the run from the ledger
```

Each trial writes `verifier/reward.json`. `reward` is the test score of the submission with the
best validation score. `auarc` is the area under that score over the 24 hour budget. Both use
each task's own score scale; the
[scoring guide](https://github.com/bespokelabsai/AutoResearchExam-Terminus/blob/main/scripts/custom_harness.md)
maps them to the leaderboard scale. Every submission's scores and times are in the trial's
`artifacts/var/lib/are/ledger.jsonl`.

## Run Evaluation / Harness

From the registry, after publishing:

```bash
harbor run -d bespokelabs/autoresearch-exam -a <agent> -m <model>
```

From generated tasks:

```bash
harbor run -c src/autoresearch-exam/run_autoresearch-exam.yaml
harbor run -p datasets/autoresearch-exam/hicard-latent-encoder -a claude-code -m anthropic/claude-opus-5-5
```

During the run the agent can reach `api.openai.com`, `api.anthropic.com` and the grader. For an
agent that uses another host, add `--allow-agent-host <host>`.

## Usage: Create Task Directories

```bash
cd src/autoresearch-exam
uv run autoresearch-exam --output-dir ../../datasets/autoresearch-exam
uv run autoresearch-exam --output-dir ../../datasets/autoresearch-exam --task-ids hicard-latent-encoder
```

The adapter clones the v1.0 tag of the ARE repository. Pass `--source-dir` to use a local
checkout instead. `--limit` and `--overwrite` are also supported.

## Comparison with Original Benchmark (Parity)

Parity experiments have not been run yet. The plan will be agreed with the Harbor team.

## Notes & Caveats

- **Protocol in the instruction.** The research protocol (submit often, keep improving until the
  budget ends) is appended to `instruction.md`. Published v1.1 passes the same text as a prompt
  template, so the agent sees the same prompt.
- **Oracle.** The tasks are open-ended and have no reference solution. `solve.sh` submits the
  deliverable folder as shipped (empty in most tasks) and waits for both grades. This checks the
  full grading path only. Its reward is usually 0, not 1.
- **Scores can differ from v1.0.** In v1.0 the harness kept the agent working for the full
  budget and paused it during grading. In v1.1 the agent decides when to stop and keeps working
  while a submission is graded.
- **Compute.** The two graders take turns and each uses the task's verifier resources, so plan
  for about twice the CPUs each task requests.
- **GPU tasks** need an NVIDIA GPU and the NVIDIA Container Toolkit. Grading shares GPU 0 with
  the agent. On a host with a spare GPU, set `ARE_GRADER_GPU=1` to give grading its own.

## Installation / Prerequisites

- [Harbor](https://github.com/harbor-framework/harbor) and Docker with Compose.
- [uv](https://docs.astral.sh/uv/) to run the adapter.
- Credentials for your model provider.

## Troubleshooting

- **A submission is refused:** the previous submission is still waiting for its validation
  score. Wait and submit again.
- **Low scores with an agent that stops early:** the agent must keep submitting until the
  budget ends. The protocol in `instruction.md` asks it to.

## Citation

```bibtex
@misc{ramesh2026autoresearchexam,
  author = {Ramesh, Anirudha and
            Devic, Siddartha and
            Garg, Shivank and
            Parulekar, Advait and
            Mahnot, Drish and
            Pimpalgaonkar, Shreyas and
            Suresh, Vishnu and
            Dimakis, Alex and
            Sathiamoorthy, Maheswaran},
  title = {{AutoResearchExam}},
  year = {2026},
  month = sep,
  url = {https://benchmarks.bespokelabs.ai/autoresearchexam/},
  note = {Published September 9, 2026}
}
```

## Authors & Contributions

Adapter built by Anirudha Ramesh (anirudha@bespokelabs.ai), one of the ARE authors.
