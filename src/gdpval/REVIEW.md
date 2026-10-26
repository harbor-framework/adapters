# GDPval Docker review — 2026-10-23

> Historical review of the first migration. The two security findings below are
> updated in [SECURITY.md](SECURITY.md) (2026-10-24). “Fixed” in the tables here
> means the first review patch, before separate verifier environments.

The three-task Docker smoke passes. **Formal acceptance is blocked by grader
mutability and public Gold access.** No model evaluation, parity experiment,
publication, commit, push, or merge was performed.

## Scope and evidence

- Contract v1, repository base `cfe10f29e1cd8dfeac70381f6547c006dcf8437b`.
- Reviewed the repository `review-adapter` skill, adapter guide, and workflow
  grading-integrity requirements. This is a focused runtime/security review;
  historical parity links/results were not independently revalidated.
- Upstream PR #1384 head `d935522f2837ba4a05f862741aa014f9cd78b151`.
  Local branch: `feat/gdpval-adapter`; implementation is uncommitted.
- Dataset: `openai/gdpval`, train, cached revision
  `11e7900cdcac61bc4daf59e65feb238acda98fbf`. The original 185 generated tasks
  remain unchanged. Three review tasks were regenerated under `tmp/gdpval-review/`.
- Runtime: Harbor PyPI 0.23.0, Docker Engine 29.8.2, Linux ARM64 containers,
  Python 3.11. Base image resolved to
  `sha256:b7a9e5f6a93d6d4a31f129bbd4bdee69efccb6ded0fb230d78aafaf37af98377`.
  Docker installed LiteLLM 1.106.2 and pypdf 6.21.2 from floating requirements.
  No shared Harbor code or other adapter was changed.

Selection was fixed before results: the first task in sorted UUID order with only
PDF, DOCX, or XLSX outputs. These cover three extraction paths; they do not cover
multiple deliverables, images, slides, audio/video, or the oversized external asset.

| Type | Task ID | Deliverable | Original Oracle | Fixed Oracle | Fixed NOP |
| --- | --- | --- | --- | --- | --- |
| PDF | `0112fc9b-c3b2-4084-8993-5a4abb1f54f1` | `mTBI SOAP.pdf` | 1 | 1 | 0 |
| DOCX | `01d7e53e-0513-4109-a242-8ccaf442cd21` | `Recreare_RecFit_Contract-5.docx` | 1 | 1 | 0 |
| XLSX | `02aa1805-c658-4069-8a6a-02dec146063a` | `Illinois Project Water Wells.xlsx` | 1 | 1 | 0 |

All nine real Harbor trials above finished without exceptions. Compose overlays
merged successfully; the entrypoint installed OUTPUT rules with NET_ADMIN; reference
files were present for the DOCX task. Every Oracle result used the byte-match
shortcut and made no judge request. This proves packaging/copy/runtime behavior,
not the judge's ability to assess a valid independent submission.

Artifacts below are relative to the repository root and Git-ignored:

- `tmp/gdpval-review/jobs/{upstream-oracle,fixed-oracle,fixed-nop}/`: real Harbor
  configs, per-trial results, verifier logs, rewards, and terminal job states.
- `tmp/gdpval-review/{original-controls,final-controls}/report.json`: per-task
  Docker controls, image IDs, agent surface, firewall rules, and tamper probes.
  Per-case logs and local fake-service requests are stored alongside the reports.
- `tmp/gdpval-review/jobs/fault-classification/`: two diagnostic copies of the PDF
  task with intentionally corrupted Oracle output and an injected judge exception.
  Original: valid reward 0. Fixed: no verifier result, `RewardFileNotFoundError`.
  Harbor's reward histogram contains only the original zero; the fixed attempt is
  in exception statistics. Do not interpret the job's aggregate mean alone.
- `tmp/gdpval-review/public-gold-results.json`: three HTTP 200 downloads from a
  fresh container, each with SHA-256 identical to the corresponding Gold file.
- `tmp/gdpval-review/reference-gold-audit.json`: no selected reference file is a
  byte-identical Gold copy. This does not rule out semantic answer leakage.

## Reproduced findings and corrections

### High — judge failures and invalid responses became valid zeros (fixed)

Source: `src/gdpval/task-template/tests/test.sh`, original judge/error branches;
`rubric_judge.py::_normalize_judge_result`. This violates the skill's requirement
to keep infrastructure failures out of the valid-score denominator.

An injected HTTP 401 returned exit 0/reward 0 on all three original tasks. A judge
message containing `{}` also returned reward 0. Unknown winner strings could be
accepted through substring matching, and missing scores defaulted to Gold wins.

The verifier now exits nonzero, removes both reward formats, and writes
`/logs/verifier/error.json` when the judge or result parser fails. Tracebacks remain
in verifier stdout/stderr logs. Missing Gold metadata/files also fail unscored.
Recognized winners retain 1/0.5/0; score-only 0/0.5/1 compatibility is retained.
Unknown/missing winners and invalid fallback scores fail instead of becoming 0.
All task prompts, rubrics, judge messages, and normal reward mappings are unchanged.

### High — stale reward.json overrides reward.txt (fixed for this path)

Source: `test.sh` startup; Harbor `Verifier.verify()` prefers reward.json.
A prewritten `{"reward":1}` survived the original verifier's missing-output
reward.txt=0. Harbor would prefer the forged JSON. Startup now removes both reward
formats, previous judge output, and previous error state. Docker checks confirm
missing output produces only reward.txt=0. This closes a specific path; it does
not solve root-level tampering.

### High — Gold symlink receives an exact-match pass (fixed for this path)

Source: `test.sh` existence and byte-match checks. A candidate path symlinked to
`/tests/gold/<name>` received 1 on all three original tasks after tests were
uploaded. Fixed checks reject the symlink as an invalid submission with reward 0.
Python `-I` also prevents PYTHONPATH/current-directory imports from controlling the
judge. Neither change establishes a strong boundary against a root agent.

### Blocking — agent can modify the grading runtime (unresolved)

Source: `environment/Dockerfile` has no unprivileged USER; `task.toml` does not set
an agent user. The agent and verifier share a mutable container. All six
original/fixed security probes observed uid 0 and a writable Python interpreter.
Replacing `/usr/local/bin/python3` with a wrapper that writes reward 1 made an
empty `/app` pass in both variants. The probe modified only a disposable container;
no host path was mounted and the container was removed afterward.

The base image did not expose `/tests` or `/solution` before upload. Nevertheless,
root can persist processes or alter interpreter/dependency state before grading.
The workflow's grading-integrity invariant therefore fails. A later design must
use an enforceable user/permission boundary or a fresh verifier environment with
only submitted artifacts transferred. Validate agent installation, artifact access,
logs, and verifier permissions under that design; changing a shell flag is insufficient.
No framework or agent-user contract was changed in this review.

### High — public Gold remains reachable (unresolved)

Source: `environment/restrict-network.sh` permits arbitrary HTTP/HTTPS, and tasks
allow internet access. In fresh containers using the actual entrypoint, all three
pinned public Gold URLs were reachable without credentials and downloaded bytes
matched local Gold. The oracle/test files are absent from the initial image, but
network-accessible answers remain available. The probe supplied known source URLs;
it does not prove a model can independently discover them from the task prompt.

Before release, define the required agent internet access and enforce the chosen
answer-source restriction outside agent control. NET_ADMIN/root makes the present
iptables policy unsuitable as a security boundary. Removing source identifiers
alone cannot prevent recognition of public prompts and filenames. A generic network
cutoff may affect tasks and agent setup, so no arbitrary restriction was added.

### High — exact match differs from pairwise tie (retained upstream semantics)

Source: `test.sh` exact-match branch versus `rubric_judge.py` judge instructions.
Byte-identical Gold receives 1; the judge defines approximately equivalent output
as tie/0.5. Appending a harmless trailing newline to each valid file bypassed the
shortcut; the local fake service's tie produced 0.5 on all three types. This proves
branch sensitivity, not what a real judge would decide. The shortcut was retained
for upstream fidelity. Review whether it applies only to Oracle controls before
using this implementation for score comparisons. ADP-PARITY remains unproven.

## Docker control results

The local fake service runs inside the container at 127.0.0.1:3000, with a dummy
key. It records SDK requests and returns fixed messages. It never calls a model.
Each row below was checked for all three tasks, original and fixed:

| Condition | Original | Fixed |
| --- | --- | --- |
| Missing output / wrong filename | 0 | 0 |
| Exact Gold via Oracle solve.sh | 1 | 1 |
| Valid file + trailing newline; local response tie | 0.5 | 0.5 |
| Invalid bytes; local response Gold wins | 0 | 0 |
| HTTP 401 | 0, exit 0 | no reward, error, exit 1 |
| Judge message `{}` | 0, exit 0 | no reward, error, exit 1 |
| Stale reward.json=1 plus missing output | JSON remains, takes precedence | JSON removed, 0 |
| Candidate symlink to Gold | 1 | 0 |
| Root replaces interpreter, no deliverable | 1 | 1 — blocker |

These controls establish file routing, extraction/request transport, normalization,
and failure bookkeeping. A fake response that says Gold wins cannot prove the
verifier understands an invalid document. Semantic recognition of arbitrary valid
or invalid deliverables remains unverified because model calls were prohibited.

## The original 13 lint findings

- Four mechanical fixes: two I001 import layouts, one RUF012 ClassVar annotation,
  and one B033 duplicate `1`/`1.0` set element. No runtime semantics changed.
- One diagnostic fix: S112 now logs a failed Office XML part before continuing.
- Eight BLE001 catches were deliberately retained with individual `noqa` comments:
  four download/source fallbacks and four best-effort extraction/dependency
  fallbacks. Narrowing them only to satisfy lint could change which source files
  are skipped or which content is judged. Their errors remain a disclosed fidelity
  limitation; no global lint suppression was added.

Run Ruff inside `src/gdpval/` so its package import classification matches the
adapter. The full adapter source and tests pass. Four offline regression tests,
Python compilation, wheel/sdist build, and the structural validator pass. The
validator still has six historical one-run warnings (31 pass, 0 error); those
records do not satisfy ADP-PARITY or ADP-STATS.

## Reproduction and remaining scope

From repository root, generate a separate review set:

```bash
uv run --project src/gdpval gdpval --output-dir tmp/gdpval-review/fixed-tasks \
  --task-ids 0112fc9b-c3b2-4084-8993-5a4abb1f54f1 \
  01d7e53e-0513-4109-a242-8ccaf442cd21 02aa1805-c658-4069-8a6a-02dec146063a
uv run --project src/gdpval --with harbor==0.23.0 harbor run \
  -p tmp/gdpval-review/fixed-tasks -a oracle -n 1 --n-concurrent 1 \
  --jobs-dir tmp/gdpval-review/jobs --job-name reproduce-oracle
uv run --project src/gdpval --with harbor==0.23.0 harbor run \
  -p tmp/gdpval-review/fixed-tasks -a nop -n 1 --n-concurrent 1 \
  --jobs-dir tmp/gdpval-review/jobs --job-name reproduce-nop
uv run --project src/gdpval python src/gdpval/tests/docker_review.py \
  --tasks-root tmp/gdpval-review/fixed-tasks \
  --artifacts tmp/gdpval-review/reproduced-controls --expect hardened
```

Use fresh output/job names for a new attempt; retain previous attempts. The Docker
script deliberately demonstrates the root vulnerability and removes only its own
containers. It leaves images and logs for inspection. `--expect upstream` supports
reproducing controls on an unmodified upstream task set.

Next work: decide verifier isolation and internet boundaries first; then validate
that malformed document extraction, Office layout loss, audio/video metadata-only
judging, truncation, prompt injection, fixed Gold-first order, and judge credentials
meet the intended benchmark contract. Pin runtime dependencies and dataset/assets.
Full Oracle coverage, paid semantic judge checks, historical parity denominators,
and matched expert/model parity remain outside this review. Do not treat these
three successful Oracle tasks as acceptance of the other 182 tasks.
