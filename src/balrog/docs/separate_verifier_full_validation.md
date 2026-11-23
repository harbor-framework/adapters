# Full separate-verifier reference validation

Harbor **0.26.0**, Docker, standard `oracle` agent: **255/255 tasks completed with zero exceptions**. All 255 trials used a separate verifier and successfully transferred the protected game result. There were **239 full-score oracles and 16 diagnostic references**. Completion does not mean that every task earned full reward.

| Environment | Completed | Full-score oracles | Diagnostic references | Mean native progression | Actions |
|---|---:|---:|---:|---:|---:|
| BabyAI | 50 | 50 | 0 | 1 | 411 |
| Baba Is AI | 120 | 120 | 0 | 1 | 1522 |
| TextWorld | 30 | 30 | 0 | 1 | 996 |
| Crafter | 10 | 0 | 10 | 0.0909090909091 | 204 |
| NetHack / NLE | 5 | 0 | 5 | 0.00307845381507 | 162 |
| MiniHack | 40 | 39 | 1 | 0.975 | 1527 |

Job: `separate-verifier-full-v1` (`2e04219d-d836-4933-80ac-e4f0c9df3367`). One attempt per task, 4 concurrent trials and no retries.

The audit verified complete fixed-seed coverage, unchanged task/source snapshots, actual runtime configuration, task identity and budgets, reference actions and scores, reward validity, absence of infrastructure errors, and agreement between the collected game artifact and the offline verifier result. The artifact source was `/var/lib/balrog/result.json` in service `game`, with successful collection recorded in every manifest.

Exact fresh replay passed in 255 trials. The existing explicit Crafter native-state fallback was used in 0 trials; the audit recorded 0 individual fixture-transition field differences. Native scores, reference actions, task identity and stopping rules were not relaxed.

The [machine-readable summary](separate_verifier_full_validation.json) contains all 255 task IDs, accepted scores, reference classifications and evidence hashes. It records the new run separately from the historical baseline and the earlier representative correct/wrong/regrade checks. Full original jobs, submissions, agent logs, grading results, artifact manifests and generated task/source snapshots remain saved locally. They have not been uploaded to Hugging Face.

This run does not resolve the remaining incomplete oracles or benchmark issues and does not constitute model parity or Ready for Review status. No model API call was made. Existing native scoring and the Crafter replay policy remain unchanged.
