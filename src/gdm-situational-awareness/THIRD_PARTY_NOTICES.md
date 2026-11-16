# Third-party notices

This adapter generates tasks from UK AI Security Institute's Inspect
Evals repository, `src/inspect_evals/gdm_self_reasoning`, pinned at
commit `a68dade7efb803ef50c8442d3f16264b293d1414`, and copies its
challenge environment assets into generated tasks at generation time.
The parity agent also includes constants extracted mechanically from
that code (oversight fake history, database rows, Game-of-Life cases).

Inspect Evals is MIT licensed. The full license text, including the
copyright notice, is in `LICENSE.inspect-evals`, and a copy is placed
in each generated task's `environment/` directory.
