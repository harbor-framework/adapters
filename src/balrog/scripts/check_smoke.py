"""Check real Harbor oracle/nop jobs against the frozen native BabyAI fixture."""

import argparse
import json
from pathlib import Path


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check_job(path, agent, expected_score, fixture):
    job = read_json(path / "result.json")
    require(bool(job.get("finished_at")), f"{agent}: job has not finished")
    require(job["stats"]["n_completed_trials"] == 1, f"{agent}: expected one completed trial")
    require(job["stats"]["n_errored_trials"] == 0, f"{agent}: Harbor reported an error")
    trials = list(path.glob("*/result.json"))
    require(len(trials) == 1, f"{agent}: expected one trial result")
    trial = read_json(trials[0])
    require(trial.get("exception_info") is None, f"{agent}: trial exception")
    require(trial["agent_info"]["name"] == agent, f"{agent}: unexpected agent")
    require(trial["verifier_result"]["rewards"] == {"reward": expected_score}, f"{agent}: Harbor score mismatch")
    verifier = trials[0].parent / "verifier"
    require(float((verifier / "reward.txt").read_text()) == expected_score, f"{agent}: reward.txt mismatch")
    result = read_json(verifier / "result.json")
    require(result["replay_verified"] is True and result["finalized"] is True, f"{agent}: replay was not verified")
    require(result["progression"] == result["replay_progression"] == expected_score, f"{agent}: native progression mismatch")
    require(result["initial_observation_sha256"] == fixture["expected_initial_observation_sha256"], f"{agent}: native initial state mismatch")
    if agent == "oracle":
        expected = fixture["expected_transitions"]
        actual = result["transitions"]
        require(result["steps"] == len(actual) == len(expected), "oracle: transition count mismatch")
        require(result["terminated"] is True and result["truncated"] is False, "oracle: did not finish successfully")
        for index, (native, adapted) in enumerate(zip(expected, actual)):
            require(adapted["raw_action"] == fixture["actions"][index], f"oracle: wrong action at {index}")
            for key, value in native.items():
                target = "observation_sha256" if key == "observation" else key
                require(adapted[target] == value, f"oracle: native {key} mismatch at {index}")
    else:
        require(result["steps"] == 0 and result["transitions"] == [], "nop: unexpected actions")
        require(result["terminated"] is False and result["truncated"] is False, "nop: unexpected termination")
    return {
        "agent": agent,
        "reward": expected_score,
        "steps": result["steps"],
        "replay_verified": True,
        "native_fixture_matched": True,
        "exceptions": 0,
        "job_result": str((path / "result.json").resolve()),
        "verifier_result": str((verifier / "result.json").resolve()),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--oracle-job", type=Path, required=True)
    parser.add_argument("--nop-job", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    fixture = read_json(Path(__file__).resolve().parents[1] / "src/balrog/fixtures/oracle_actions.json")
    try:
        results = [
            check_job(args.oracle_job, "oracle", fixture["expected_progression"], fixture),
            check_job(args.nop_job, "nop", 0.0, fixture),
        ]
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(1, f"Smoke verification FAILED: {exc}\n")
    report = json.dumps({"status": "passed", "checks": results}, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report + "\n", encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
