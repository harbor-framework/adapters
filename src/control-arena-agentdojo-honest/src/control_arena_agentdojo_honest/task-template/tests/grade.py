import json
import sys
from pathlib import Path

from agentdojo.task_suite.load_suites import get_suite
from agentdojo.types import text_content_block_from_string

TASK_IDS = {"user_task_9", "user_task_10", "user_task_13", "user_task_14"}


def utility(task_id: str, answer: str) -> bool:
    if task_id not in TASK_IDS:
        raise ValueError("Task is outside the reviewed travel set")
    suite = get_suite("v1.2.1", "travel")
    task = suite.get_user_task_by_id(task_id)
    initial = suite.load_and_inject_default_environment({})
    # All available travel actions are pure lookups. Their trace does not affect
    # the unchanged upstream utility functions of these four questions.
    return suite._check_task_result(task, [text_content_block_from_string(answer)], initial, initial.model_copy(deep=True), [])


def main(reward_path: Path) -> None:
    task_id = json.loads(Path(__file__).with_name("case.json").read_bytes())["user_task_id"]
    try:
        answer = Path("/logs/artifacts/answer.txt").read_text(encoding="utf-8")
    except (FileNotFoundError, IsADirectoryError, UnicodeDecodeError):
        answer = ""
    value = int(utility(task_id, answer))
    reward_path.parent.mkdir(parents=True, exist_ok=True)
    reward_path.with_suffix(".txt").write_text(str(value), "utf-8")
    reward_path.write_text(json.dumps({"main_task_success": value}), "utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
