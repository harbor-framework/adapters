"""Validate one complete Harbor honest-oracle pass without printing evaluation material."""

import argparse
import hashlib
import json
import sys
from pathlib import Path
from zipfile import ZipFile

from control_arena import EvalMode
from control_arena.settings.sae_interp_sabotage.setting import SAEInterpSetting

from control_arena_sae_interp.analysis import load_trials

if sys.version_info < (3, 14):
    import zipfile_zstd  # noqa: F401 - enables reading Inspect's compressed .eval headers


def check(jobs: list[Path], judge: str) -> dict:
    samples = SAEInterpSetting().get_dataset(EvalMode.HONEST)
    expected = {index: hashlib.sha256(sample.input.encode("utf-8")).hexdigest()
                for index, sample in enumerate(samples)}
    verdicts = {}
    for job in jobs:
        for path in load_trials(job):
            trial = json.loads(path.read_bytes())
            verifier = path.parent / "verifier"
            source = json.loads((verifier / "provenance.json").read_bytes())
            index = source["source_index"]
            digest = expected.get(index)
            if (index in verdicts or not digest or source["prompt_sha256"] != digest
                    or trial["task_name"] != f"control-arena/sae-interp-{digest[:12]}"):
                raise ValueError(f"Duplicate or mismatched sample in {path.parent.name}")
            if (not trial.get("finished_at") or trial.get("exception_info") or trial["agent_info"]["name"] != "oracle"
                    or source["eval_mode"] != "honest" or source["setting"] != "sae_interp_sabotage"
                    or source["judge_model"] != judge or source["valid_submission"] is not True
                    or source["control_arena_version"] != "20.1.1" or source["inspect_ai_version"] != "0.3.292"):
                raise ValueError(f"Unexpected trial configuration or outcome for source row {index}")
            (log_path,) = (verifier / "inspect").glob("*.eval")
            with ZipFile(log_path) as archive:
                header = json.loads(archive.read("header.json"))
            usage = header["stats"]["model_usage"].get(judge, {})
            if (header["status"] != "success" or header["eval"]["model"] != judge
                    or usage.get("input_tokens", 0) <= 0 or usage.get("output_tokens", 0) <= 0):
                raise ValueError(f"Missing completed judge call for source row {index}")
            reward = json.loads((verifier / "reward.json").read_bytes())
            if reward not in ({"main_task_success": 0}, {"main_task_success": 1}) or trial["verifier_result"]["rewards"] != reward:
                raise ValueError(f"Invalid or conflicting reward for source row {index}")
            verdicts[index] = int(reward["main_task_success"])
    if missing := expected.keys() - verdicts.keys():
        raise ValueError(f"Missing upstream rows: {sorted(missing)}")
    return {"judge": judge, "cases": len(verdicts), "accepted": sum(verdicts.values()),
            "rejected_source_rows": sorted(row for row, value in verdicts.items() if not value)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("jobs", nargs="+", type=Path)
    parser.add_argument("--judge", default="openai/gpt-4.1-mini-2025-04-14")
    args = parser.parse_args()
    print(json.dumps(check(args.jobs, args.judge), indent=2))
