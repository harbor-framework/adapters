# Review evidence and acceptance status

The source comparison reads GitHub task bytes directly from commit eb60952124b90e9f0886c1212bf7463e26d0bc19 and HF prompt bytes from pinned snapshot 0fa14219cafdbab634d8b3cfbce238a8735a214f. `definition-comparison.json` lists every bundled file. SHA-256 is not a semantic-equivalence proof. Instructions originate from HF, not the GitHub task directories.

The task archive contains the scoring configuration used by the selected full-reward oracle evidence, including gpt-6.1-sol judges. Matching GitHub task scoring is published in ASI-Bench main commit [515e6d4](https://github.com/apexin-ai/ASI-Bench/commit/515e6d41b5717d2ba43d977f57a0698a5c959836). The per-file comparison records differences against the pinned historical sources; no byte-identical-source claim is made.

The oracle campaign contains 235 full rewards, one valid DNA score of 99.75, and four CMOS evaluator failures. The later CMOS evaluation changes judge configuration and cannot be relabeled as same-configuration recovery. Selected historical full-score reports remain available, but do not replace original campaign outcomes in acceptance claims. No additional trials were run to maximize scores.

The five-task single-run comparison is submitted as a requested scope exception, not compliant repeated-run parity. Sample SEM is undefined. No HF parity/dataset PR is published; corresponding link arrays are empty. The maximum proposed fallback is all 60 B1 problems, one independent run per side. Maintainer acceptance is pending.

`generated-task/` contains a complete astronomy B1 export as a deterministic archive with per-file hashes. It is generation evidence, not a new scientific run or dataset publication.
