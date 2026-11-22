# Ready-for-review PR model survey

Reviewed 2026-11-21 (America/Los_Angeles). Unauthenticated GitHub API snapshot: 91 open PRs; 22 have ready-for-review titles. These are author-reported results, not independent reruns or evidence of maintainer acceptance.

| PR | Model role(s) | Agent | Evidence status |
| --- | --- | --- | --- |
| [#121](https://github.com/harbor-framework/adapters/pull/121) | deepseek/deepseek-flash | opencode@1.19.6 | PR reports matched parity, 14 tasks, 3 runs per side |
| [#97](https://github.com/harbor-framework/adapters/pull/97) | claude-haiku-4-5 | securereviewer-single-call@1.0.0 | PR reports matched parity, 25/261 tasks, 2 runs; team-agreed plan; 2077AI gateway |
| [#93](https://github.com/harbor-framework/adapters/pull/93) | openai/gpt-5.2; judge claude-haiku-4-5 | MLR-Agent / MlrBenchAgent | Old results superseded; revised parity pending; judge endpoint unavailable |
| [#91](https://github.com/harbor-framework/adapters/pull/91) | claude-haiku-4-5; judge gemini-3.5-flash | claude-code@2.1.311 | PR reports 30/99-task parity, 3 runs; alias-only gateway limitation disclosed |
| [#85](https://github.com/harbor-framework/adapters/pull/85) | gpt-4o-mini-2024-07-18; judge gpt-4o-2024-08-06 | charxiv-direct@1.0.0 | PR reports 500-task parity, 3 runs; separate Codex run is generalization |
| [#78](https://github.com/harbor-framework/adapters/pull/78) | deepseek-v4.1-flash | mini-swe-agent@2.4.6 | PR reports 60 Lite tasks, 3 runs; 2077AI gateway; earlier leakage-contaminated results retained separately |
| [#77](https://github.com/harbor-framework/adapters/pull/77) | Not selected in PR body | Proposed CLI agent | Parity plan and results pending |
| [#64](https://github.com/harbor-framework/adapters/pull/64) | DeepSeek-V4-Flash | qwen-code | Six-task live smoke test only; parity pending |
| [#63](https://github.com/harbor-framework/adapters/pull/63) | gpt-5.2-2025-12-11 (oracle judge); gemini/gemini-3-pro-preview (default judge) | No parity agent selected | Judge-graded oracle only; parity pending |
| [#62](https://github.com/harbor-framework/adapters/pull/62) | Haiku; original judge gpt-5-mini vs Harbor Haiku | Claude Code | Historical results retained; judge and failure-accounting mismatches unresolved |
| [#57](https://github.com/harbor-framework/adapters/pull/57) | openai/gpt-5-mini | See archived configs | Historical parity configs; upload label gpt-4o-mini is explicitly identified as stale |
| [#51](https://github.com/harbor-framework/adapters/pull/51) | deepseek-v4-pro; judge gemini-2.5-pro | claude-code@2.1.177 | PR reports 5/132-task parity, 3 runs per side; no full-set model evidence |
| [#44](https://github.com/harbor-framework/adapters/pull/44) | One-shot parity model not named in this PR body; GPT-5.6 is a separate agentic run | One-shot custom agent; separate Codex evaluation | Historical one-shot parity retained; agentic GPT-5.6 must not be counted as matched parity |
| [#43](https://github.com/harbor-framework/adapters/pull/43) | Not named in PR body | InspectSolver bridge | Historical 150-task, 3-run parity reported; model not inferred |
| [#27](https://github.com/harbor-framework/adapters/pull/27) | claude-haiku-5-5; judge claude-haiku-4-5 | claude-code@2.1.330 | PR reports alfworld-10 and random-30 subsets, 3 runs |
| [#24](https://github.com/harbor-framework/adapters/pull/24) | Claude Haiku 5.5; judge gpt-5.4 | claude-code@2.1.322 | PR reports 150-task matched parity, 3 runs; served snapshot limitations disclosed |
| [#19](https://github.com/harbor-framework/adapters/pull/19) | Not selected in PR body | Not established | Matched model parity pending; patch validation is separate |
| [#18](https://github.com/harbor-framework/adapters/pull/18) | Not selected in PR body | Not established | Reference-solution differential checks only; independent parity to coordinate |
| [#17](https://github.com/harbor-framework/adapters/pull/17) | Not selected in PR body | Not established | Authored-oracle checks only; independent parity separated |
| [#13](https://github.com/harbor-framework/adapters/pull/13) | MiniMax/m2.5 | mini-swe-agent@1.14.4 | PR reports 105-task parity, 3 runs per side |
| [#6](https://github.com/harbor-framework/adapters/pull/6) | deepseek-v4-1-flash-260910 | mini-swe-agent@2.4.6 | PR reports 15/49-task parity, 3 runs; API estimate about $40 plus separate TPU costs |
| [#5](https://github.com/harbor-framework/adapters/pull/5) | gemini-2.5-pro (judge) | No parity agent selected | Judge-graded oracle only; parity pending |

## Decision for BizAgentBench

Prefer discussing DeepSeek Flash with Harbor: #121, #78 and #6 provide completed-parity precedents. Keep the native HTTPAgent/Harbor relay; the OpenCode and mini-swe-agent wrappers in those PRs are not replacements for the native two-role protocol. Haiku is a fallback supported by #97/#91 precedents.

The identifiers deepseek/deepseek-flash, deepseek-v4.1-flash and deepseek-v4-1-flash-260910 belong to different provider/config contexts. Confirm the actual served snapshot and endpoint instead of copying a name and assuming equivalent behavior. Gateway availability and funding remain unconfirmed.

Use the Summary / Implementation / Validation / Proposed parity / Status organization seen in #121 and #6. Keep scripted controls, real customer oracle and model parity distinct. Do not copy another benchmark's low invoice, task subset, judge or completed checkbox into this WIP.

BizAgentBench uses deterministic isolated grading, so judge-model choices in the surveyed PRs do not introduce a third model role here. Current live-plan files remain disabled; no model calls, login, PR submission or external messages were made.
