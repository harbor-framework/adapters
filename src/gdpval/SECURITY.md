# GDPval security boundary

The current task template requires Harbor 0.23.0 separate verifier environments.
Only declared `/app` artifacts should be transferred into a fresh verifier; the
agent interpreter and background processes are not the grading runtime.
`tests/security_review.py` contains local fake-service checks; the older
`tests/docker_review.py` documents historical shared-container diagnostics.

The optional `--agent-network no-network` generation profile sets Docker
`network_mode: none` and removes NET_ADMIN/NET_RAW. It changes task capabilities
and requires prepared inputs/tools. Default public mode retains web access and
allows access to publicly hosted Gold files. It is not a secure answer-source boundary.

Verifier logs may share a host mount with the agent. Isolation after agent cleanup
failure is not accepted: a Runner guarantee and completed fault-injection evidence
are still required. Do not interpret limited migration acceptance as closure of this risk.

Missing/symlinked submissions score zero. Stale reward files are removed.
Judge/API/parser failures are unscored errors. Exact Gold receives one without a
judge call; this is an Oracle convenience, not proof of semantic grading quality.
See ACCEPTANCE.md for current acceptance scope and REVIEW.md for historical findings.
