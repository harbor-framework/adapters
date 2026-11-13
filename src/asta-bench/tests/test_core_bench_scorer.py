"""Offline equivalence tests for the core-bench-hard verifier and builder.

The expected values below were computed with the REAL upstream functions
(``inspect_evals.core_bench.{scorer,utils,dataset}`` at the commit pinned by
asta-bench's inspect_evals submodule, c2bec9ebee7a5995512bf5ff67a2e82afe4d12e1,
numpy 2.4.4 / scipy 1.17.1) and pasted in as literals, so these tests do not
need the upstream checkout.  Gold data comes only from the public, unencrypted
CORE-Bench *train* split (the adapter's validation split) plus synthetic cases.

The prediction-interval paths need scipy (as upstream does); those tests are
skipped when scipy is absent, e.g. run with
``uv run --with pytest --with scipy pytest tests/test_core_bench_scorer.py``.
"""

from __future__ import annotations

import io
import json
import math
import subprocess
import sys
import tarfile
import types
from pathlib import Path

import pytest

from asta_bench.benchmarks import core_bench_hard as cbh

FIXTURES = json.loads(
    r"""{"cases":[["5975162-zero-mean",{"Report the mean metric from the output.":0.0,"Report the Avg FES from the output.":96.7741935483871},[{"Report the mean metric from the output.":4.440892098500626e-16,"Report the Avg FES from the output.":96.7741935483871},{"Report the mean metric from the output.":4.440892098500626e-16,"Report the Avg FES from the output.":96.7741935483871},{"Report the mean metric from the output.":4.440892098500626e-16,"Report the Avg FES from the output.":96.7741935483871}],{"correct_written_answers":1,"correct_vision_answers":0,"total_written_questions":2,"total_vision_questions":0}],["5975162-gold0",{"Report the mean metric from the output.":4.440892098500626e-16,"Report the Avg FES from the output.":96.7741935483871},[{"Report the mean metric from the output.":4.440892098500626e-16,"Report the Avg FES from the output.":96.7741935483871},{"Report the mean metric from the output.":4.440892098500626e-16,"Report the Avg FES from the output.":96.7741935483871},{"Report the mean metric from the output.":4.440892098500626e-16,"Report the Avg FES from the output.":96.7741935483871}],{"correct_written_answers":2,"correct_vision_answers":0,"total_written_questions":2,"total_vision_questions":0}],["lower-bound-rounding",{"q":0.12349},[{"q":0.1235},{"q":0.1235}],{"correct_written_answers":0,"correct_vision_answers":0,"total_written_questions":1,"total_vision_questions":0}],["tiny-interval",{"q":2e-05},[{"q":1e-05},{"q":3e-05}],{"correct_written_answers":1,"correct_vision_answers":0,"total_written_questions":1,"total_vision_questions":0}],["single-trial-exact",{"q":1.5},[{"q":1.5}],{"correct_written_answers":0,"correct_vision_answers":0,"total_written_questions":1,"total_vision_questions":0}],["single-trial-string",{"q":"Yes."},[{"q":"yes"}],{"correct_written_answers":1,"correct_vision_answers":0,"total_written_questions":1,"total_vision_questions":0}],["percent-string",{"q":"45%"},[{"q":44.0},{"q":46.0},{"q":45.5}],{"correct_written_answers":1,"correct_vision_answers":0,"total_written_questions":1,"total_vision_questions":0}],["strip-punct-keys",{"What is x?":3,"fig label.":"Cat"},[{"What is x":3.0,"fig label":"cat","lst":[1,2]},{"What is x":3.2,"fig label":"cat","lst":[1,2]}],{"correct_written_answers":1,"correct_vision_answers":1,"total_written_questions":2,"total_vision_questions":1}],["list-eq",{"lst":[1,2]},[{"lst":[1,2]},{"lst":[1,3]}],{"correct_written_answers":1,"correct_vision_answers":0,"total_written_questions":1,"total_vision_questions":0}],["list-neq",{"lst":[2,1]},[{"lst":[1,2]},{"lst":[1,2]}],{"correct_written_answers":0,"correct_vision_answers":0,"total_written_questions":1,"total_vision_questions":0}],["bool-numeric",{"q":true},[{"q":1.0},{"q":1.0}],{"correct_written_answers":1,"correct_vision_answers":0,"total_written_questions":1,"total_vision_questions":0}],["non-dict-agent",[1,2,3],[{"q":1.0},{"q":2.0}],{"correct_written_answers":0,"correct_vision_answers":0,"total_written_questions":1,"total_vision_questions":0}],["extra-keys-nan",{"zzz":1,"q":"nan"},[{"q":1.0},{"q":2.0}],{"correct_written_answers":0,"correct_vision_answers":0,"total_written_questions":1,"total_vision_questions":0}],["string-num-gt",{"q":"5"},[{"q":"5"},{"q":"5"}],{"correct_written_answers":0,"correct_vision_answers":0,"total_written_questions":1,"total_vision_questions":0}],["inf",{"q":"inf"},[{"q":1.0},{"q":2.0}],{"correct_written_answers":0,"correct_vision_answers":0,"total_written_questions":1,"total_vision_questions":0}],["zero-variance",{"q":0.1},[{"q":0.1},{"q":0.1},{"q":0.1}],{"correct_written_answers":1,"correct_vision_answers":0,"total_written_questions":1,"total_vision_questions":0}],["dict-value",{"q":{"a":1}},[{"q":1.0},{"q":2.0}],{"correct_written_answers":0,"correct_vision_answers":0,"total_written_questions":1,"total_vision_questions":0}],["null-value",{"q":null},[{"q":1.0},{"q":2.0}],{"correct_written_answers":0,"correct_vision_answers":0,"total_written_questions":1,"total_vision_questions":0}],["capsule-0201225-gold0",{"Report the AUC at the 'sample-level'.":0.998,"Report the sensitivity at the 'sample-level'.":0.966,"Report the specificity at the 'sample-level'.":0.994,"Report the accuracy at the 'sample-level'.":0.992,"Report the AUC at the 'patient-level'.":0.998,"Report the sensitivity at the 'patient-level'.":1.0,"Report the specificity at the 'patient-level'.":0.972,"Report the accuracy at the 'patient-level'.":0.978},[{"Report the AUC at the 'sample-level'.":0.998,"Report the sensitivity at the 'sample-level'.":0.966,"Report the specificity at the 'sample-level'.":0.994,"Report the accuracy at the 'sample-level'.":0.992,"Report the AUC at the 'patient-level'.":0.998,"Report the sensitivity at the 'patient-level'.":1.0,"Report the specificity at the 'patient-level'.":0.972,"Report the accuracy at the 'patient-level'.":0.978},{"Report the AUC at the 'sample-level'.":0.998,"Report the sensitivity at the 'sample-level'.":0.966,"Report the specificity at the 'sample-level'.":0.994,"Report the accuracy at the 'sample-level'.":0.992,"Report the AUC at the 'patient-level'.":0.998,"Report the sensitivity at the 'patient-level'.":1.0,"Report the specificity at the 'patient-level'.":0.972,"Report the accuracy at the 'patient-level'.":0.978},{"Report the AUC at the 'sample-level'.":0.998,"Report the sensitivity at the 'sample-level'.":0.966,"Report the specificity at the 'sample-level'.":0.994,"Report the accuracy at the 'sample-level'.":0.992,"Report the AUC at the 'patient-level'.":0.998,"Report the sensitivity at the 'patient-level'.":1.0,"Report the specificity at the 'patient-level'.":0.972,"Report the accuracy at the 'patient-level'.":0.978}],{"correct_written_answers":8,"correct_vision_answers":0,"total_written_questions":8,"total_vision_questions":0}],["capsule-0201225-empty",{},[{"Report the AUC at the 'sample-level'.":0.998,"Report the sensitivity at the 'sample-level'.":0.966,"Report the specificity at the 'sample-level'.":0.994,"Report the accuracy at the 'sample-level'.":0.992,"Report the AUC at the 'patient-level'.":0.998,"Report the sensitivity at the 'patient-level'.":1.0,"Report the specificity at the 'patient-level'.":0.972,"Report the accuracy at the 'patient-level'.":0.978},{"Report the AUC at the 'sample-level'.":0.998,"Report the sensitivity at the 'sample-level'.":0.966,"Report the specificity at the 'sample-level'.":0.994,"Report the accuracy at the 'sample-level'.":0.992,"Report the AUC at the 'patient-level'.":0.998,"Report the sensitivity at the 'patient-level'.":1.0,"Report the specificity at the 'patient-level'.":0.972,"Report the accuracy at the 'patient-level'.":0.978},{"Report the AUC at the 'sample-level'.":0.998,"Report the sensitivity at the 'sample-level'.":0.966,"Report the specificity at the 'sample-level'.":0.994,"Report the accuracy at the 'sample-level'.":0.992,"Report the AUC at the 'patient-level'.":0.998,"Report the sensitivity at the 'patient-level'.":1.0,"Report the specificity at the 'patient-level'.":0.972,"Report the accuracy at the 'patient-level'.":0.978}],{"correct_written_answers":0,"correct_vision_answers":0,"total_written_questions":8,"total_vision_questions":0}],["capsule-0201225-perturbed",{"Report the AUC at the 'sample-level'.":2.497,"Report the sensitivity at the 'sample-level'.":2.449,"Report the specificity at the 'sample-level'.":2.491,"Report the accuracy at the 'sample-level'.":2.488,"Report the AUC at the 'patient-level'.":2.497,"Report the sensitivity at the 'patient-level'.":2.5,"Report the specificity at the 'patient-level'.":2.458,"Report the accuracy at the 'patient-level'.":2.467},[{"Report the AUC at the 'sample-level'.":0.998,"Report the sensitivity at the 'sample-level'.":0.966,"Report the specificity at the 'sample-level'.":0.994,"Report the accuracy at the 'sample-level'.":0.992,"Report the AUC at the 'patient-level'.":0.998,"Report the sensitivity at the 'patient-level'.":1.0,"Report the specificity at the 'patient-level'.":0.972,"Report the accuracy at the 'patient-level'.":0.978},{"Report the AUC at the 'sample-level'.":0.998,"Report the sensitivity at the 'sample-level'.":0.966,"Report the specificity at the 'sample-level'.":0.994,"Report the accuracy at the 'sample-level'.":0.992,"Report the AUC at the 'patient-level'.":0.998,"Report the sensitivity at the 'patient-level'.":1.0,"Report the specificity at the 'patient-level'.":0.972,"Report the accuracy at the 'patient-level'.":0.978},{"Report the AUC at the 'sample-level'.":0.998,"Report the sensitivity at the 'sample-level'.":0.966,"Report the specificity at the 'sample-level'.":0.994,"Report the accuracy at the 'sample-level'.":0.992,"Report the AUC at the 'patient-level'.":0.998,"Report the sensitivity at the 'patient-level'.":1.0,"Report the specificity at the 'patient-level'.":0.972,"Report the accuracy at the 'patient-level'.":0.978}],{"correct_written_answers":0,"correct_vision_answers":0,"total_written_questions":8,"total_vision_questions":0}],["capsule-0940461-gold0",{"Report the best test R^2 value for c = 1.0.":0.8259,"Report the best test RMSE value for c = 1.0.":0.2806},[{"Report the best test R^2 value for c = 1.0.":0.8259,"Report the best test RMSE value for c = 1.0.":0.2806},{"Report the best test R^2 value for c = 1.0.":0.8259,"Report the best test RMSE value for c = 1.0.":0.2806},{"Report the best test R^2 value for c = 1.0.":0.8259,"Report the best test RMSE value for c = 1.0.":0.2806}],{"correct_written_answers":2,"correct_vision_answers":0,"total_written_questions":2,"total_vision_questions":0}],["capsule-0940461-empty",{},[{"Report the best test R^2 value for c = 1.0.":0.8259,"Report the best test RMSE value for c = 1.0.":0.2806},{"Report the best test R^2 value for c = 1.0.":0.8259,"Report the best test RMSE value for c = 1.0.":0.2806},{"Report the best test R^2 value for c = 1.0.":0.8259,"Report the best test RMSE value for c = 1.0.":0.2806}],{"correct_written_answers":0,"correct_vision_answers":0,"total_written_questions":2,"total_vision_questions":0}],["capsule-0940461-perturbed",{"Report the best test R^2 value for c = 1.0.":2.2388500000000002,"Report the best test RMSE value for c = 1.0.":1.4209},[{"Report the best test R^2 value for c = 1.0.":0.8259,"Report the best test RMSE value for c = 1.0.":0.2806},{"Report the best test R^2 value for c = 1.0.":0.8259,"Report the best test RMSE value for c = 1.0.":0.2806},{"Report the best test R^2 value for c = 1.0.":0.8259,"Report the best test RMSE value for c = 1.0.":0.2806}],{"correct_written_answers":0,"correct_vision_answers":0,"total_written_questions":2,"total_vision_questions":0}],["capsule-1906954-gold0",{"Report the Delta value for Italy.":0.459,"Report the Delta value for adults.":0.092},[{"Report the Delta value for Italy.":0.459,"Report the Delta value for adults.":0.092},{"Report the Delta value for Italy.":0.459,"Report the Delta value for adults.":0.092},{"Report the Delta value for Italy.":0.459,"Report the Delta value for adults.":0.092}],{"correct_written_answers":2,"correct_vision_answers":0,"total_written_questions":2,"total_vision_questions":0}],["capsule-1906954-empty",{},[{"Report the Delta value for Italy.":0.459,"Report the Delta value for adults.":0.092},{"Report the Delta value for Italy.":0.459,"Report the Delta value for adults.":0.092},{"Report the Delta value for Italy.":0.459,"Report the Delta value for adults.":0.092}],{"correct_written_answers":0,"correct_vision_answers":0,"total_written_questions":2,"total_vision_questions":0}],["capsule-1906954-perturbed",{"Report the Delta value for Italy.":1.6885,"Report the Delta value for adults.":1.138},[{"Report the Delta value for Italy.":0.459,"Report the Delta value for adults.":0.092},{"Report the Delta value for Italy.":0.459,"Report the Delta value for adults.":0.092},{"Report the Delta value for Italy.":0.459,"Report the Delta value for adults.":0.092}],{"correct_written_answers":0,"correct_vision_answers":0,"total_written_questions":2,"total_vision_questions":0}],["capsule-3249574-gold0",{"Report the F1-score after epoch 200.":0.94743},[{"Report the F1-score after epoch 200.":0.94743},{"Report the F1-score after epoch 200.":0.95698},{"Report the F1-score after epoch 200.":0.99188}],{"correct_written_answers":1,"correct_vision_answers":0,"total_written_questions":1,"total_vision_questions":0}],["capsule-3249574-empty",{},[{"Report the F1-score after epoch 200.":0.94743},{"Report the F1-score after epoch 200.":0.95698},{"Report the F1-score after epoch 200.":0.99188}],{"correct_written_answers":0,"correct_vision_answers":0,"total_written_questions":1,"total_vision_questions":0}],["capsule-3249574-perturbed",{"Report the F1-score after epoch 200.":2.421145},[{"Report the F1-score after epoch 200.":0.94743},{"Report the F1-score after epoch 200.":0.95698},{"Report the F1-score after epoch 200.":0.99188}],{"correct_written_answers":0,"correct_vision_answers":0,"total_written_questions":1,"total_vision_questions":0}],["capsule-4098236-gold0",{"Report the exact match of the classification.":0.27338983050847454,"Report the hamming loss of the classification.":0.2262241054613936},[{"Report the exact match of the classification.":0.27338983050847454,"Report the hamming loss of the classification.":0.2262241054613936},{"Report the exact match of the classification.":0.27338983050847454,"Report the hamming loss of the classification.":0.2262241054613936},{"Report the exact match of the classification.":0.27338983050847454,"Report the hamming loss of the classification.":0.2262241054613936}],{"correct_written_answers":2,"correct_vision_answers":0,"total_written_questions":2,"total_vision_questions":0}],["capsule-4098236-empty",{},[{"Report the exact match of the classification.":0.27338983050847454,"Report the hamming loss of the classification.":0.2262241054613936},{"Report the exact match of the classification.":0.27338983050847454,"Report the hamming loss of the classification.":0.2262241054613936},{"Report the exact match of the classification.":0.27338983050847454,"Report the hamming loss of the classification.":0.2262241054613936}],{"correct_written_answers":0,"correct_vision_answers":0,"total_written_questions":2,"total_vision_questions":0}],["capsule-4098236-perturbed",{"Report the exact match of the classification.":1.410084745762712,"Report the hamming loss of the classification.":1.3393361581920904},[{"Report the exact match of the classification.":0.27338983050847454,"Report the hamming loss of the classification.":0.2262241054613936},{"Report the exact match of the classification.":0.27338983050847454,"Report the hamming loss of the classification.":0.2262241054613936},{"Report the exact match of the classification.":0.27338983050847454,"Report the hamming loss of the classification.":0.2262241054613936}],{"correct_written_answers":0,"correct_vision_answers":0,"total_written_questions":2,"total_vision_questions":0}],["capsule-5286757-gold0",{"Report the train loss after training the final epoch (epoch 9).":0.04598272387846722},[{"Report the train loss after training the final epoch (epoch 9).":0.04598272387846722},{"Report the train loss after training the final epoch (epoch 9).":0.05381510184042584},{"Report the train loss after training the final epoch (epoch 9).":0.0502882808202249}],{"correct_written_answers":1,"correct_vision_answers":0,"total_written_questions":1,"total_vision_questions":0}],["capsule-5286757-empty",{},[{"Report the train loss after training the final epoch (epoch 9).":0.04598272387846722},{"Report the train loss after training the final epoch (epoch 9).":0.05381510184042584},{"Report the train loss after training the final epoch (epoch 9).":0.0502882808202249}],{"correct_written_answers":0,"correct_vision_answers":0,"total_written_questions":1,"total_vision_questions":0}],["capsule-5286757-perturbed",{"Report the train loss after training the final epoch (epoch 9).":1.0689740858177008},[{"Report the train loss after training the final epoch (epoch 9).":0.04598272387846722},{"Report the train loss after training the final epoch (epoch 9).":0.05381510184042584},{"Report the train loss after training the final epoch (epoch 9).":0.0502882808202249}],{"correct_written_answers":0,"correct_vision_answers":0,"total_written_questions":1,"total_vision_questions":0}],["capsule-6133093-gold0",{"Report the estimate for the Label2 attribute and Attackers level in the Average Marginal Component Effects (AMCE) table of model6_c":0.0685169},[{"Report the estimate for the Label2 attribute and Attackers level in the Average Marginal Component Effects (AMCE) table of model6_c":0.0685169},{"Report the estimate for the Label2 attribute and Attackers level in the Average Marginal Component Effects (AMCE) table of model6_c":0.0685169},{"Report the estimate for the Label2 attribute and Attackers level in the Average Marginal Component Effects (AMCE) table of model6_c":0.0685169}],{"correct_written_answers":1,"correct_vision_answers":0,"total_written_questions":1,"total_vision_questions":0}],["capsule-6133093-empty",{},[{"Report the estimate for the Label2 attribute and Attackers level in the Average Marginal Component Effects (AMCE) table of model6_c":0.0685169},{"Report the estimate for the Label2 attribute and Attackers level in the Average Marginal Component Effects (AMCE) table of model6_c":0.0685169},{"Report the estimate for the Label2 attribute and Attackers level in the Average Marginal Component Effects (AMCE) table of model6_c":0.0685169}],{"correct_written_answers":0,"correct_vision_answers":0,"total_written_questions":1,"total_vision_questions":0}],["capsule-6133093-perturbed",{"Report the estimate for the Label2 attribute and Attackers level in the Average Marginal Component Effects (AMCE) table of model6_c":1.10277535},[{"Report the estimate for the Label2 attribute and Attackers level in the Average Marginal Component Effects (AMCE) table of model6_c":0.0685169},{"Report the estimate for the Label2 attribute and Attackers level in the Average Marginal Component Effects (AMCE) table of model6_c":0.0685169},{"Report the estimate for the Label2 attribute and Attackers level in the Average Marginal Component Effects (AMCE) table of model6_c":0.0685169}],{"correct_written_answers":0,"correct_vision_answers":0,"total_written_questions":1,"total_vision_questions":0}],["capsule-7935517-gold0",{"fig From the plot sampling rho, report the rho value corresponding to the solid red line.":0,"fig Report the x-axis label of the plot measuring Cohen's d.":"Power"},[{"fig From the plot sampling rho, report the rho value corresponding to the solid red line.":0,"fig Report the x-axis label of the plot measuring Cohen's d.":"Power"},{"fig From the plot sampling rho, report the rho value corresponding to the solid red line.":0,"fig Report the x-axis label of the plot measuring Cohen's d.":"Power"},{"fig From the plot sampling rho, report the rho value corresponding to the solid red line.":0,"fig Report the x-axis label of the plot measuring Cohen's d.":"Power"}],{"correct_written_answers":0,"correct_vision_answers":2,"total_written_questions":0,"total_vision_questions":2}],["capsule-7935517-empty",{},[{"fig From the plot sampling rho, report the rho value corresponding to the solid red line.":0,"fig Report the x-axis label of the plot measuring Cohen's d.":"Power"},{"fig From the plot sampling rho, report the rho value corresponding to the solid red line.":0,"fig Report the x-axis label of the plot measuring Cohen's d.":"Power"},{"fig From the plot sampling rho, report the rho value corresponding to the solid red line.":0,"fig Report the x-axis label of the plot measuring Cohen's d.":"Power"}],{"correct_written_answers":0,"correct_vision_answers":0,"total_written_questions":0,"total_vision_questions":2}],["capsule-7935517-perturbed",{"fig From the plot sampling rho, report the rho value corresponding to the solid red line.":1.0,"fig Report the x-axis label of the plot measuring Cohen's d.":"Power"},[{"fig From the plot sampling rho, report the rho value corresponding to the solid red line.":0,"fig Report the x-axis label of the plot measuring Cohen's d.":"Power"},{"fig From the plot sampling rho, report the rho value corresponding to the solid red line.":0,"fig Report the x-axis label of the plot measuring Cohen's d.":"Power"},{"fig From the plot sampling rho, report the rho value corresponding to the solid red line.":0,"fig Report the x-axis label of the plot measuring Cohen's d.":"Power"}],{"correct_written_answers":0,"correct_vision_answers":1,"total_written_questions":0,"total_vision_questions":2}],["capsule-9070543-gold0",{"fig From the figure 4 continuous dose response, report the name of the sample with the highest normalized cell number at an LGX818 concentration of 0.":"Vector Control"},[{"fig From the figure 4 continuous dose response, report the name of the sample with the highest normalized cell number at an LGX818 concentration of 0.":"Vector Control"},{"fig From the figure 4 continuous dose response, report the name of the sample with the highest normalized cell number at an LGX818 concentration of 0.":"Vector Control"},{"fig From the figure 4 continuous dose response, report the name of the sample with the highest normalized cell number at an LGX818 concentration of 0.":"Vector Control"}],{"correct_written_answers":0,"correct_vision_answers":1,"total_written_questions":0,"total_vision_questions":1}],["capsule-9070543-empty",{},[{"fig From the figure 4 continuous dose response, report the name of the sample with the highest normalized cell number at an LGX818 concentration of 0.":"Vector Control"},{"fig From the figure 4 continuous dose response, report the name of the sample with the highest normalized cell number at an LGX818 concentration of 0.":"Vector Control"},{"fig From the figure 4 continuous dose response, report the name of the sample with the highest normalized cell number at an LGX818 concentration of 0.":"Vector Control"}],{"correct_written_answers":0,"correct_vision_answers":0,"total_written_questions":0,"total_vision_questions":1}],["capsule-9070543-perturbed",{"fig From the figure 4 continuous dose response, report the name of the sample with the highest normalized cell number at an LGX818 concentration of 0.":"Vector Control"},[{"fig From the figure 4 continuous dose response, report the name of the sample with the highest normalized cell number at an LGX818 concentration of 0.":"Vector Control"},{"fig From the figure 4 continuous dose response, report the name of the sample with the highest normalized cell number at an LGX818 concentration of 0.":"Vector Control"},{"fig From the figure 4 continuous dose response, report the name of the sample with the highest normalized cell number at an LGX818 concentration of 0.":"Vector Control"}],{"correct_written_answers":0,"correct_vision_answers":1,"total_written_questions":0,"total_vision_questions":1}]],"intervals":[["5975162-zero-mean",{"Report the mean metric from the output":["4.440892098500626e-16","4.440892098500626e-16"],"Report the Avg FES from the output":["96.77419354838703","96.7741935483872"]}],["5975162-gold0",{"Report the mean metric from the output":["4.440892098500626e-16","4.440892098500626e-16"],"Report the Avg FES from the output":["96.77419354838703","96.7741935483872"]}],["lower-bound-rounding",{"q":["0.1235","0.1235"]}],["tiny-interval",{"q":["-0.00020007792174426867","0.00024007792174426867"]}],["single-trial-exact",{"q":["nan","nan"]}],["single-trial-string",{}],["percent-string",{"q":["39.9955216541244","50.337811679208926"]}],["strip-punct-keys",{"What is x":["0.8992207825573106","5.30077921744269"]}],["list-eq",{}],["list-neq",{}],["bool-numeric",{"q":["1.0","1.0"]}],["non-dict-agent",{"q":["-9.503896087213436","12.503896087213436"]}],["extra-keys-nan",{"q":["-9.503896087213436","12.503896087213436"]}],["string-num-gt",{}],["inf",{"q":["-9.503896087213436","12.503896087213436"]}],["zero-variance",{"q":["0.09999999999999994","0.1000000000000001"]}],["dict-value",{"q":["-9.503896087213436","12.503896087213436"]}],["null-value",{"q":["-9.503896087213436","12.503896087213436"]}],["capsule-0201225-gold0",{"Report the AUC at the 'sample-level":["0.9979999999999992","0.9980000000000006"],"Report the sensitivity at the 'sample-level":["0.9659999999999992","0.9660000000000005"],"Report the specificity at the 'sample-level":["0.9939999999999994","0.9940000000000008"],"Report the accuracy at the 'sample-level":["0.992","0.992"],"Report the AUC at the 'patient-level":["0.9979999999999992","0.9980000000000006"],"Report the sensitivity at the 'patient-level":["1.0","1.0"],"Report the specificity at the 'patient-level":["0.972","0.972"],"Report the accuracy at the 'patient-level":["0.9779999999999994","0.9780000000000008"]}],["capsule-0201225-empty",{"Report the AUC at the 'sample-level":["0.9979999999999992","0.9980000000000006"],"Report the sensitivity at the 'sample-level":["0.9659999999999992","0.9660000000000005"],"Report the specificity at the 'sample-level":["0.9939999999999994","0.9940000000000008"],"Report the accuracy at the 'sample-level":["0.992","0.992"],"Report the AUC at the 'patient-level":["0.9979999999999992","0.9980000000000006"],"Report the sensitivity at the 'patient-level":["1.0","1.0"],"Report the specificity at the 'patient-level":["0.972","0.972"],"Report the accuracy at the 'patient-level":["0.9779999999999994","0.9780000000000008"]}],["capsule-0201225-perturbed",{"Report the AUC at the 'sample-level":["0.9979999999999992","0.9980000000000006"],"Report the sensitivity at the 'sample-level":["0.9659999999999992","0.9660000000000005"],"Report the specificity at the 'sample-level":["0.9939999999999994","0.9940000000000008"],"Report the accuracy at the 'sample-level":["0.992","0.992"],"Report the AUC at the 'patient-level":["0.9979999999999992","0.9980000000000006"],"Report the sensitivity at the 'patient-level":["1.0","1.0"],"Report the specificity at the 'patient-level":["0.972","0.972"],"Report the accuracy at the 'patient-level":["0.9779999999999994","0.9780000000000008"]}],["capsule-0940461-gold0",{"Report the best test R^2 value for c = 1.0":["0.8259","0.8259"],"Report the best test RMSE value for c = 1.0":["0.2806","0.2806"]}],["capsule-0940461-empty",{"Report the best test R^2 value for c = 1.0":["0.8259","0.8259"],"Report the best test RMSE value for c = 1.0":["0.2806","0.2806"]}],["capsule-0940461-perturbed",{"Report the best test R^2 value for c = 1.0":["0.8259","0.8259"],"Report the best test RMSE value for c = 1.0":["0.2806","0.2806"]}],["capsule-1906954-gold0",{"Report the Delta value for Italy":["0.459","0.459"],"Report the Delta value for adults":["0.09199999999999993","0.0920000000000001"]}],["capsule-1906954-empty",{"Report the Delta value for Italy":["0.459","0.459"],"Report the Delta value for adults":["0.09199999999999993","0.0920000000000001"]}],["capsule-1906954-perturbed",{"Report the Delta value for Italy":["0.459","0.459"],"Report the Delta value for adults":["0.09199999999999993","0.0920000000000001"]}],["capsule-3249574-gold0",{"Report the F1-score after epoch 200":["0.8491784594348933","1.0816815405651068"]}],["capsule-3249574-empty",{"Report the F1-score after epoch 200":["0.8491784594348933","1.0816815405651068"]}],["capsule-3249574-perturbed",{"Report the F1-score after epoch 200":["0.8491784594348933","1.0816815405651068"]}],["capsule-4098236-gold0",{"Report the exact match of the classification":["0.27338983050847454","0.27338983050847454"],"Report the hamming loss of the classification":["0.2262241054613936","0.2262241054613936"]}],["capsule-4098236-empty",{"Report the exact match of the classification":["0.27338983050847454","0.27338983050847454"],"Report the hamming loss of the classification":["0.2262241054613936","0.2262241054613936"]}],["capsule-4098236-perturbed",{"Report the exact match of the classification":["0.27338983050847454","0.27338983050847454"],"Report the hamming loss of the classification":["0.2262241054613936","0.2262241054613936"]}],["capsule-5286757-gold0",{"Report the train loss after training the final epoch (epoch 9":["0.03053996693767207","0.06951743742173991"]}],["capsule-5286757-empty",{"Report the train loss after training the final epoch (epoch 9":["0.03053996693767207","0.06951743742173991"]}],["capsule-5286757-perturbed",{"Report the train loss after training the final epoch (epoch 9":["0.03053996693767207","0.06951743742173991"]}],["capsule-6133093-gold0",{"Report the estimate for the Label2 attribute and Attackers level in the Average Marginal Component Effects (AMCE) table of model6_c":["0.0685169","0.0685169"]}],["capsule-6133093-empty",{"Report the estimate for the Label2 attribute and Attackers level in the Average Marginal Component Effects (AMCE) table of model6_c":["0.0685169","0.0685169"]}],["capsule-6133093-perturbed",{"Report the estimate for the Label2 attribute and Attackers level in the Average Marginal Component Effects (AMCE) table of model6_c":["0.0685169","0.0685169"]}],["capsule-7935517-gold0",{"fig From the plot sampling rho, report the rho value corresponding to the solid red line":["0.0","0.0"]}],["capsule-7935517-empty",{"fig From the plot sampling rho, report the rho value corresponding to the solid red line":["0.0","0.0"]}],["capsule-7935517-perturbed",{"fig From the plot sampling rho, report the rho value corresponding to the solid red line":["0.0","0.0"]}],["capsule-9070543-gold0",{}],["capsule-9070543-empty",{}],["capsule-9070543-perturbed",{}]],"numeric":[[0.0,[4.440892098500626e-16,4.440892098500626e-16],false],[4.440892098500626e-16,[4.440892098500626e-16,4.440892098500626e-16],true],[0.12349,[0.1235,0.2],false],[2e-05,[1e-05,3e-05],true],["2e-05",[1e-05,3e-05],true],["abc",[0,1],false],[null,[0,1],false],[true,[0,2],true],[1.0,[NaN,NaN],false]],"gpu_specs":{"c-gpu":[["c-gpu/code/run.py","x"],["c-gpu/REPRODUCING.md","Requires a GPU (CUDA)."]],"c-cpu":[["c-cpu/REPRODUCING.md","Run on CPU only."]],"c-none":[["c-none/code/run.py","gpu"]],"c-first":[["c-first/REPRODUCING.md","cpu"],["c-first/sub/REPRODUCING.md","gpu"]],"c-nested-gpu":[["c-nested-gpu/environment/REPRODUCING.md","uses Gpu"]]},"gpu":{"c-gpu":true,"c-cpu":false,"c-none":false,"c-first":false,"c-nested-gpu":true}}"""
)


def _scorer_module() -> types.ModuleType:
    pytest.importorskip("numpy")
    mod = types.ModuleType("core_bench_run_scorer")
    exec(compile(cbh.RUN_SCORER_PY, "run_scorer.py", "exec"), mod.__dict__)  # noqa: S102
    return mod


# --- vendored scorer == pinned upstream --------------------------------------


@pytest.mark.parametrize(
    "case", FIXTURES["cases"], ids=[c[0] for c in FIXTURES["cases"]]
)
def test_evaluate_results_matches_upstream(case) -> None:
    pytest.importorskip("scipy")
    _name, agent, gt, expected = case
    assert _scorer_module().evaluate_results(agent, gt) == expected


@pytest.mark.parametrize(
    "case", FIXTURES["intervals"], ids=[c[0] for c in FIXTURES["intervals"]]
)
def test_prediction_intervals_match_upstream(case) -> None:
    pytest.importorskip("scipy")
    name, expected = case
    _, _agent, gt, _ = next(c for c in FIXTURES["cases"] if c[0] == name)
    mod = _scorer_module()
    gts = [mod.strip_keys(r) for r in gt]
    numeric_keys, _, _ = mod.categorize_keys(gts)
    got = mod.calculate_prediction_intervals(gts, numeric_keys)
    assert set(got) == set(expected)
    for key, (lo, hi) in expected.items():
        for a, b in zip(got[key], (float(lo), float(hi))):
            if math.isnan(b):
                assert math.isnan(a)
            else:
                assert math.isclose(float(a), b, rel_tol=1e-12, abs_tol=0.0)


@pytest.mark.parametrize(
    "case", FIXTURES["numeric"], ids=[repr(c[0]) for c in FIXTURES["numeric"]]
)
def test_check_numeric_answer_matches_upstream(case) -> None:
    value, interval, expected = case
    assert _scorer_module().check_numeric_answer(value, tuple(interval)) is expected


def test_audit_divergences_now_match_upstream() -> None:
    """Cases where the previous (unpinned blob/main) port disagreed with
    upstream at the evaluate_results level.  The interval-level divergences
    (0.12349 vs lower bound 0.1235 -> upstream False; 2e-05 in
    (1e-05, 3e-05) -> upstream True) are in FIXTURES["numeric"]."""
    pytest.importorskip("scipy")
    by_name = {c[0]: c for c in FIXTURES["cases"]}
    mod = _scorer_module()
    for name in (
        "5975162-zero-mean",  # upstream wrong; old port right (isclose branch)
        "single-trial-exact",  # upstream NaN interval -> wrong; old port right
    ):
        _, agent, gt, expected = by_name[name]
        assert mod.evaluate_results(agent, gt) == expected, name
    # The oracle for capsule-5975162 (gold 4.44e-16, zero variance) passes.
    _, agent, gt, expected = by_name["5975162-gold0"]
    assert expected["correct_written_answers"] == expected["total_written_questions"]
    assert mod.evaluate_results(agent, gt) == expected


def test_no_import_fallback_in_scorer() -> None:
    src = cbh.RUN_SCORER_PY
    assert "except ImportError" not in src
    assert "round_to_gt_precision" not in src
    assert "isclose" not in src
    assert cbh.INSPECT_EVALS_COMMIT in src


# --- run_scorer.py end to end ------------------------------------------------


def _run_scorer(tmp_path: Path, report: bytes | None | str, gold, config_text=None):
    root = tmp_path
    for d in ("app", "tests", "logs/verifier"):
        (root / d).mkdir(parents=True, exist_ok=True)
    src = (
        cbh.RUN_SCORER_PY.replace("/app/", f"{root}/app/")
        .replace("/tests/", f"{root}/tests/")
        .replace("/logs/", f"{root}/logs/")
    )
    (root / "tests" / "run_scorer.py").write_text(src)
    cfg = config_text if config_text is not None else json.dumps({"gold_results": gold})
    (root / "tests" / "config.json").write_text(cfg)
    rp = root / "app" / "report.json"
    if report == "DIR":
        rp.mkdir()
    elif report is not None:
        rp.write_bytes(report)
    proc = subprocess.run(
        [sys.executable, str(root / "tests" / "run_scorer.py")],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    reward_file = root / "logs" / "verifier" / "reward.txt"
    reward = float(reward_file.read_text()) if reward_file.exists() else None
    return proc.returncode, reward


_GOLD = [
    {"acc": 0.9, "label": "Yes", "fig x": 2.0},
    {"acc": 0.92, "label": "yes", "fig x": 2.0},
]


@pytest.mark.parametrize(
    "report, expected",
    [
        (None, 0.0),  # FileNotFoundError -> INCORRECT
        (b"", 0.0),  # invalid json -> INCORRECT
        (b"not json", 0.0),
        (b"[1, 2]", 0.0),  # valid json, not a dict -> nothing correct
        (b'{"acc": 0.91, "label": "yes.", "fig x": "2"}', 1.0),
        (b'{"acc": "91%", "label": "yes", "fig x": 2}', 0.0),  # 91 not in PI
        (b'{"acc": 0.91, "label": "yes"}', 0.0),  # vision question missing
    ],
)
def test_scorer_outcomes(tmp_path: Path, report, expected) -> None:
    pytest.importorskip("scipy")
    rc, reward = _run_scorer(tmp_path, report, _GOLD)
    assert rc == 0
    assert reward == expected


@pytest.mark.parametrize(
    "report", [b"\xff\xfe\x00bad", "DIR"], ids=["non-utf8", "directory"]
)
def test_scorer_read_errors_are_verifier_failures(tmp_path: Path, report) -> None:
    # Upstream only maps FileNotFoundError to INCORRECT; other read errors
    # raise (a sample error), so no reward may be written.
    rc, reward = _run_scorer(tmp_path, report, _GOLD)
    assert rc != 0
    assert reward is None


def test_scorer_broken_config_is_verifier_failure(tmp_path: Path) -> None:
    rc, reward = _run_scorer(tmp_path, None, _GOLD, config_text="{ nope")
    assert rc != 0
    assert reward is None


def test_deeply_nested_report_is_verifier_failure(tmp_path: Path) -> None:
    # json.loads raises RecursionError (not JSONDecodeError) -> upstream
    # sample error -> no reward.
    rc, reward = _run_scorer(tmp_path, b"[" * 200000, _GOLD)
    assert rc != 0
    assert reward is None


# --- GPU filter port ---------------------------------------------------------


def test_requires_gpu_matches_upstream(tmp_path: Path) -> None:
    for cid, members in FIXTURES["gpu_specs"].items():
        path = tmp_path / f"{cid}.tar.gz"
        with tarfile.open(path, "w:gz") as tar:
            for name, text in members:
                data = text.encode()
                info = tarfile.TarInfo(name)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
        assert cbh.requires_gpu(path) is FIXTURES["gpu"][cid], cid


def test_gpu_filter_uses_cache_and_refuses_offline_download(tmp_path, monkeypatch):
    monkeypatch.setenv("ASTA_BENCH_CORE_BENCH_CAPSULE_DIR", str(tmp_path))
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    cached = tmp_path / "capsule-1.tar.gz"
    cached.write_bytes(b"x")
    assert cbh._ensure_capsule_tarball("capsule-1") == cached
    with pytest.raises(RuntimeError, match="not cached"):
        cbh._ensure_capsule_tarball("capsule-2")


# --- generated task shape ----------------------------------------------------


def _write_task(tmp_path: Path, split: str = "validation") -> Path:
    gold = [
        {"Report the acc.": 0.5, "fig label": "a"},
        {"Report the acc.": 0.6, "fig label": "a"},
    ]
    record = cbh.SampleRecord(
        sample_id="capsule-0000001",
        split=split,
        instruction="run main.py and report the accuracy",
        target=json.dumps(gold),
        metadata={
            "capsule_id": "capsule-0000001",
            "field": "CS",
            "language": "Python",
            "results": gold,
        },
        workspace_files={},
    )
    builder = cbh.CoreBenchHardBuilder(tmp_path)
    task_dir = tmp_path / "t"
    task_dir.mkdir()
    builder.write_task(record, task_dir)
    return task_dir


def test_instruction_is_upstream_prompt(tmp_path: Path) -> None:
    text = (_write_task(tmp_path) / "instruction.md").read_text()
    assert text == (
        "Task: codeocean_hard\n\nYour goal is to test the computational reproducibility "
        "of the repository cloned to your current directory, which is code from a "
        "scientific paper. Specifically, you need to run main.py and report the "
        "accuracy. Save your report to a file named report.json in the environment "
        "directory you started in that contains the capsule itself, where you fill in "
        "all of the following fields: dict_keys(['Report the acc.', 'fig label']). The "
        "absolute file path for report.json should just be /app/report.json. You should "
        "install all of the requirements found in the Readme file and then run the "
        "commands necessary to answer the questions.\n"
    )
    assert "CORE-Bench" not in text and "corebench" not in text.lower()


def test_dockerfile_strips_answer_files(tmp_path: Path) -> None:
    df = (_write_task(tmp_path) / "environment" / "Dockerfile").read_text()
    assert "capsules/capsule-0000001.tar.gz" in df
    assert (
        "tar --no-same-owner --strip-components=1 -xzf /tmp/capsule.tar.gz -C /app"
        in df
    )
    assert "rm -rf results;" in df
    assert "rm -f REPRODUCING.md run run.sh;" in df
    assert "rm -rf environment;" in df
    assert "for p in results REPRODUCING.md run run.sh environment; do" in df
    assert '"scipy==1.17.1"' in df and '"numpy==2.4.4"' in df
    # The capsule layer precedes the workspace copy; set -e fails the build.
    assert df.index("set -eux") < df.index("COPY workspace/inspect_config.json")


def test_oracle_writes_report_and_bridge_exports_it(tmp_path: Path) -> None:
    task_dir = _write_task(tmp_path, split="validation")
    solve = (task_dir / "solution" / "solve.sh").read_text()
    assert "/app/report.json" in solve and "answer.txt" not in solve
    cfg = json.loads(
        (task_dir / "environment" / "workspace" / "inspect_config.json").read_text()
    )
    assert cfg["task"] == "astabench/core_bench"
    assert cfg["task_args"] == {"split": "train", "capsule_ids": "[capsule-0000001]"}
    assert cfg["export_files"] == [{"src": "report.json", "dest": "/app/report.json"}]
    assert cfg["require_tools"] is True
    assert "--sandbox" in cfg["eval_args"]
    tests_cfg = json.loads((task_dir / "tests" / "config.json").read_text())
    assert "capsule_url" not in tests_cfg
