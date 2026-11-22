"""Assert infra/simulator failures are unscored under native and isolated Harbor."""
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--validation", type=Path, default=Path("validation"))
args = parser.parse_args()
rows = []
for native_name, harbor_name, forged in (("native-user-protocol", "offline-user-protocol", True),
                                         ("native-provider-error", "offline-provider-error", True),
                                         ("native-agent-provider", "relay-provider-final", False)):
    native = json.loads((args.validation / native_name / "case_031__trial0/result.json").read_text("utf-8"))
    job = args.validation / "harbor" / harbor_name
    paths = list(job.glob("*/artifacts/private/runs/evidence.json"))
    assert len(paths) == 1, paths
    evidence = json.loads(paths[0].read_text("utf-8"))
    trial = paths[0].parents[3]
    harbor = evidence["result"]
    assert native["classification"] == harbor["classification"]
    assert native["reward"] is None and harbor["reward"] is None
    assert native["verification"] == harbor["verification"]
    assert not (trial / "verifier/reward.txt").exists()
    assert not (trial / "verifier/reward.json").exists()
    error = json.loads((trial / "verifier/error.json").read_text("utf-8"))
    assert harbor["classification"] in error["error"]
    trial_result = json.loads((trial / "result.json").read_text("utf-8"))
    assert trial_result.get("verifier_result") is None
    assert trial_result["exception_info"]["exception_type"] == "RewardFileNotFoundError"
    rows.append({"scenario": native_name, "classification": harbor["classification"], "native_reward": None,
                 "harbor_reward": None, "full_verdict_equal": True,
                 "forged_rewards_removed": forged, "verifier_error": error})
(args.validation / "error-equivalence.json").write_text(json.dumps(rows, indent=2) + "\n", "utf-8")
print(f"Preserved {len(rows)} unscored native error scenarios; no numeric rewards")
