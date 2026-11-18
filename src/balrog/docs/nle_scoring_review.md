# NLE scoring review at the pinned BALROG revision

Status: WIP source review and saved offline runtime evidence. No upstream issue
was posted, no score was changed, and no model parity is claimed. The committed
[NLE audit summary](../validation/diagnostics/nle_ceiling.json) records the source
bound and proof results; [baseline results](../validation/baseline.json) cover
the five fixed diagnostic tasks. Full local research jobs are not uploaded.

## Native metric and the full-score blocker

The source revision is BALROG
`b7afe79e3e4265811cfa985ed7c95c4d1a11e3f5`, with `balrog-nle==0.9.0`.

The code path is:

1. `balrog/environments/nle/nle_env.py` constructs `NetHackChallenge-v0`.
2. `NLELanguageWrapper` obtains `Progress()` from `get_progress_system`.
3. Every action invokes `Progress.update` in
   `balrog/environments/nle/progress.py`.
4. The adapter reports the unchanged `env.get_stats()["progression"]`.

`Progress.update` has two assignments that can increase progression. It builds
an `Xp:{experience_level}` key and a `Dlvl:{depth}` key, then keeps the highest
matching value from `achievements.json`. Progression starts at zero. The done
branch records an end-reason string; it does not assign a terminal success score.
The native `info["is_ascended"]` event is not used by this scoring function.

The table also contains `Astral Plane` with value `0.8745866562925501` and
`You ascend t` with value `1.0`. Neither key can be produced by the implemented
`Xp:*`/`Dlvl:*` key construction. The largest value among all keys the code does
construct is `Dlvl:50 = 0.8067964442444019`.

Consequently, induction over `Progress.update` gives an upper bound of
`0.8067964442444019` for this implementation. This is a **source-derived upper
bound**, not a claim that a test run reached dungeon level 50. A full-score 1.0
NLE oracle cannot be honestly certified at this source pin. An actual ascension
trajectory has not been generated here.

Immutable source references:

- [Native progression code](https://github.com/balrog-ai/BALROG/blob/b7afe79e3e4265811cfa985ed7c95c4d1a11e3f5/balrog/environments/nle/progress.py)
- [Achievement table](https://github.com/balrog-ai/BALROG/blob/b7afe79e3e4265811cfa985ed7c95c4d1a11e3f5/balrog/environments/nle/achievements.json)
- [Language wrapper integration](https://github.com/balrog-ai/BALROG/blob/b7afe79e3e4265811cfa985ed7c95c4d1a11e3f5/balrog/environments/nle/base.py)

The appropriate review decision is to agree with the maintainers either to
accept explicitly documented partial-progression NLE references, or to fix the
upstream scorer and use the same newly pinned source on both parity sides.
An ascension fix should explicitly handle the trustworthy native ascension
event and test it, while also deciding whether the unused Astral Plane entry
belongs in the intended metric. The Harbor adapter must not independently
rescale partial scores or replace progression with a success flag.

## Genuine nonzero reference evidence

The dataset selection remains the native task `NetHackChallenge-v0` with the
predetermined seeds 0..4. No seed or task was removed, replaced or added based
on success. Native settings remain `max_episode_steps=100000`,
`no_progress_timeout=150`, `character="@"` and `skip_more=True`.

A deterministic reference controller uses only actions accepted by the native
language action space. On seed 1 it reaches dungeon level 2 after **130 actions**
and produces native progression **0.015392269075361172**, exactly the `Dlvl:2`
table value. Two fresh original-environment executions have identical initial
observations, actions, transition hashes, rewards, termination flags and final
stats. The reference intentionally stops after this partial-progress event; it
is not a full episode oracle, full benchmark performance estimate, or parity
experiment. The remaining four instances keep their eight-action deterministic
diagnostic references.

`fixtures/nle_manifest.json` labels all five as
`diagnostic_not_full_oracle`, keeps `oracle: null`, and stores the native expected
progression and each transition. The separate adapter `Episode` check also
reconstructs the environment and independently replays the accepted actions
before returning the original progression. The reference does not mutate game
state, edit observations, inject rewards, or shorten the task's native budget.

All five separate Harbor diagnostic trials completed with zero exceptions and
verified replay. The [saved validator reports](../validation/validator_reports.json)
distinguish that Harbor evidence from the native checks. Neither establishes
full-score oracle availability or model parity.

## Related MiniHack quirk retained unchanged

The same source file's `BaseProgress.update` sets progression to 1.0 only when
the returned reward is at least 1.0. MiniHack can report `TASK_SUCCESSFUL` with
reward 0.99 when `penalty_step=-0.01` applies to a fast character's action that
does not advance game time. In MazeWalk-15x15 seed 1, a nine-action staircase
solution demonstrates exactly this outcome: terminal success with progression
0.0. Two additional legal movement actions that return to the start produce an
eleven-action tape whose terminal reward and native progression are both 1.0.
Both are original game outcomes, not adapter errors. Full MiniHack references
are accepted only after achieving native progression 1.0 and passing independent
original and adapter replay checks. The final correctly seeded dataset has
39 full oracles and one separately labeled Boxoban budget diagnostic; see
`minihack_seed_and_budget_review.md`.

## Independent source and runtime audit, 2026-11-17

The saved source audit checks every scoring write and 2,550 boundary inputs.
It confirms the source-derived bound above; it does
not demonstrate that any fixed game seed attains that bound. A separate,
**unapplied** patch recognizes only a terminal native `info["is_ascended"]`
event. Ten candidate assertions pass, including 5,100 non-ascension cases
whose results remain identical. Text mentioning ascension, large rewards,
and nonterminal flags do not manufacture success. The patch leaves the
separate MiniHack `BaseProgress` class unchanged. The
[committed audit summary](../validation/diagnostics/nle_ceiling.json) retains
these results and source hashes. The local candidate patch and full research
scripts are not packaged as a production fix; neither scorer nor source pin
has changed. These are saved audit results, not a claim that a reviewer has
reproduced the research checks from this checkout alone.

A fresh Docker run rechecked all five existing references and all 162 native
transitions. No ascension occurred. The fixed roles are Priest, Samurai,
Healer, Monk and Knight. The original action interface accepts the commands
needed by ascension strategies, but that does not establish that a particular
external bot works here. The public bots reviewed do not provide validated
winning trajectories for these five seeds under the pinned dependencies,
100,000-action limit and 150-action no-progress timeout.

There are still two distinct requirements: agree on the scorer's handling, and supply
actual successful trajectories if full NLE oracles are required. A tested
scoring patch alone does not satisfy the second requirement. The investigation
used no model API calls; no upstream scoring issue or fix has been submitted.

## Requested maintainer decision

Should we propose and pin an upstream ascension-scoring correction on both
parity sides, or is explicitly documented partial-progression reference evidence
acceptable for this environment? A correction would still leave us responsible
for genuine successful trajectories for all five selected seeds if full oracles
remain required. We will not substitute the theoretical score bound, a fabricated
ascension event, or a rescaled partial score for those trajectories.
