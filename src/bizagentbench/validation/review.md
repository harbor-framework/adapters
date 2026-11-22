# BizAgentBench adapter self-review

Verdict: **WIP; offline implementation is reproducible, acceptance remains blocked
by missing live oracle and real-model parity evidence.** This review covers only
the new, uncommitted `src/bizagentbench/` working copy on branch
`bizagentbench-adapter`, based on adapters commit
`543861e1ad298c5d94f2480e9cbad74587041864`. It does not claim a published adapter
revision or immutable GitHub permalink for new files. The source-tree digest in
`summary.json` identifies the inspected local file bytes. No changes to BALROG
were made.

The review standard is adapter contract v1 at that base commit, with automation
skill revision `f2ebf9c297ca57d9b7ce8a046cef4a2e228ca2b2`. The shared guide was read
from its pinned raw URL, together with the base `docs/adapters.mdx`, human guide
and parity diagnostics. Local new code has no public revision permalink; those
source locations are consequently local/unpublished, not fabricated remote links.

| Area | Assessment | Evidence and practical coverage |
|---|---|---|
| Harbor standards | Issues found / incomplete acceptance | CLI, names, authors, README sections, independent project and separate verifier implemented; structural checks pass except the absent parity artifact. |
| Upstream fidelity | Assessed offline; real-provider behavior unverified | Exact official source archive; unmodified `tools.evaluate.run_case`, native HTTPAgent/user and verifier. Full upstream Linux tests pass. |
| Generation | Executed locally | All 50 tasks generated with unique names; every task selects a separate verifier and sidecar-only artifacts. Source/config identities are recorded. |
| Public-tool construction | All 50 tasks pass isolated checks | Every task has a terminal workflow built through public native tools. A separate network-disabled grader reports G/P/F/Strict true for all 50. No success-state or history assignment is used. |
| Agent execution | All 50 scripted native/Harbor controls pass; generalization unverified | All 50 complete verdicts and separate grader rewards match. Per-case evidence and explicit retries are audited in scripted-reference-equivalence.json. Negative controls and the production relay remain covered. No real model or standard CLI agent was evaluated. |
| Grading integrity | Executed locally and inspected | Main stopped before sidecar collection; fresh verifier recomputes native checks. Main-container fake state/reward files are ignored. Public provider-error spoofing is rejected. |
| Model parity | Unverified | No paired real-model runs, sample SEM or range-overlap claim exists. |

## Acceptance blockers

1. **Independent live-customer oracle evidence (specification Step 3) is missing.**
   Public-tool reference construction now covers all 50 tasks, with all G/P/F/Strict
   checks passing in a separate grader. Scripted customer controls replay the actual
   native tools, approval requests, uploads, updates and receipts. The explicit
   50-case selection and complete native/Harbor comparisons are recorded separately
   from `live-llm-validation.json`, which correctly reports zero tasks verified.
   A scripted customer's approval is a real engine action, but its decision is
   prewritten; it does not establish independent model consent or policy compliance.
   Linear trajectories can depend on event ordering and should not be assumed to
   generalize to another customer's actions. Default generated task solutions
   continue to fail unless references are supplied; only the separately named
   scripted datasets use the fixtures. Next evidence is live validation of these
   candidate workflows with the agreed independent customer.

2. **ADP-PARITY / ADP-STATS evidence is missing.** The README correctly reports zero
   real-model runs; `parity_experiment.json` is intentionally absent. This is a real
   acceptance failure, not a validator defect. The two negative controls are two
   different tasks, not two repeated model runs. The positive reference also cannot
   substitute for statistical parity. Exact provider configurations, credentials,
   dated models, a coordinated repetition plan and an exact Harbor source revision
   remain necessary before paid experiments. Follow the symmetric sanity/full/repeat
   order and calculate mean plus sample SEM from raw arrays once runs exist.

3. **Publication and generalization remain unverified.** No registry dataset, adapter
   PR, parity upload or standard CLI-agent experiment was created. Publication was
   outside the authorization for this implementation task. CLI routing instructions
   exist, but that does not prove compatibility or matched performance for Codex or
   another shell agent. Keep that experiment separate from the native HTTPAgent relay.

## Integrity and fidelity findings resolved during implementation

Static inspection exposed an important boundary issue: a public raw provider-response
interface could let an untrusted agent falsely report a provider failure and escape
numeric scoring. The final public route accepts only an assistant message. Only
trusted adapter host code can forward actual provider HTTP statuses and SSE through
Harbor service execution to a sidecar-loopback endpoint. The agent never receives
that channel's file, credential or collection entry point. Both a public HTTP-error
spoof rejection and a genuine trusted-relay HTTP 401 were exercised. The latter
retains native `infrastructure_invalid` with no numeric reward.

Native customer protocol failure and user-provider HTTP failure were also reproduced
on both sides. The fresh grader reports their original classifications and removes
both reward formats; Harbor surfaces a missing-reward error rather than including
these cases as agent zeros. Genuine unsuccessful business controls remain scored
zero. All full-verdict comparisons, including the positive reference, were computed
from collected service evidence rather than agent-authored state.

The first diagnostic incorrectly assumed assistant `###STOP###` text would stop the
native HTTPAgent. That upstream path actually concludes through the customer's
stop signal. The fixture and documentation were corrected without changing the
native orchestrator. Original diagnostic logs were retained; final controls use
`user_stop`. These recoveries are transport diagnostics, not selected model scores.

## Remaining limitations

The full reference work exposed one adapter grading defect: native expense checks
contain tuple-valued payment evidence while the collected JSON contains lists.
Cases 021 and 030 initially produced a false full-verdict mismatch and no reward.
The grader now compares the complete recomputed verdict in its JSON transport
representation. It does not drop fields, alter native evaluation, or accept changed
payment amounts; the regression test covers both transport equality and tampering.
Each initial failure and explicitly selected successful retry remains in the
attempt ledger. The other construction attempts, including a stopped no-event
wait loop, are also retained and are not reported as model trials.

The planner, tool client and interactive exploration entry points do not import
native graders or private contracts. The trusted construction service is a separate
process that accepts only role/tool/arguments requests; offline grading is a later,
separate container operation. This developer process separation is distinct from
the production Docker security boundary and is not presented as a sandbox against
a malicious author with host filesystem access. The authoring service and grader
scripts are never deployed to the main agent. The production boundary remains the
business sidecar, trusted collection and fresh separate verifier.

The host relay buffers SSE before native parsing, so arrival timing differs even
though chunks and errors are preserved. Its finalization watcher cancels the host
provider call when the native deadline wins. Real-provider deadline, overflow and
reasoning compatibility remain unverified. Windows participant-stack tests printed
passing summaries but stalled on process exit; completed Linux tests are the
validation basis. Dependencies and the Python base image are locked; the tested
Harbor distribution exposes version 0.26.0 but no Git SHA. Raw local trial paths,
control results and outstanding work are recorded in `summary.json` and the README.
