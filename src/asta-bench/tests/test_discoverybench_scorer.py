"""Offline fidelity tests for the discoverybench verifier (tests/run_scorer.py).

The expected values below were computed by running the *real* upstream scorer
(astabench/evals/discoverybench/task.py::score_discoverybench, fork
smiky2011/asta-bench@claude-haiku-judges commit 17c84ca, inspect_ai 0.3.203)
with Inspect's `get_model` replaced by a scripted fake that records every
outgoing request.  For each case we pinned:

* the outcome (HMS reward, or a raised sample error);
* every judge request: sha256 (first 16 hex) of the system and user message,
  the model (`anthropic/claude-haiku-4-5`) and generation config
  (temperature 0, max_tokens 250, no response schema).

Here the generated scorer runs against a stub `litellm` fed the same scripted
judge replies and must reproduce all of it.  No network, no upstream checkout.
"""

from __future__ import annotations

import builtins
import hashlib
import importlib.util
import json
import re
import sys
import types
from pathlib import Path

import pytest

from asta_bench.benchmarks import discoverybench as db
from asta_bench.benchmarks.base import SampleRecord

API_ERROR = "__API_ERROR__"
MODEL = "anthropic/claude-haiku-4-5"

# fmt: off
FIXTURES = json.loads(r'''
{
 "format_query": {"input": {"data_folder": "folder_x", "metadata": {"datasets": [{"columns": {"raw": [{"description": "Age in years (%d)", "name": "age"}, {"description": "Body-mass \u201cindex\u201d", "name": "bmi"}]}, "description": "Survey of \"adults\" \u2014 50% rural; it's {braced}\nsecond line", "name": "d.csv"}, {"columns": {"raw": [{"description": "x\ty", "name": "x"}]}, "description": "Second", "name": "e.csv"}]}, "query": "Q with %s and {b}"}, "sample_input_sha256": "1e0fb4d71b209cfd7e91b5d04b4ce02251c86db526a0e7be6ed2f4c358f89494"},
 "inputs": {
  "plain": {"dataset_meta": {"datasets": [{"columns": {"raw": [{"description": "Education expenditure", "name": "spend"}, {"description": "GDP per capita", "name": "gdp"}]}, "description": "World Bank panel data, 1975-2015.", "name": "wb.csv"}]}, "gold_hypothesis": "Higher education spending is associated with higher GDP per capita in LMC countries.", "gold_workflow": "1. Load the CSV. 2. Filter LMC rows. 3. Correlate spending with GDP.", "name": "plain", "query": "What is the relationship between education spending and GDP?"},
  "tricky": {"dataset_meta": {"datasets": [{"columns": {"raw": [{"description": "Age in years (%d)", "name": "age"}, {"description": "Body-mass \u201cindex\u201d", "name": "bmi"}]}, "description": "Survey of \"adults\" \u2014 50% rural; it's {braced}\nsecond line", "name": "d.csv"}, {"columns": {"raw": [{"description": "x\ty", "name": "x"}]}, "description": "Second", "name": "e.csv"}]}, "gold_hypothesis": "BMI rises with \"age\" by 5%\nin rural {areas}", "gold_workflow": "Loaded d.csv; ran OLS (p<0.05) \u2014 done", "name": "tricky", "query": "How does %s BMI relate to {age}?"}
 },
 "cases": {
  "plain::answer_array": {"answer": "[1, 2, 3]", "outcome": {"reward": 0.0}, "requests": [["a72157819fb04f58", "1da6568eecab747e"], ["a72157819fb04f58", "4360e63e2ac06363"], ["a72157819fb04f58", "e8e96dba25ca9fa7"]], "script": ["{\"context\": \"adults in rural areas\"}", "{\"context\": \"adults in rural areas\"}", "{\"match\": false, \"reason\": \"diff\"}"]},
  "plain::answer_empty": {"answer": "", "outcome": {"reward": 0.0}, "requests": [["a72157819fb04f58", "1da6568eecab747e"], ["a72157819fb04f58", "4360e63e2ac06363"], ["a72157819fb04f58", "e8e96dba25ca9fa7"]], "script": ["{\"context\": \"adults in rural areas\"}", "{\"context\": \"adults in rural areas\"}", "{\"match\": false, \"reason\": \"diff\"}"]},
  "plain::answer_extra_keys_prose": {"answer": "Final: {\"hypothesis\": \"h\", \"workflow\": \"w\", \"x\": 1} done", "outcome": {"reward": 0.8}, "requests": [["a72157819fb04f58", "1da6568eecab747e"], ["a72157819fb04f58", "5a7442537157a075"], ["a72157819fb04f58", "fa78aba45a4e3b5c"], ["deb934ce6386ddab", "e9293742f88a7cce"], ["deb934ce6386ddab", "8002c52aa5faef12"]], "script": ["{\"context\": \"adults in rural areas\"}", "{\"context\": \"adults in rural areas\"}", "{\"match\": true, \"reason\": \"same\"}", "{\"sizeA\": 3, \"sizeB\": 2, \"intersection\": 2, \"explanation\": \"e\"}", "{\"answer\": \"A) very similar\", \"explanation\": \"e\"}"]},
  "plain::answer_fenced_two_objects": {"answer": "```json\n{\"hypothesis\": \"h\", \"workflow\": \"w\"}\n```\n{\"a\": 1}", "outcome": {"reward": 0.0}, "requests": [["a72157819fb04f58", "1da6568eecab747e"], ["a72157819fb04f58", "4360e63e2ac06363"], ["a72157819fb04f58", "e8e96dba25ca9fa7"]], "script": ["{\"context\": \"adults in rural areas\"}", "{\"context\": \"adults in rural areas\"}", "{\"match\": false, \"reason\": \"diff\"}"]},
  "plain::answer_hypothesis_null": {"answer": "{\"hypothesis\": null, \"workflow\": \"w\"}", "outcome": {"reward": 0.0}, "requests": [], "script": []},
  "plain::answer_inner_number": {"answer": "x {1} y", "outcome": {"reward": 0.0}, "requests": [["a72157819fb04f58", "1da6568eecab747e"], ["a72157819fb04f58", "0df26384afce2bf2"], ["a72157819fb04f58", "999e46856119742d"]], "script": ["{\"context\": \"adults in rural areas\"}", "{\"context\": \"adults in rural areas\"}", "{\"match\": false, \"reason\": \"diff\"}"]},
  "plain::answer_missing_workflow": {"answer": "{\"hypothesis\": \"h\"}", "outcome": {"reward": 0.0}, "requests": [], "script": []},
  "plain::answer_prose": {"answer": "I think BMI rises.", "outcome": {"reward": 0.8}, "requests": [["a72157819fb04f58", "1da6568eecab747e"], ["a72157819fb04f58", "4360e63e2ac06363"], ["a72157819fb04f58", "e8e96dba25ca9fa7"], ["deb934ce6386ddab", "162e9179aa87eab1"], ["deb934ce6386ddab", "95b501e7b10f9c4a"]], "script": ["{\"context\": \"adults in rural areas\"}", "{\"context\": \"adults in rural areas\"}", "{\"match\": true, \"reason\": \"same\"}", "{\"sizeA\": 3, \"sizeB\": 2, \"intersection\": 2, \"explanation\": \"e\"}", "{\"answer\": \"A) very similar\", \"explanation\": \"e\"}"]},
  "plain::answer_workflow_int": {"answer": "{\"hypothesis\": \"h\", \"workflow\": 3}", "outcome": {"reward": 0.0}, "requests": [], "script": []},
  "plain::api_error_extract": {"answer": "{\"hypothesis\": \"BMI \\\"grows\\\" 5% with age\\nstrongly\", \"workflow\": \"OLS {fit}\"}", "outcome": {"error": "RuntimeError"}, "requests": [["a72157819fb04f58", "1da6568eecab747e"]], "script": ["__API_ERROR__"]},
  "plain::api_error_var": {"answer": "{\"hypothesis\": \"BMI \\\"grows\\\" 5% with age\\nstrongly\", \"workflow\": \"OLS {fit}\"}", "outcome": {"error": "RuntimeError"}, "requests": [["a72157819fb04f58", "1da6568eecab747e"], ["a72157819fb04f58", "2e08f479394468b1"], ["a72157819fb04f58", "eff05d0c4b855dd2"], ["deb934ce6386ddab", "1858728598e4e974"]], "script": ["{\"context\": \"adults in rural areas\"}", "{\"context\": \"adults in rural areas\"}", "{\"match\": true, \"reason\": \"same\"}", "__API_ERROR__"]},
  "plain::context_mismatch": {"answer": "{\"hypothesis\": \"BMI \\\"grows\\\" 5% with age\\nstrongly\", \"workflow\": \"OLS {fit}\"}", "outcome": {"reward": 0.0}, "requests": [["a72157819fb04f58", "1da6568eecab747e"], ["a72157819fb04f58", "2e08f479394468b1"], ["a72157819fb04f58", "eff05d0c4b855dd2"]], "script": ["{\"context\": \"adults in rural areas\"}", "{\"context\": \"adults in rural areas\"}", "{\"match\": false, \"reason\": \"diff\"}"]},
  "plain::full_rel_A_fenced": {"answer": "{\"hypothesis\": \"BMI \\\"grows\\\" 5% with age\\nstrongly\", \"workflow\": \"OLS {fit}\"}", "outcome": {"reward": 0.8}, "requests": [["a72157819fb04f58", "1da6568eecab747e"], ["a72157819fb04f58", "2e08f479394468b1"], ["a72157819fb04f58", "eff05d0c4b855dd2"], ["deb934ce6386ddab", "1858728598e4e974"], ["deb934ce6386ddab", "e708264d179c29c9"]], "script": ["{\"context\": \"adults in rural areas\"}", "```json\n{\"context\": \"adults in rural areas\"}\n```", "{\"match\": true, \"reason\": \"same\"}", "```json\n{\"sizeA\": 3, \"sizeB\": 2, \"intersection\": 2, \"explanation\": \"e\"}\n```", "Sure:\n{\"answer\": \"A) very similar\", \"explanation\": \"e\"}"]},
  "plain::full_rel_B": {"answer": "{\"hypothesis\": \"BMI \\\"grows\\\" 5% with age\\nstrongly\", \"workflow\": \"OLS {fit}\"}", "outcome": {"reward": 0.4}, "requests": [["a72157819fb04f58", "1da6568eecab747e"], ["a72157819fb04f58", "2e08f479394468b1"], ["a72157819fb04f58", "eff05d0c4b855dd2"], ["deb934ce6386ddab", "1858728598e4e974"], ["deb934ce6386ddab", "e708264d179c29c9"]], "script": ["{\"context\": \"adults in rural areas\"}", "{\"context\": \"adults in rural areas\"}", "{\"match\": true, \"reason\": \"same\"}", "{\"sizeA\": 3, \"sizeB\": 2, \"intersection\": 2, \"explanation\": \"e\"}", "{\"answer\": \"B) similar but general than HypoA\", \"explanation\": \"e\"}"]},
  "plain::gen_ctx_list_raises": {"answer": "{\"hypothesis\": \"BMI \\\"grows\\\" 5% with age\\nstrongly\", \"workflow\": \"OLS {fit}\"}", "outcome": {"error": "AttributeError"}, "requests": [["a72157819fb04f58", "1da6568eecab747e"], ["a72157819fb04f58", "2e08f479394468b1"]], "script": ["{\"context\": \"adults in rural areas\"}", "[1, 2]"]},
  "plain::gold_ctx_unparseable": {"answer": "{\"hypothesis\": \"BMI \\\"grows\\\" 5% with age\\nstrongly\", \"workflow\": \"OLS {fit}\"}", "outcome": {"reward": 0.8}, "requests": [["a72157819fb04f58", "1da6568eecab747e"], ["a72157819fb04f58", "2e08f479394468b1"], ["a72157819fb04f58", "5b42e69cba4e7835"], ["deb934ce6386ddab", "1858728598e4e974"], ["deb934ce6386ddab", "e708264d179c29c9"]], "script": ["not json", "{\"context\": \"adults in rural areas\"}", "{\"match\": true, \"reason\": \"same\"}", "{\"sizeA\": 3, \"sizeB\": 2, \"intersection\": 2, \"explanation\": \"e\"}", "{\"answer\": \"A) very similar\", \"explanation\": \"e\"}"]},
  "plain::match_missing_key": {"answer": "{\"hypothesis\": \"BMI \\\"grows\\\" 5% with age\\nstrongly\", \"workflow\": \"OLS {fit}\"}", "outcome": {"reward": 0.0}, "requests": [["a72157819fb04f58", "1da6568eecab747e"], ["a72157819fb04f58", "2e08f479394468b1"], ["a72157819fb04f58", "eff05d0c4b855dd2"]], "script": ["{\"context\": \"adults in rural areas\"}", "{\"context\": \"adults in rural areas\"}", "{\"reason\": \"x\"}"]},
  "plain::match_string_false_is_truthy": {"answer": "{\"hypothesis\": \"BMI \\\"grows\\\" 5% with age\\nstrongly\", \"workflow\": \"OLS {fit}\"}", "outcome": {"reward": 0.8}, "requests": [["a72157819fb04f58", "1da6568eecab747e"], ["a72157819fb04f58", "2e08f479394468b1"], ["a72157819fb04f58", "eff05d0c4b855dd2"], ["deb934ce6386ddab", "1858728598e4e974"], ["deb934ce6386ddab", "e708264d179c29c9"]], "script": ["{\"context\": \"adults in rural areas\"}", "{\"context\": \"adults in rural areas\"}", "{\"match\": \"false\"}", "{\"sizeA\": 3, \"sizeB\": 2, \"intersection\": 2, \"explanation\": \"e\"}", "{\"answer\": \"A) very similar\", \"explanation\": \"e\"}"]},
  "plain::match_unparseable_4x_then_ok": {"answer": "{\"hypothesis\": \"BMI \\\"grows\\\" 5% with age\\nstrongly\", \"workflow\": \"OLS {fit}\"}", "outcome": {"reward": 0.8}, "requests": [["a72157819fb04f58", "1da6568eecab747e"], ["a72157819fb04f58", "2e08f479394468b1"], ["a72157819fb04f58", "eff05d0c4b855dd2"], ["a72157819fb04f58", "eff05d0c4b855dd2"], ["a72157819fb04f58", "eff05d0c4b855dd2"], ["a72157819fb04f58", "eff05d0c4b855dd2"], ["a72157819fb04f58", "eff05d0c4b855dd2"], ["deb934ce6386ddab", "1858728598e4e974"], ["deb934ce6386ddab", "e708264d179c29c9"]], "script": ["{\"context\": \"adults in rural areas\"}", "{\"context\": \"adults in rural areas\"}", "nope", "nope", "nope", "nope", "{\"match\": true, \"reason\": \"same\"}", "{\"sizeA\": 3, \"sizeB\": 2, \"intersection\": 2, \"explanation\": \"e\"}", "{\"answer\": \"A) very similar\", \"explanation\": \"e\"}"]},
  "plain::match_unparseable_5x_raises": {"answer": "{\"hypothesis\": \"BMI \\\"grows\\\" 5% with age\\nstrongly\", \"workflow\": \"OLS {fit}\"}", "outcome": {"error": "AttributeError"}, "requests": [["a72157819fb04f58", "1da6568eecab747e"], ["a72157819fb04f58", "2e08f479394468b1"], ["a72157819fb04f58", "eff05d0c4b855dd2"], ["a72157819fb04f58", "eff05d0c4b855dd2"], ["a72157819fb04f58", "eff05d0c4b855dd2"], ["a72157819fb04f58", "eff05d0c4b855dd2"], ["a72157819fb04f58", "eff05d0c4b855dd2"]], "script": ["{\"context\": \"adults in rural areas\"}", "{\"context\": \"adults in rural areas\"}", "nope", "nope", "nope", "nope", "nope"]},
  "plain::rel_C": {"answer": "{\"hypothesis\": \"BMI \\\"grows\\\" 5% with age\\nstrongly\", \"workflow\": \"OLS {fit}\"}", "outcome": {"reward": 0.0}, "requests": [["a72157819fb04f58", "1da6568eecab747e"], ["a72157819fb04f58", "2e08f479394468b1"], ["a72157819fb04f58", "eff05d0c4b855dd2"], ["deb934ce6386ddab", "1858728598e4e974"], ["deb934ce6386ddab", "e708264d179c29c9"]], "script": ["{\"context\": \"adults in rural areas\"}", "{\"context\": \"adults in rural areas\"}", "{\"match\": true, \"reason\": \"same\"}", "{\"sizeA\": 3, \"sizeB\": 2, \"intersection\": 2, \"explanation\": \"e\"}", "{\"answer\": \"C) different\"}"]},
  "plain::rel_answer_not_str": {"answer": "{\"hypothesis\": \"BMI \\\"grows\\\" 5% with age\\nstrongly\", \"workflow\": \"OLS {fit}\"}", "outcome": {"reward": 0.0}, "requests": [["a72157819fb04f58", "1da6568eecab747e"], ["a72157819fb04f58", "2e08f479394468b1"], ["a72157819fb04f58", "eff05d0c4b855dd2"], ["deb934ce6386ddab", "1858728598e4e974"], ["deb934ce6386ddab", "e708264d179c29c9"]], "script": ["{\"context\": \"adults in rural areas\"}", "{\"context\": \"adults in rural areas\"}", "{\"match\": true, \"reason\": \"same\"}", "{\"sizeA\": 3, \"sizeB\": 2, \"intersection\": 2, \"explanation\": \"e\"}", "{\"answer\": 1}"]},
  "plain::rel_other": {"answer": "{\"hypothesis\": \"BMI \\\"grows\\\" 5% with age\\nstrongly\", \"workflow\": \"OLS {fit}\"}", "outcome": {"reward": 0.0}, "requests": [["a72157819fb04f58", "1da6568eecab747e"], ["a72157819fb04f58", "2e08f479394468b1"], ["a72157819fb04f58", "eff05d0c4b855dd2"], ["deb934ce6386ddab", "1858728598e4e974"], ["deb934ce6386ddab", "e708264d179c29c9"]], "script": ["{\"context\": \"adults in rural areas\"}", "{\"context\": \"adults in rural areas\"}", "{\"match\": true, \"reason\": \"same\"}", "{\"sizeA\": 3, \"sizeB\": 2, \"intersection\": 2, \"explanation\": \"e\"}", "{\"answer\": \"maybe\"}"]},
  "plain::rel_unparseable": {"answer": "{\"hypothesis\": \"BMI \\\"grows\\\" 5% with age\\nstrongly\", \"workflow\": \"OLS {fit}\"}", "outcome": {"reward": 0.0}, "requests": [["a72157819fb04f58", "1da6568eecab747e"], ["a72157819fb04f58", "2e08f479394468b1"], ["a72157819fb04f58", "eff05d0c4b855dd2"], ["deb934ce6386ddab", "1858728598e4e974"], ["deb934ce6386ddab", "e708264d179c29c9"]], "script": ["{\"context\": \"adults in rural areas\"}", "{\"context\": \"adults in rural areas\"}", "{\"match\": true, \"reason\": \"same\"}", "{\"sizeA\": 3, \"sizeB\": 2, \"intersection\": 2, \"explanation\": \"e\"}", "no"]},
  "plain::var_missing_explanation": {"answer": "{\"hypothesis\": \"BMI \\\"grows\\\" 5% with age\\nstrongly\", \"workflow\": \"OLS {fit}\"}", "outcome": {"reward": 0.0}, "requests": [["a72157819fb04f58", "1da6568eecab747e"], ["a72157819fb04f58", "2e08f479394468b1"], ["a72157819fb04f58", "eff05d0c4b855dd2"], ["deb934ce6386ddab", "1858728598e4e974"], ["deb934ce6386ddab", "e708264d179c29c9"]], "script": ["{\"context\": \"adults in rural areas\"}", "{\"context\": \"adults in rural areas\"}", "{\"match\": true, \"reason\": \"same\"}", "{\"sizeA\": 2, \"sizeB\": 2, \"intersection\": 2}", "{\"answer\": \"A) very similar\", \"explanation\": \"e\"}"]},
  "plain::var_sizeB_zero": {"answer": "{\"hypothesis\": \"BMI \\\"grows\\\" 5% with age\\nstrongly\", \"workflow\": \"OLS {fit}\"}", "outcome": {"reward": 0.0}, "requests": [["a72157819fb04f58", "1da6568eecab747e"], ["a72157819fb04f58", "2e08f479394468b1"], ["a72157819fb04f58", "eff05d0c4b855dd2"], ["deb934ce6386ddab", "1858728598e4e974"], ["deb934ce6386ddab", "e708264d179c29c9"]], "script": ["{\"context\": \"adults in rural areas\"}", "{\"context\": \"adults in rural areas\"}", "{\"match\": true, \"reason\": \"same\"}", "{\"sizeA\": 2, \"sizeB\": 0, \"intersection\": 1, \"explanation\": \"\"}", "{\"answer\": \"A) very similar\", \"explanation\": \"e\"}"]},
  "plain::var_string_count": {"answer": "{\"hypothesis\": \"BMI \\\"grows\\\" 5% with age\\nstrongly\", \"workflow\": \"OLS {fit}\"}", "outcome": {"reward": 0.0}, "requests": [["a72157819fb04f58", "1da6568eecab747e"], ["a72157819fb04f58", "2e08f479394468b1"], ["a72157819fb04f58", "eff05d0c4b855dd2"], ["deb934ce6386ddab", "1858728598e4e974"], ["deb934ce6386ddab", "e708264d179c29c9"]], "script": ["{\"context\": \"adults in rural areas\"}", "{\"context\": \"adults in rural areas\"}", "{\"match\": true, \"reason\": \"same\"}", "{\"sizeA\": \"2\", \"sizeB\": \"2\", \"intersection\": 1, \"explanation\": \"\"}", "{\"answer\": \"A) very similar\", \"explanation\": \"e\"}"]},
  "plain::var_unparseable": {"answer": "{\"hypothesis\": \"BMI \\\"grows\\\" 5% with age\\nstrongly\", \"workflow\": \"OLS {fit}\"}", "outcome": {"reward": 0.0}, "requests": [["a72157819fb04f58", "1da6568eecab747e"], ["a72157819fb04f58", "2e08f479394468b1"], ["a72157819fb04f58", "eff05d0c4b855dd2"], ["deb934ce6386ddab", "1858728598e4e974"], ["deb934ce6386ddab", "e708264d179c29c9"]], "script": ["{\"context\": \"adults in rural areas\"}", "{\"context\": \"adults in rural areas\"}", "{\"match\": true, \"reason\": \"same\"}", "no", "{\"answer\": \"A) very similar\", \"explanation\": \"e\"}"]},
  "tricky::answer_array": {"answer": "[1, 2, 3]", "outcome": {"reward": 0.0}, "requests": [["a72157819fb04f58", "3ddf4ce3a0df48a7"], ["a72157819fb04f58", "42e85b9df23b47ec"], ["a72157819fb04f58", "a96a0c0fd3838896"]], "script": ["{\"context\": \"adults in rural areas\"}", "{\"context\": \"adults in rural areas\"}", "{\"match\": false, \"reason\": \"diff\"}"]},
  "tricky::answer_empty": {"answer": "", "outcome": {"reward": 0.0}, "requests": [["a72157819fb04f58", "3ddf4ce3a0df48a7"], ["a72157819fb04f58", "42e85b9df23b47ec"], ["a72157819fb04f58", "a96a0c0fd3838896"]], "script": ["{\"context\": \"adults in rural areas\"}", "{\"context\": \"adults in rural areas\"}", "{\"match\": false, \"reason\": \"diff\"}"]},
  "tricky::answer_extra_keys_prose": {"answer": "Final: {\"hypothesis\": \"h\", \"workflow\": \"w\", \"x\": 1} done", "outcome": {"reward": 0.8}, "requests": [["a72157819fb04f58", "3ddf4ce3a0df48a7"], ["a72157819fb04f58", "88f6bcfb4f04efbf"], ["a72157819fb04f58", "8b348b45bea0eb79"], ["deb934ce6386ddab", "6c41ee00d487643e"], ["deb934ce6386ddab", "e977ac27a3227de7"]], "script": ["{\"context\": \"adults in rural areas\"}", "{\"context\": \"adults in rural areas\"}", "{\"match\": true, \"reason\": \"same\"}", "{\"sizeA\": 3, \"sizeB\": 2, \"intersection\": 2, \"explanation\": \"e\"}", "{\"answer\": \"A) very similar\", \"explanation\": \"e\"}"]},
  "tricky::answer_fenced_two_objects": {"answer": "```json\n{\"hypothesis\": \"h\", \"workflow\": \"w\"}\n```\n{\"a\": 1}", "outcome": {"reward": 0.0}, "requests": [["a72157819fb04f58", "3ddf4ce3a0df48a7"], ["a72157819fb04f58", "42e85b9df23b47ec"], ["a72157819fb04f58", "a96a0c0fd3838896"]], "script": ["{\"context\": \"adults in rural areas\"}", "{\"context\": \"adults in rural areas\"}", "{\"match\": false, \"reason\": \"diff\"}"]},
  "tricky::answer_hypothesis_null": {"answer": "{\"hypothesis\": null, \"workflow\": \"w\"}", "outcome": {"reward": 0.0}, "requests": [], "script": []},
  "tricky::answer_inner_number": {"answer": "x {1} y", "outcome": {"reward": 0.0}, "requests": [["a72157819fb04f58", "3ddf4ce3a0df48a7"], ["a72157819fb04f58", "a48e852f9b4f2015"], ["a72157819fb04f58", "c4ccec51a72531e8"]], "script": ["{\"context\": \"adults in rural areas\"}", "{\"context\": \"adults in rural areas\"}", "{\"match\": false, \"reason\": \"diff\"}"]},
  "tricky::answer_missing_workflow": {"answer": "{\"hypothesis\": \"h\"}", "outcome": {"reward": 0.0}, "requests": [], "script": []},
  "tricky::answer_prose": {"answer": "I think BMI rises.", "outcome": {"reward": 0.8}, "requests": [["a72157819fb04f58", "3ddf4ce3a0df48a7"], ["a72157819fb04f58", "42e85b9df23b47ec"], ["a72157819fb04f58", "a96a0c0fd3838896"], ["deb934ce6386ddab", "eac554ca601cfc19"], ["deb934ce6386ddab", "24bffe4694c65b0a"]], "script": ["{\"context\": \"adults in rural areas\"}", "{\"context\": \"adults in rural areas\"}", "{\"match\": true, \"reason\": \"same\"}", "{\"sizeA\": 3, \"sizeB\": 2, \"intersection\": 2, \"explanation\": \"e\"}", "{\"answer\": \"A) very similar\", \"explanation\": \"e\"}"]},
  "tricky::answer_workflow_int": {"answer": "{\"hypothesis\": \"h\", \"workflow\": 3}", "outcome": {"reward": 0.0}, "requests": [], "script": []},
  "tricky::api_error_extract": {"answer": "{\"hypothesis\": \"BMI \\\"grows\\\" 5% with age\\nstrongly\", \"workflow\": \"OLS {fit}\"}", "outcome": {"error": "RuntimeError"}, "requests": [["a72157819fb04f58", "3ddf4ce3a0df48a7"]], "script": ["__API_ERROR__"]},
  "tricky::api_error_var": {"answer": "{\"hypothesis\": \"BMI \\\"grows\\\" 5% with age\\nstrongly\", \"workflow\": \"OLS {fit}\"}", "outcome": {"error": "RuntimeError"}, "requests": [["a72157819fb04f58", "3ddf4ce3a0df48a7"], ["a72157819fb04f58", "47a9607e9ce9a796"], ["a72157819fb04f58", "d975a021407acfab"], ["deb934ce6386ddab", "8f7694ef1b5d36b3"]], "script": ["{\"context\": \"adults in rural areas\"}", "{\"context\": \"adults in rural areas\"}", "{\"match\": true, \"reason\": \"same\"}", "__API_ERROR__"]},
  "tricky::context_mismatch": {"answer": "{\"hypothesis\": \"BMI \\\"grows\\\" 5% with age\\nstrongly\", \"workflow\": \"OLS {fit}\"}", "outcome": {"reward": 0.0}, "requests": [["a72157819fb04f58", "3ddf4ce3a0df48a7"], ["a72157819fb04f58", "47a9607e9ce9a796"], ["a72157819fb04f58", "d975a021407acfab"]], "script": ["{\"context\": \"adults in rural areas\"}", "{\"context\": \"adults in rural areas\"}", "{\"match\": false, \"reason\": \"diff\"}"]},
  "tricky::full_rel_A_fenced": {"answer": "{\"hypothesis\": \"BMI \\\"grows\\\" 5% with age\\nstrongly\", \"workflow\": \"OLS {fit}\"}", "outcome": {"reward": 0.8}, "requests": [["a72157819fb04f58", "3ddf4ce3a0df48a7"], ["a72157819fb04f58", "47a9607e9ce9a796"], ["a72157819fb04f58", "d975a021407acfab"], ["deb934ce6386ddab", "8f7694ef1b5d36b3"], ["deb934ce6386ddab", "a7b3fd1c957ff54f"]], "script": ["{\"context\": \"adults in rural areas\"}", "```json\n{\"context\": \"adults in rural areas\"}\n```", "{\"match\": true, \"reason\": \"same\"}", "```json\n{\"sizeA\": 3, \"sizeB\": 2, \"intersection\": 2, \"explanation\": \"e\"}\n```", "Sure:\n{\"answer\": \"A) very similar\", \"explanation\": \"e\"}"]},
  "tricky::full_rel_B": {"answer": "{\"hypothesis\": \"BMI \\\"grows\\\" 5% with age\\nstrongly\", \"workflow\": \"OLS {fit}\"}", "outcome": {"reward": 0.4}, "requests": [["a72157819fb04f58", "3ddf4ce3a0df48a7"], ["a72157819fb04f58", "47a9607e9ce9a796"], ["a72157819fb04f58", "d975a021407acfab"], ["deb934ce6386ddab", "8f7694ef1b5d36b3"], ["deb934ce6386ddab", "a7b3fd1c957ff54f"]], "script": ["{\"context\": \"adults in rural areas\"}", "{\"context\": \"adults in rural areas\"}", "{\"match\": true, \"reason\": \"same\"}", "{\"sizeA\": 3, \"sizeB\": 2, \"intersection\": 2, \"explanation\": \"e\"}", "{\"answer\": \"B) similar but general than HypoA\", \"explanation\": \"e\"}"]},
  "tricky::gen_ctx_list_raises": {"answer": "{\"hypothesis\": \"BMI \\\"grows\\\" 5% with age\\nstrongly\", \"workflow\": \"OLS {fit}\"}", "outcome": {"error": "AttributeError"}, "requests": [["a72157819fb04f58", "3ddf4ce3a0df48a7"], ["a72157819fb04f58", "47a9607e9ce9a796"]], "script": ["{\"context\": \"adults in rural areas\"}", "[1, 2]"]},
  "tricky::gold_ctx_unparseable": {"answer": "{\"hypothesis\": \"BMI \\\"grows\\\" 5% with age\\nstrongly\", \"workflow\": \"OLS {fit}\"}", "outcome": {"reward": 0.8}, "requests": [["a72157819fb04f58", "3ddf4ce3a0df48a7"], ["a72157819fb04f58", "47a9607e9ce9a796"], ["a72157819fb04f58", "89fd8dcf3de3917d"], ["deb934ce6386ddab", "8f7694ef1b5d36b3"], ["deb934ce6386ddab", "a7b3fd1c957ff54f"]], "script": ["not json", "{\"context\": \"adults in rural areas\"}", "{\"match\": true, \"reason\": \"same\"}", "{\"sizeA\": 3, \"sizeB\": 2, \"intersection\": 2, \"explanation\": \"e\"}", "{\"answer\": \"A) very similar\", \"explanation\": \"e\"}"]},
  "tricky::match_missing_key": {"answer": "{\"hypothesis\": \"BMI \\\"grows\\\" 5% with age\\nstrongly\", \"workflow\": \"OLS {fit}\"}", "outcome": {"reward": 0.0}, "requests": [["a72157819fb04f58", "3ddf4ce3a0df48a7"], ["a72157819fb04f58", "47a9607e9ce9a796"], ["a72157819fb04f58", "d975a021407acfab"]], "script": ["{\"context\": \"adults in rural areas\"}", "{\"context\": \"adults in rural areas\"}", "{\"reason\": \"x\"}"]},
  "tricky::match_string_false_is_truthy": {"answer": "{\"hypothesis\": \"BMI \\\"grows\\\" 5% with age\\nstrongly\", \"workflow\": \"OLS {fit}\"}", "outcome": {"reward": 0.8}, "requests": [["a72157819fb04f58", "3ddf4ce3a0df48a7"], ["a72157819fb04f58", "47a9607e9ce9a796"], ["a72157819fb04f58", "d975a021407acfab"], ["deb934ce6386ddab", "8f7694ef1b5d36b3"], ["deb934ce6386ddab", "a7b3fd1c957ff54f"]], "script": ["{\"context\": \"adults in rural areas\"}", "{\"context\": \"adults in rural areas\"}", "{\"match\": \"false\"}", "{\"sizeA\": 3, \"sizeB\": 2, \"intersection\": 2, \"explanation\": \"e\"}", "{\"answer\": \"A) very similar\", \"explanation\": \"e\"}"]},
  "tricky::match_unparseable_4x_then_ok": {"answer": "{\"hypothesis\": \"BMI \\\"grows\\\" 5% with age\\nstrongly\", \"workflow\": \"OLS {fit}\"}", "outcome": {"reward": 0.8}, "requests": [["a72157819fb04f58", "3ddf4ce3a0df48a7"], ["a72157819fb04f58", "47a9607e9ce9a796"], ["a72157819fb04f58", "d975a021407acfab"], ["a72157819fb04f58", "d975a021407acfab"], ["a72157819fb04f58", "d975a021407acfab"], ["a72157819fb04f58", "d975a021407acfab"], ["a72157819fb04f58", "d975a021407acfab"], ["deb934ce6386ddab", "8f7694ef1b5d36b3"], ["deb934ce6386ddab", "a7b3fd1c957ff54f"]], "script": ["{\"context\": \"adults in rural areas\"}", "{\"context\": \"adults in rural areas\"}", "nope", "nope", "nope", "nope", "{\"match\": true, \"reason\": \"same\"}", "{\"sizeA\": 3, \"sizeB\": 2, \"intersection\": 2, \"explanation\": \"e\"}", "{\"answer\": \"A) very similar\", \"explanation\": \"e\"}"]},
  "tricky::match_unparseable_5x_raises": {"answer": "{\"hypothesis\": \"BMI \\\"grows\\\" 5% with age\\nstrongly\", \"workflow\": \"OLS {fit}\"}", "outcome": {"error": "AttributeError"}, "requests": [["a72157819fb04f58", "3ddf4ce3a0df48a7"], ["a72157819fb04f58", "47a9607e9ce9a796"], ["a72157819fb04f58", "d975a021407acfab"], ["a72157819fb04f58", "d975a021407acfab"], ["a72157819fb04f58", "d975a021407acfab"], ["a72157819fb04f58", "d975a021407acfab"], ["a72157819fb04f58", "d975a021407acfab"]], "script": ["{\"context\": \"adults in rural areas\"}", "{\"context\": \"adults in rural areas\"}", "nope", "nope", "nope", "nope", "nope"]},
  "tricky::rel_C": {"answer": "{\"hypothesis\": \"BMI \\\"grows\\\" 5% with age\\nstrongly\", \"workflow\": \"OLS {fit}\"}", "outcome": {"reward": 0.0}, "requests": [["a72157819fb04f58", "3ddf4ce3a0df48a7"], ["a72157819fb04f58", "47a9607e9ce9a796"], ["a72157819fb04f58", "d975a021407acfab"], ["deb934ce6386ddab", "8f7694ef1b5d36b3"], ["deb934ce6386ddab", "a7b3fd1c957ff54f"]], "script": ["{\"context\": \"adults in rural areas\"}", "{\"context\": \"adults in rural areas\"}", "{\"match\": true, \"reason\": \"same\"}", "{\"sizeA\": 3, \"sizeB\": 2, \"intersection\": 2, \"explanation\": \"e\"}", "{\"answer\": \"C) different\"}"]},
  "tricky::rel_answer_not_str": {"answer": "{\"hypothesis\": \"BMI \\\"grows\\\" 5% with age\\nstrongly\", \"workflow\": \"OLS {fit}\"}", "outcome": {"reward": 0.0}, "requests": [["a72157819fb04f58", "3ddf4ce3a0df48a7"], ["a72157819fb04f58", "47a9607e9ce9a796"], ["a72157819fb04f58", "d975a021407acfab"], ["deb934ce6386ddab", "8f7694ef1b5d36b3"], ["deb934ce6386ddab", "a7b3fd1c957ff54f"]], "script": ["{\"context\": \"adults in rural areas\"}", "{\"context\": \"adults in rural areas\"}", "{\"match\": true, \"reason\": \"same\"}", "{\"sizeA\": 3, \"sizeB\": 2, \"intersection\": 2, \"explanation\": \"e\"}", "{\"answer\": 1}"]},
  "tricky::rel_other": {"answer": "{\"hypothesis\": \"BMI \\\"grows\\\" 5% with age\\nstrongly\", \"workflow\": \"OLS {fit}\"}", "outcome": {"reward": 0.0}, "requests": [["a72157819fb04f58", "3ddf4ce3a0df48a7"], ["a72157819fb04f58", "47a9607e9ce9a796"], ["a72157819fb04f58", "d975a021407acfab"], ["deb934ce6386ddab", "8f7694ef1b5d36b3"], ["deb934ce6386ddab", "a7b3fd1c957ff54f"]], "script": ["{\"context\": \"adults in rural areas\"}", "{\"context\": \"adults in rural areas\"}", "{\"match\": true, \"reason\": \"same\"}", "{\"sizeA\": 3, \"sizeB\": 2, \"intersection\": 2, \"explanation\": \"e\"}", "{\"answer\": \"maybe\"}"]},
  "tricky::rel_unparseable": {"answer": "{\"hypothesis\": \"BMI \\\"grows\\\" 5% with age\\nstrongly\", \"workflow\": \"OLS {fit}\"}", "outcome": {"reward": 0.0}, "requests": [["a72157819fb04f58", "3ddf4ce3a0df48a7"], ["a72157819fb04f58", "47a9607e9ce9a796"], ["a72157819fb04f58", "d975a021407acfab"], ["deb934ce6386ddab", "8f7694ef1b5d36b3"], ["deb934ce6386ddab", "a7b3fd1c957ff54f"]], "script": ["{\"context\": \"adults in rural areas\"}", "{\"context\": \"adults in rural areas\"}", "{\"match\": true, \"reason\": \"same\"}", "{\"sizeA\": 3, \"sizeB\": 2, \"intersection\": 2, \"explanation\": \"e\"}", "no"]},
  "tricky::var_missing_explanation": {"answer": "{\"hypothesis\": \"BMI \\\"grows\\\" 5% with age\\nstrongly\", \"workflow\": \"OLS {fit}\"}", "outcome": {"reward": 0.0}, "requests": [["a72157819fb04f58", "3ddf4ce3a0df48a7"], ["a72157819fb04f58", "47a9607e9ce9a796"], ["a72157819fb04f58", "d975a021407acfab"], ["deb934ce6386ddab", "8f7694ef1b5d36b3"], ["deb934ce6386ddab", "a7b3fd1c957ff54f"]], "script": ["{\"context\": \"adults in rural areas\"}", "{\"context\": \"adults in rural areas\"}", "{\"match\": true, \"reason\": \"same\"}", "{\"sizeA\": 2, \"sizeB\": 2, \"intersection\": 2}", "{\"answer\": \"A) very similar\", \"explanation\": \"e\"}"]},
  "tricky::var_sizeB_zero": {"answer": "{\"hypothesis\": \"BMI \\\"grows\\\" 5% with age\\nstrongly\", \"workflow\": \"OLS {fit}\"}", "outcome": {"reward": 0.0}, "requests": [["a72157819fb04f58", "3ddf4ce3a0df48a7"], ["a72157819fb04f58", "47a9607e9ce9a796"], ["a72157819fb04f58", "d975a021407acfab"], ["deb934ce6386ddab", "8f7694ef1b5d36b3"], ["deb934ce6386ddab", "a7b3fd1c957ff54f"]], "script": ["{\"context\": \"adults in rural areas\"}", "{\"context\": \"adults in rural areas\"}", "{\"match\": true, \"reason\": \"same\"}", "{\"sizeA\": 2, \"sizeB\": 0, \"intersection\": 1, \"explanation\": \"\"}", "{\"answer\": \"A) very similar\", \"explanation\": \"e\"}"]},
  "tricky::var_string_count": {"answer": "{\"hypothesis\": \"BMI \\\"grows\\\" 5% with age\\nstrongly\", \"workflow\": \"OLS {fit}\"}", "outcome": {"reward": 0.0}, "requests": [["a72157819fb04f58", "3ddf4ce3a0df48a7"], ["a72157819fb04f58", "47a9607e9ce9a796"], ["a72157819fb04f58", "d975a021407acfab"], ["deb934ce6386ddab", "8f7694ef1b5d36b3"], ["deb934ce6386ddab", "a7b3fd1c957ff54f"]], "script": ["{\"context\": \"adults in rural areas\"}", "{\"context\": \"adults in rural areas\"}", "{\"match\": true, \"reason\": \"same\"}", "{\"sizeA\": \"2\", \"sizeB\": \"2\", \"intersection\": 1, \"explanation\": \"\"}", "{\"answer\": \"A) very similar\", \"explanation\": \"e\"}"]},
  "tricky::var_unparseable": {"answer": "{\"hypothesis\": \"BMI \\\"grows\\\" 5% with age\\nstrongly\", \"workflow\": \"OLS {fit}\"}", "outcome": {"reward": 0.0}, "requests": [["a72157819fb04f58", "3ddf4ce3a0df48a7"], ["a72157819fb04f58", "47a9607e9ce9a796"], ["a72157819fb04f58", "d975a021407acfab"], ["deb934ce6386ddab", "8f7694ef1b5d36b3"], ["deb934ce6386ddab", "a7b3fd1c957ff54f"]], "script": ["{\"context\": \"adults in rural areas\"}", "{\"context\": \"adults in rural areas\"}", "{\"match\": true, \"reason\": \"same\"}", "no", "{\"answer\": \"A) very similar\", \"explanation\": \"e\"}"]}
 }
}
''')
# fmt: on


class APIConnectionError(Exception):
    pass


def _sha16(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


class _Judge:
    """Stub `litellm` module: replays scripted replies, records requests."""

    def __init__(self, script: list[str]) -> None:
        self.script = list(script)
        self.calls: list[dict] = []
        self.module = types.ModuleType("litellm")
        self.module.completion = self.completion
        self.module.APIConnectionError = APIConnectionError

    def completion(self, **kwargs):
        self.calls.append(kwargs)
        reply = self.script.pop(0)
        if reply == API_ERROR:
            raise APIConnectionError("judge outage")
        message = types.SimpleNamespace(content=reply)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])


def _load_scorer(tmp_path: Path, monkeypatch, judge: _Judge):
    monkeypatch.setitem(sys.modules, "litellm", judge.module)
    path = tmp_path / "run_scorer.py"
    path.write_text(db._render_run_scorer(), encoding="utf-8")
    spec = importlib.util.spec_from_file_location("db_run_scorer", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.ANSWER_FILE = tmp_path / "answer.txt"
    mod.CONFIG_FILE = tmp_path / "config.json"
    mod.REWARD_FILE = tmp_path / "logs" / "reward.txt"
    return mod


def _config(inp: dict, marker: str = "asta-bench-oracle/test-marker") -> dict:
    return {
        "family": "discoverybench",
        "gold_hypothesis": inp["gold_hypothesis"],
        "gold_workflow": inp["gold_workflow"],
        "dataset_meta": inp["dataset_meta"],
        "query": inp["query"],
        "oracle_marker": marker,
    }


def _run(tmp_path, monkeypatch, cfg, answer, script):
    judge = _Judge(script)
    mod = _load_scorer(tmp_path, monkeypatch, judge)
    mod.CONFIG_FILE.write_text(json.dumps(cfg))
    if answer is not None:
        mod.ANSWER_FILE.write_text(answer, encoding="utf-8")
    return mod, judge


def _reward(mod) -> float | None:
    if not mod.REWARD_FILE.exists():
        return None
    return float(mod.REWARD_FILE.read_text())


# --- equivalence with the real upstream scorer --------------------------------


@pytest.mark.parametrize("case_id", sorted(FIXTURES["cases"]))
def test_scorer_matches_upstream(case_id: str, tmp_path: Path, monkeypatch) -> None:
    case = FIXTURES["cases"][case_id]
    inp = FIXTURES["inputs"][case_id.split("::")[0]]
    mod, judge = _run(
        tmp_path, monkeypatch, _config(inp), case["answer"], case["script"]
    )

    if "error" in case["outcome"]:
        # Upstream raises -> Inspect sample error; Harbor: no reward, non-zero.
        expected = (
            APIConnectionError
            if API_ERROR in case["script"]
            else getattr(builtins, case["outcome"]["error"])
        )
        with pytest.raises(expected):
            mod.main()
        assert _reward(mod) is None
    else:
        assert mod.main() == 0
        assert _reward(mod) == pytest.approx(case["outcome"]["reward"], abs=0, rel=0)

    assert judge.script == []  # same number of judge calls as upstream
    got = [[_sha16(m["content"]) for m in c["messages"]] for c in judge.calls]
    assert got == case["requests"]
    for call in judge.calls:
        assert [m["role"] for m in call["messages"]] == ["system", "user"]
        assert call["model"] == MODEL
        assert call["temperature"] == 0
        assert call["max_tokens"] == 250
        assert "top_p" not in call and "response_format" not in call
        # Transport retries are bounded (then the error propagates).
        assert 0 <= call["num_retries"] <= 5


def test_fixture_covers_failure_modes() -> None:
    outcomes = {k.split("::")[1]: v["outcome"] for k, v in FIXTURES["cases"].items()}
    assert outcomes["match_unparseable_5x_raises"] == {"error": "AttributeError"}
    assert outcomes["gen_ctx_list_raises"] == {"error": "AttributeError"}
    assert outcomes["gold_ctx_unparseable"] == {"reward": 0.8}
    assert outcomes["var_unparseable"] == {"reward": 0.0}
    assert outcomes["rel_unparseable"] == {"reward": 0.0}
    assert outcomes["answer_missing_workflow"] == {"reward": 0.0}


# --- oracle --------------------------------------------------------------------

CTX = '{"context": "c"}'
MATCH_F = '{"match": false}'


def test_oracle_marker_short_circuits_without_judge(tmp_path, monkeypatch) -> None:
    inp = FIXTURES["inputs"]["plain"]
    answer = json.dumps(
        {
            "_oracle_marker": "asta-bench-oracle/test-marker",
            "hypothesis": "h",
            "workflow": "w",
        }
    )
    mod, judge = _run(tmp_path, monkeypatch, _config(inp), answer, [])
    assert mod.main() == 0
    assert _reward(mod) == 1.0
    assert judge.calls == []


@pytest.mark.parametrize("marker", ["asta-bench-oracle/wrong", None, ""])
def test_wrong_marker_is_judged(tmp_path, monkeypatch, marker) -> None:
    inp = FIXTURES["inputs"]["plain"]
    answer = json.dumps({"_oracle_marker": marker, "hypothesis": "h", "workflow": "w"})
    mod, judge = _run(tmp_path, monkeypatch, _config(inp), answer, [CTX, CTX, MATCH_F])
    assert mod.main() == 0
    assert _reward(mod) == 0.0
    assert len(judge.calls) == 3


def test_gold_text_is_judged_not_short_circuited(tmp_path, monkeypatch) -> None:
    inp = FIXTURES["inputs"]["plain"]
    answer = json.dumps(
        {"hypothesis": inp["gold_hypothesis"], "workflow": inp["gold_workflow"]}
    )
    mod, judge = _run(tmp_path, monkeypatch, _config(inp), answer, [CTX, CTX, MATCH_F])
    assert mod.main() == 0
    assert _reward(mod) == 0.0
    assert len(judge.calls) == 3


def test_missing_answer_scores_zero(tmp_path, monkeypatch) -> None:
    inp = FIXTURES["inputs"]["plain"]
    mod, judge = _run(tmp_path, monkeypatch, _config(inp), None, [])
    assert mod.main() == 0
    assert _reward(mod) == 0.0
    assert judge.calls == []


def test_config_without_marker_is_verifier_error(tmp_path, monkeypatch) -> None:
    cfg = _config(FIXTURES["inputs"]["plain"])
    del cfg["oracle_marker"]
    mod, _ = _run(
        tmp_path, monkeypatch, cfg, '{"hypothesis": "h", "workflow": "w"}', []
    )
    with pytest.raises(KeyError):
        mod.main()
    assert _reward(mod) is None


# --- generation ----------------------------------------------------------------


def test_instruction_body_is_upstream_sample_input() -> None:
    fq = FIXTURES["format_query"]
    assert (
        hashlib.sha256(db._format_query(fq["input"]).encode("utf-8")).hexdigest()
        == fq["sample_input_sha256"]
    )


def _record(sample_id: str = "s-1") -> SampleRecord:
    inp = FIXTURES["inputs"]["plain"]
    block = {
        "data_folder": "wb",
        "query": inp["query"],
        "metadata": inp["dataset_meta"],
    }
    return SampleRecord(
        sample_id=sample_id,
        split="test",
        instruction=db._format_query(block),
        target=(inp["gold_hypothesis"], inp["gold_workflow"]),
        metadata={"query": inp["query"], "dataset_meta": inp["dataset_meta"]},
        workspace_files={"wb/wb.csv": b"spend,gdp\n1,2\n"},
    )


def test_write_task(tmp_path: Path) -> None:
    builder = db.DiscoveryBenchBuilder.__new__(db.DiscoveryBenchBuilder)
    builder.inspect_pip_install = lambda: None
    builder.task_id = lambda r: f"discoverybench-{r.split}-{r.sample_id}"
    markers = []
    for i in range(2):
        task_dir = tmp_path / f"t{i}"
        builder.write_task(_record(), task_dir)
        toml = (task_dir / "task.toml").read_text()
        assert re.search(r"^allow_internet = true$", toml, re.MULTILINE)
        assert "JUDGE_MODEL" not in toml
        instruction = (task_dir / "instruction.md").read_text()
        assert "discoverybench" not in instruction.lower()
        assert instruction.startswith(_record().instruction + "\n\n# Data location")
        cfg = json.loads((task_dir / "tests" / "config.json").read_text())
        marker = cfg["oracle_marker"]
        solve = (task_dir / "solution" / "solve.sh").read_text()
        assert json.dumps(marker) in solve
        assert marker not in instruction
        assert (
            not (task_dir / "environment" / "workspace")
            .joinpath("config.json")
            .exists()
        )
        markers.append(marker)
        dockerfile = (task_dir / "environment" / "Dockerfile").read_text()
        assert '"litellm==' in dockerfile
    assert markers[0] != markers[1]


def test_csv_fetch_failure_raises(tmp_path: Path, monkeypatch) -> None:
    meta = tmp_path / "meta.json"
    inp = FIXTURES["inputs"]["plain"]
    meta.write_text(
        json.dumps(
            [
                {
                    "id": "x-0",
                    "input": {
                        "data_folder": "wb",
                        "query": inp["query"],
                        "metadata": inp["dataset_meta"],
                    },
                    "gold_output": {"hypothesis": "h", "workflow": "w"},
                }
            ]
        )
    )

    def fake_download(repo_id, filename, **kwargs):
        if repo_id == "allenai/asta-bench":
            return str(meta)
        raise OSError("offline")

    hub = types.ModuleType("huggingface_hub")
    hub.hf_hub_download = fake_download
    monkeypatch.setitem(sys.modules, "huggingface_hub", hub)
    builder = db.DiscoveryBenchBuilder.__new__(db.DiscoveryBenchBuilder)
    with pytest.raises(RuntimeError, match="failed to fetch"):
        list(builder.load_samples("test"))
