"""Generated-task trust-boundary assertions shared by generator tests."""

import json
from pathlib import PurePosixPath
import re
import tomllib


def assert_separate_verifier_contract(test, destination, episode):
    config = tomllib.loads((destination / "task.toml").read_text(encoding="utf-8"))
    verifier = config["verifier"]
    test.assertEqual(verifier["environment_mode"], "separate")
    test.assertIn("environment", verifier)
    test.assertNotIn("healthcheck", verifier["environment"])
    test.assertNotIn("RESULT_TOKEN", verifier.get("env", {}))
    test.assertNotIn("BALROG_SERVER", verifier.get("env", {}))
    result_path = verifier.get("env", {}).get("BALROG_RESULT_PATH", "/var/lib/balrog/result.json")
    test.assertTrue(PurePosixPath(result_path).is_absolute())
    test.assertNotEqual(result_path, "/logs/artifacts")
    test.assertFalse(result_path.startswith("/logs/artifacts/"))
    matching = [item for item in config["artifacts"] if item["source"] == result_path]
    test.assertEqual(len(matching), 1, "Result must have one unambiguous trusted source")
    test.assertEqual(matching[0]["service"], "game")
    collect = verifier["collect"]
    test.assertTrue(any(item.get("service") == "game" and
                        "/app/export_result.py" in item["command"] for item in collect))
    for relative in ("environment/export_result.py", "tests/Dockerfile", "tests/test.sh",
                     "tests/verifier.py", "tests/task_config.json"):
        test.assertTrue((destination / relative).is_file(), relative)
    expected = json.loads((destination / "tests/task_config.json").read_text(encoding="utf-8"))
    test.assertEqual(expected, episode)
    dockerfile = (destination / "tests/Dockerfile").read_text(encoding="utf-8")
    test.assertRegex(dockerfile, r"(?m)^COPY\s+\.\s+/tests/?\s*$")
    test.assertNotIn("requirements-agent", dockerfile)
    game_dockerfile = (destination / "environment/Dockerfile.game").read_text(encoding="utf-8")
    test.assertIn("export_result.py", game_dockerfile)
    test.assertIn("/var/lib/balrog", game_dockerfile)
    compose = (destination / "environment/docker-compose.yaml").read_text(encoding="utf-8")
    token = re.search(r'RESULT_TOKEN:\s*"([0-9a-f]{64})"', compose)
    test.assertIsNotNone(token, "Only the game service receives the generated result token")
    test.assertNotIn(token.group(1), (destination / "task.toml").read_text(encoding="utf-8"))
    test.assertNotIn(token.group(1), (destination / "tests/task_config.json").read_text(encoding="utf-8"))
    return token.group(1)
