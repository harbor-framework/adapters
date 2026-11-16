# Third-party notices

This adapter works from UK AI Security Institute's Inspect Evals
repository, `src/inspect_evals/gdm_stealth`, pinned at commit
`a68dade7efb803ef50c8442d3f16264b293d1414`. It copies the
AI-secretary `email_tasks` files into generated tasks, vendors the
strategic-rule-breaking environment core in
`src/gdm_stealth/custom_agent/strategic/` (import/RNG rewrites only),
copies the cover-your-tracks `email.csv` and AI-secretary rating
criteria into the parity agent, and extracts the subtlety objectives.

Inspect Evals is MIT licensed. The full license text, including the
copyright notice, is in `LICENSE.inspect-evals`, and a copy is placed
in each generated task's `environment/` directory.
