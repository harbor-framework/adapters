Vendored unchanged from https://github.com/aiming-lab/RSI-Exam/tree/085036f6efabe2db832332b1de87fffffb913e87/infra/prompts
(MIT License, (c) RSI-Exam Team). These files define the upstream autoresearch run
protocol and are applied at run time; do not edit them here.

- autoresearch.j2  — prompt template passed via `--ak prompt_template_path=...`
- autoresearch.md  — program mounted at /app/AUTORESEARCH.md (via mount.yaml, $ARB_PROGRAM)
- budget.py        — budget reporter mounted at /app/budget.py (via mount.yaml, $ARB_BUDGET_PY)
- mount.yaml       — docker-compose overlay passed via `--extra-docker-compose`
