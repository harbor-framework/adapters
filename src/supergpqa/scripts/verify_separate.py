"""Validate separate verification and regrade saved parity replies; no model calls.

Original trials are read-only inputs. Derived source copies explicitly reconstruct
an answer artifact from the byte-identical saved API reply, with provenance.
"""

import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import shutil
from pathlib import Path

from harbor.agents.base import BaseAgent
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext
from harbor.models.trial.config import TrialConfig
from harbor.trial.trial import Trial

from supergpqa.adapter import SuperGPQAAdapter


def save(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SavedSubmissionAgent(BaseAgent):
    """Offline file handoff for negative controls, with no API client."""

    def __init__(self, *args, submission_path: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.submission_path = Path(submission_path)

    @staticmethod
    def name() -> str:
        return "supergpqa-saved-submission"

    def version(self) -> str:
        return "0.1.0"

    async def setup(self, environment: BaseEnvironment) -> None:
        return

    async def run(
        self, instruction: str, environment: BaseEnvironment, context: AgentContext
    ) -> None:
        await environment.upload_file(
            source_path=self.submission_path, target_path="/app/answer.txt"
        )


async def run_trial(task: Path, target: Path, **options) -> dict:
    result = target / "result.json"
    if not result.exists():
        config = TrialConfig.model_validate(
            {
                "task": {"path": str(task)},
                "trial_name": target.name,
                "trials_dir": str(target.parent),
                "environment": {"type": "docker", "force_build": False, "delete": True},
                **options,
            }
        )
        trial = await Trial.create(config)
        await trial.run()
    raw = json.loads(result.read_text())
    if raw.get("exception_info"):
        raise RuntimeError(f"Trial failed: {target}: {raw['exception_info']}")
    assert raw["verifier_environment_mode"] == "separate", target
    reward = raw["verifier_result"]["rewards"]["reward"]
    assert reward in (0, 1), target
    return {"trial": str(target), "reward": reward, "mode": "separate"}


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--controls-only", action="store_true")
    args = parser.parse_args()
    if args.concurrency < 1:
        parser.error("concurrency must be positive")
    source, output = args.experiment_dir.resolve(), args.output_dir.resolve()
    if source == output or source in output.parents or output in source.parents:
        parser.error("output must be separate from the original experiment")
    output.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((source / "manifest.json").read_text())
    ids = manifest["task_ids"]
    records = [
        json.loads(
            (source / "tasks" / ("supergpqa-" + uid) / "tests/record.json").read_text()
        )
        for uid in ids
    ]
    tasks = output / "tasks"
    if not tasks.exists():
        SuperGPQAAdapter(tasks, records).run()
    # Preserve identical instructions, records, and parser code during migration.
    for uid in ids:
        for name in [
            "instruction.md",
            "tests/record.json",
            "tests/grade.py",
            "tests/scoring.py",
            "tests/upstream_parser.py",
        ]:
            assert (source / "tasks" / ("supergpqa-" + uid) / name).read_bytes() == (
                tasks / ("supergpqa-" + uid) / name
            ).read_bytes(), (uid, name)
    uid = ids[0]
    task = tasks / ("supergpqa-" + uid)
    row = records[0]
    correct = await run_trial(
        task, output / "controls/oracle", agent={"name": "oracle"}
    )
    wrong_letter = next(
        chr(65 + i)
        for i in range(len(row["options"]))
        if chr(65 + i) != row["answer_letter"]
    )
    submission = output / "wrong-answer.txt"
    submission.write_text(f"Answer: {wrong_letter}\n")
    wrong = await run_trial(
        task,
        output / "controls/wrong",
        agent={
            "import_path": "verify_separate:SavedSubmissionAgent",
            "kwargs": {"submission_path": str(submission)},
        },
    )
    assert correct["reward"] == 1 and wrong["reward"] == 0
    controls = {
        "task_id": "supergpqa-" + uid,
        "task_name": "m-a-p/supergpqa-" + uid,
        "gold_letter": row["answer_letter"],
        "wrong_letter": wrong_letter,
        "oracle": correct,
        "wrong": wrong,
        "harbor": importlib.metadata.version("harbor"),
        "model_calls": 0,
    }
    save(output / "controls.json", controls)
    print("Same-task controls passed: oracle=1, valid incorrect option=0", flush=True)
    if args.controls_only:
        return
    results = []
    gate = asyncio.Semaphore(args.concurrency)

    async def regrade(index: int, uid: str) -> None:
        async with gate:
            original = source / f"run-{index}/harbor" / uid
            derived = output / f"derived-sources/run-{index}" / uid
            # Never fabricate an original collection event: only this derived copy
            # gets a reconstructed entry, with a separate provenance document.
            response = original / "agent/response.txt"
            api = json.loads((original / "agent/response.json").read_text())
            assert (
                response.read_bytes().decode("utf-8")
                == api["choices"][0]["message"]["content"]
            )
            tracked = {
                str(p.relative_to(original)): digest(p)
                for p in original.rglob("*")
                if p.is_file()
            }
            if not derived.exists():
                shutil.copytree(original, derived)
                answer = derived / "artifacts/app/answer.txt"
                answer.parent.mkdir(parents=True, exist_ok=True)
                answer.write_bytes(response.read_bytes())
                path = derived / "artifacts/manifest.json"
                entries = json.loads(path.read_text())
                assert not any(e["source"] == "/app/answer.txt" for e in entries)
                entries.append(
                    {
                        "source": "/app/answer.txt",
                        "destination": "artifacts/app/answer.txt",
                        "type": "file",
                        "status": "ok",
                        "service": None,
                        "exclude": [],
                    }
                )
                save(path, entries)
                save(
                    derived / "reconstruction-provenance.json",
                    {
                        "kind": "derived_regrade_source_not_original_collection",
                        "source_trial": str(original),
                        "response_source": str(response),
                        "response_sha256": digest(response),
                        "original_file_sha256": tracked,
                        "note": "Answer artifact reconstructed from saved API response; original manifest and source trial remain unchanged.",
                    },
                )
            provenance = json.loads(
                (derived / "reconstruction-provenance.json").read_text()
            )
            assert tracked == provenance["original_file_sha256"]
            assert digest(derived / "artifacts/app/answer.txt") == digest(response)
            result = await run_trial(
                tasks / ("supergpqa-" + uid),
                output / f"regraded/run-{index}" / uid,
                source_trial={
                    "action": "regrade",
                    "type": "local",
                    "path": str(derived),
                },
            )
            old = json.loads((original / "score.json").read_text())["reward"]
            assert result["reward"] == old, (index, uid, old, result)
            assert tracked == {
                str(p.relative_to(original)): digest(p)
                for p in original.rglob("*")
                if p.is_file()
            }, "Original trial changed"
            results.append(
                {
                    "run": index,
                    "uuid": uid,
                    "original_reward": old,
                    "new_reward": result["reward"],
                    "response_sha256": digest(response),
                }
            )
            save(
                output / "progress.json",
                {
                    "completed": len(results),
                    "total": len(ids) * 3,
                    "matches": len(results),
                    "model_calls": 0,
                },
            )
            print(
                f"Regraded {len(results)}/{len(ids) * 3}, all rewards unchanged",
                flush=True,
            )

    await asyncio.gather(*(regrade(i, uid) for i in range(1, 4) for uid in ids))
    save(
        output / "regrade-audit.json",
        {
            "harbor": importlib.metadata.version("harbor"),
            "controls": controls,
            "total": len(results),
            "matches": len(results),
            "model_calls": 0,
            "original_trials_unchanged": True,
            "run_correct": {
                str(i): sum(r["new_reward"] for r in results if r["run"] == i)
                for i in range(1, 4)
            },
            "results": sorted(results, key=lambda r: (r["run"], r["uuid"])),
        },
    )


if __name__ == "__main__":
    asyncio.run(main())
