# Crafter replay, scoring and oracle review

Status: WIP proposal for maintainer review. The native simulator and metric are
unchanged, but the adapter's explicit live-state scoring exception has not been
approved. The baseline has ten partial references and no complete Crafter
oracles. Model parity and Daytona validation have not run.

## Source scope and replay limitation

The adapter pins BALROG `b7afe79e3e4265811cfa985ed7c95c4d1a11e3f5` and
[`crafter==1.8.3`](https://pypi.org/project/crafter/1.8.3/), constructor seeds
0–9, and the original 2,000-action budget. Native progression is the number of
unlocked achievements divided by 22. A partial score is never converted to a
binary success.

In the installed Crafter package, `World._chunks` stores sets of objects whose
hashes depend on object identity. `Env._balance_object` iterates one such set
to build a creature list and selects an index with the seeded world RNG. The
same index can therefore select a different creature in a fresh world. Setting
Python/NumPy seeds or `PYTHONHASHSEED` does not fix object identities. The
adapter does not sort these sets or modify native game code.

A local native-only audit ran three untouched worlds with seed 0 and the same
legal actions. Initial observation hashes matched. Object selections first
differed at raw step 10 despite matching random state before and after that
step; one pair's text observations first differed at frame 153, and its native
episodes ended after 180 versus 184 actions. Another pair's observations
happened to match until termination. Thus short replay successes do not prove
deterministic long replay. The [validation index](../validation/README.md) and
[provenance inventory](../validation/provenance.json) identify the saved local
evidence; the full exploratory jobs are not included in this PR.

## Proposed scoring behavior implemented in the adapter

The isolated game service owns the native state and action log. Normal agents
can only read public observations and submit actions. The verifier authenticates
to the protected result endpoint, which finalizes the live episode and attempts
a fresh native replay.

Five environments require successful replay. For Crafter only, an explicit
trajectory, score or termination `ReplayDivergence` permits the original live
game's native progression, with all of these fields present:

```json
{
  "env_name": "crafter",
  "scoring_mode": "authoritative_native_state",
  "replay_verified": false,
  "replay_progression": null,
  "replay_diagnostic": {
    "code": "crafter_native_object_order_nondeterminism",
    "first_divergent_step": 152
  }
}
```

The index above is from a separate 180-action Harbor diagnostic scored at
`2/22`; it is not a universal divergence location. The score never comes from
the agent or from substituting the replay's outcome. Initial-observation
mismatches, invalid scores, network failures and unrelated simulator exceptions
still produce no reward. The verifier checks the explicit diagnostic, bounds
and transition count. Regression checks are in
[`tests/runtime/test_crafter_failure_policy.py`](../tests/runtime/test_crafter_failure_policy.py)
and [`tests/runtime/test_suite_verification.py`](../tests/runtime/test_suite_verification.py).

This preserves the upstream metric but proposes an exception to mandatory
independent replay. Maintainer acceptance is still required; the existence of
the implementation and its tests does not establish acceptance.

## Baseline and remaining controller work

All ten baseline Harbor references completed at `2/22`. Their short traces are
diagnostics, not solutions to all achievements; see the committed
[baseline](../validation/baseline.json) and
[saved validator reports](../validation/validator_reports.json).

Several local adaptive policies achieved isolated full native episodes but
failed to provide reliable completion across the ten fixed seeds. The frozen
four-action tactical policy's complete ten-seed evaluation achieved **0/10**
full successes across 9,791 live actions. Its achievement counts were
`20, 12, 16, 15, 15, 19, 16, 18, 21, 17`; all cases missed `eat_plant`.
Matching immediate-health predictions did not solve farming, rest, resource
recovery or navigation. The [tactical summary](../validation/diagnostics/crafter_tactics.json)
retains the failures rather than selecting successful exploratory episodes.
Improving those policies is our remaining implementation work, separate from
the upstream nondeterminism decision.

Sorting despawn candidates by native creation index was also investigated as
an isolated, unapplied upstream candidate. It changes seeded realizations and
would require a new pin, new fixtures and validation on both parity sides.
No such patch is used by the baseline. This PR does not propose silently making
the Harbor simulator deterministic while leaving the original side unchanged.

## Separate privileged reference prototype

The committed [seed-6 diagnostic summary](../validation/diagnostics/crafter_private_seed6.json)
records a **research-only custom Harbor agent**, explicitly labeled
`PROTOTYPE_PRIVILEGED_ORACLE_NOT_APPROVED`. Its private snapshot transport and
controller are not part of the production task template or ordinary oracle.

In that isolated prototype, the game exposes allowlisted immutable JSON state
through an AF_UNIX socket inside its own container. Filesystem permissions and
Linux peer UID checks restrict access to a separate oracle UID. The controller
does not receive writable native objects or the scoring credential, and it
submits only ordinary public HTTP actions. Snapshot reads were checked not to
change current state, object identities or RNG state. The trusted host installs
the reference files only into the game service and launches the controller with
a clean environment.

Two real Harbor runs used the unchanged seed 6 and native 2,000-action budget:

| Purpose | Reference cap | Executed actions | Native/verifier/Harbor score | Trial exceptions |
| --- | ---: | ---: | ---: | ---: |
| Compatibility smoke | 80 | 80 | 8/22 | 0 |
| Full-budget diagnostic | 2,000 | 725 | 22/22 = 1.0 | 0 |

All 725 live transitions match the authoritative service log. Normal-container
isolation checks passed before and after execution. Docker inspection found no
shared game mounts, host ports or shared PID/IPC namespaces. Both runs nevertheless
report `replay_verified:false`, with the first fresh-replay divergence at action
index 25, and use the same disclosed live-state scoring policy.

This is one successful adaptive live-game episode. It is not deterministic
replay, repeated reliability, ten-seed coverage, the default `-a oracle`
workflow, or model parity. The saved summary and hashes are committed; full raw
jobs, prototype controllers and assets have not been uploaded. It adds **zero**
to the 239 baseline full-score oracles.

## Requested maintainer decision

Can this adapter use the isolated live episode's native score when the explicit
Crafter replay difference occurs, and is a separately isolated adaptive oracle
with privileged read-only state acceptable while normal models keep the
original text-only interface? If an upstream determinism change is preferred,
we would need to agree and pin it on both sides, regenerate the fixtures and
repeat oracle validation before parity. Either route still leaves us responsible
for a reliable reference policy over all ten selected seeds.
