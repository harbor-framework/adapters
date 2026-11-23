# NLE AutoAscend v2 validation

The bounded offline controller completed **49,451 accepted BALROG language actions** over the five original fixed seeds. All **5 fresh native-process replays matched every recorded transition**. There were **0 controller errors and 0 ascensions**. The host integrity audit passed and verified **91 protected files unchanged**.

This is research evidence for an adapted controller. It is **not model parity or a complete NLE oracle**, and **no v2 Harbor task replay was performed**. Official oracle fixtures and production code remain unchanged; the proposed scorer patch remains unapplied.

## Actual outcomes

| Seed | Accepted actions | Stop | BALROG progression | Final / maximum depth | Final / maximum XP level | Maximum XP points | Fresh native replay |
|---|---:|---|---:|---|---|---:|---|
| 0 | 10,000 | Controller cap; alive | 0.036887590648350246 | 1 / 1 | 6 / 6 | 336 | 10,000/10,000 exact |
| 1 | 10,000 | Controller cap; alive | 0.036887590648350246 | 1 / 1 | 6 / 6 | 338 | 10,000/10,000 exact |
| 2 | 10,000 | Controller cap; alive | 0.036887590648350246 | 1 / 1 | 6 / 6 | 373 | 10,000/10,000 exact |
| 3 | 10,000 | Controller cap; alive | 0.029108986017138745 | 1 / 1 | 5 / 5 | 254 | 10,000/10,000 exact |
| 4 | 9,451 | Native death: starvation | 0.029108986017138745 | 0 / 1 | 0 / 5 | 238 | 9,451/9,451 exact |

Mean actual BALROG progression was **0.03377614879586564**, across all five seeds without replacement or outcome filtering. This is the benchmark's progression score, not the native NetHack score.

Every run reached at most depth 1 and issued **zero native descend actions** (`>` / key 62). Maximum depth, XP level and XP points scan **all recorded `native_blstats` rows**. Seed 4 starved after 9,451 actions; its terminal status array was zeroed, so its final depth and XP level are 0 while its recorded maxima remain depth 1 and XP level 5. Its native end reason was `DEATH: starved to death.` The other four runs reached the research cap with positive HP and an active native episode. Reaching that cap does not establish native success or termination.

## Wield-confirmation fix and comparison

V1 stopped seed 1 at action 1,140 with an upstream `Inventory.wield` assertion when the observation contained `Hachi drops a crude arrow.` V2 checks the actual inventory annotation for the requested letter before accepting the wield confirmation. The audit verified **seven confirmed events, all in seed 1**, against the inventory and message in the hashed public native observations. No unconfirmed events were recorded.

| Seed | Bot step | Inventory letter | Equipped item confirmed | Observed message |
|---|---:|---|---|---|
| 1 | 1140 | `a` | Yes | Hachi drops a crude arrow. |
| 1 | 1459 | `a` | Yes | Hachi bites the newt.  The newt is killed! |
| 1 | 6242 | `a` | Yes | The wererat misses! |
| 1 | 6370 | `a` | Yes | Hachi bites the dwarf zombie.  The dwarf zombie is destroyed! |
| 1 | 9537 | `a` | Yes | The giant rat is killed! |
| 1 | 9599 | `a` | Yes | The giant rat is killed! |
| 1 | 9604 | `c` | Yes | The coyote is killed! |

All five v2 traces retain their entire corresponding v1 action/transition prefix exactly. This demonstrates recovery past the observed seed-1 assertion with native inventory evidence; it does not establish support for every future inventory interaction or an ascension policy.

| Seed | V1 actions / status | V1 progression | V2 actions / status | V2 progression |
|---|---|---:|---|---:|
| 0 | 2,000 / `controller_cap` | 0.02081163581974355 | 10,000 / `controller_cap` | 0.036887590648350246 |
| 1 | 1,140 / `controller_error` | 0.01847840456172601 | 10,000 / `controller_cap` | 0.036887590648350246 |
| 2 | 2,000 / `controller_cap` | 0.02081163581974355 | 10,000 / `controller_cap` | 0.036887590648350246 |
| 3 | 2,000 / `controller_cap` | 0.02081163581974355 | 10,000 / `controller_cap` | 0.029108986017138745 |
| 4 | 2,000 / `controller_cap` | 0.02081163581974355 | 9,451 / `native_done` | 0.029108986017138745 |

V1 used a **2,000-action / 300-second** research limit; v2 used **10,000 actions / 900 seconds**. Both the wield handling and the research limits changed, so score gains cannot be attributed solely to the assertion fix. V1's 9,140-action evidence and its historical Harbor diagnostic remain unchanged; that Harbor validation does not validate these longer v2 tapes.

## Scope and provenance

The original native limits remain **100,000 actions** and **150 calls without native-turn progress**. The original scorer remains active, including its previously documented ceiling of **0.8067964442444019**. No model API calls were made and no official full oracle was added. The recorded runtime used one CPU, 1 GiB memory and no network.

The [compact validation JSON](nle_autoascend_v2_validation.json) contains exact results, per-seed case/replay hashes, replay trace digests, prefix comparisons, source pins and inventory-confirmation events. The native replays ran in separate fresh processes. The subsequent host audit inspected saved evidence; it was not another game execution. Native end-reason text was compared between saved runs rather than independently recalculated from raw tty arrays.

The following are **local logical artifact identifiers**, not repository download links. Raw traces, observations, logs, frozen sources and the full audit remain local; they have not been uploaded. The compact JSON preserves their identifiers and hashes without exposing host absolute paths.

| Local source artifact | SHA256 |
|---|---|
| `research/nle_autoascend_v2_summary.json` | `50c3b771ad146efad4bd97f0c9e33996c572bcc8c9b282b53a79dafaf3bd4295` |
| `research/nle_autoascend_results/five_seed_v2_10000_audit.json` | `fe71d07682b23bba9f60842ca127bfde238c12b75f1159294b90a0ab5e9eb4f4` |
| `research/nle_autoascend_v2_report.md` | `bc3a00f325933e50807de8535c137f383998248f3ee0d96934e3740666ca3168` |

Frozen bridge SHA256: `15cdc23f3c250b4b675f7bc1e4c8c3201c7ed9e80be17d41591cf579ef62b4c2`. Frozen batch SHA256: `e14ac2ab57f5752bccd9761ef43ae5a848b6f35507ce307d7427b11957db630b`. Frozen plan SHA256: `faaa7afbacc44cabbb0b26570ded54e3a596ffae89f5d1f2958bc97668ad330e`. Measured image ID: `sha256:45eca5388fe179ec7ede2a1b4dffac4b5795a6b3df39aeeb44a7516784baf60a`.
