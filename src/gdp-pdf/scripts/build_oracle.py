"""Build oracle answers for GDP.pdf tasks.

The dataset ships rubrics but no reference answers, so the oracle is written
with AI help: a writer model drafts an answer from the question, the document
text and the rubric, the task's own grader judges it, and failed points go back
to the writer with the judge's rationale. An answer is kept only after it
passes every point in `--confirm` further gradings in a row, since the judge
is not deterministic.

Writes <out-dir>/<upstream task_id>.md for each accepted answer and
<out-dir>/logs/<task_id>.json with every draft and grading. Pass the same
<out-dir> to `gdp-pdf --oracle-dir`. Tasks that already have an answer are
skipped, so the script can be stopped and rerun.

Environment:
  WRITER_API_KEY, WRITER_BASE_URL, WRITER_MODEL   the model that writes answers
  OPENAI_API_KEY, OPENAI_BASE_URL, JUDGE_MODEL    the judge, as in tests/test.sh

Usage: uv run python scripts/build_oracle.py --out-dir ../oracle [--task-ids hr-03 ...]
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import logging
import os
import subprocess
from pathlib import Path

from openai import AsyncOpenAI

from gdp_pdf.adapter import TEMPLATE_DIR, GdpPdfAdapter, GdpPdfTask

logger = logging.getLogger("build_oracle")

_spec = importlib.util.spec_from_file_location("grader", TEMPLATE_DIR / "tests" / "grader.py")
grader = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(grader)

# Enough for every document in the set except the longest reports.
MAX_DOCUMENT_CHARS = 120_000

WRITE_PROMPT = """You are writing the reference answer for an expert task. A grader will check the answer against each rubric point below, one point at a time, seeing only your answer: not the question, not the document. So every fact, number, name and conclusion a point asks for must be stated explicitly in the answer, in words the grader can match without the document.

Write the answer the way a careful professional would reply to the question: complete, correct according to the document, and well organised. Do not mention the rubric or the grader.

# Question
{prompt}

# Document text (extracted; may be incomplete for scanned pages)
{document}

# Rubric points
{rubric}

Reply with the answer only."""

REVISE_PROMPT = """The answer below failed some rubric points. For each failed point you have the grader's reasoning. Rewrite the answer so it meets every point, failed and passed alike. Keep what already works, and stay correct according to the document. Do not mention the rubric or the grader.

# Question
{prompt}

# Document text (extracted; may be incomplete for scanned pages)
{document}

# All rubric points
{rubric}

# Current answer
{answer}

# Failed points and the grader's reasoning
{failures}

Reply with the full revised answer only."""


def document_text(pdf: Path) -> str:
    try:
        text = subprocess.run(
            ["pdftotext", "-layout", "-q", str(pdf), "-"],
            capture_output=True,
            text=True,
            errors="replace",
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as e:
        raise RuntimeError(f"pdftotext failed on {pdf}") from e
    if not text:
        return "(This document has no text layer; rely on the question and the rubric.)"
    if len(text) > MAX_DOCUMENT_CHARS:
        return text[:MAX_DOCUMENT_CHARS] + "\n[... truncated ...]"
    return text


def rubric_list(task: GdpPdfTask) -> str:
    return "\n".join(f"- {r['criterion']}" for r in task.rubrics)


def failures_list(task: GdpPdfTask, grades: list[dict]) -> str:
    criteria = {r["id"]: r["criterion"] for r in task.rubrics}
    return "\n".join(
        f"- {criteria[g['rubric_id']]}\n  Grader: {g.get('rationale', 'could not be scored')}"
        for g in grades
        if g["result"] != "pass"
    )


async def write(client, model: str, prompt: str) -> str:
    result = await client.chat.completions.create(
        model=model, messages=[{"role": "user", "content": prompt}]
    )
    return (result.choices[0].message.content or "").strip()


async def build_one(
    task: GdpPdfTask,
    document: str,
    writer,
    writer_model: str,
    judge,
    judge_model: str,
    max_rounds: int,
    confirm: int,
) -> tuple[str | None, list[dict]]:
    """Return (accepted answer or None, log of every round)."""
    log = []
    values = {"prompt": task.prompt, "document": document, "rubric": rubric_list(task)}
    answer = await write(writer, writer_model, WRITE_PROMPT.format(**values))
    for round_no in range(1, max_rounds + 1):
        gradings = []
        for _ in range(1 + confirm):
            grades = (await grader.grade(judge, judge_model, answer, task.rubrics))["grades"]
            gradings.append(grades)
            if any(g["result"] != "pass" for g in grades):
                break
        log.append({"round": round_no, "answer": answer, "gradings": gradings})
        failed = next((g for g in gradings if any(x["result"] != "pass" for x in g)), None)
        if failed is None:
            return answer, log
        answer = await write(
            writer,
            writer_model,
            REVISE_PROMPT.format(**values, answer=answer, failures=failures_list(task, failed)),
        )
    return None, log


async def main_async(args) -> int:
    writer = AsyncOpenAI(
        api_key=os.environ["WRITER_API_KEY"], base_url=os.environ.get("WRITER_BASE_URL") or None
    )
    judge = AsyncOpenAI(
        api_key=os.environ["OPENAI_API_KEY"], base_url=os.environ.get("OPENAI_BASE_URL") or None
    )
    writer_model = os.environ["WRITER_MODEL"]
    judge_model = os.environ.get("JUDGE_MODEL", "gemini-3.5-flash")

    adapter = GdpPdfAdapter(args.out_dir, task_ids=args.task_ids)
    tasks = adapter.load_tasks()
    names = adapter.harbor_names(tasks)
    selected = [
        t
        for t in sorted(tasks, key=lambda t: names[t.task_id])
        if args.task_ids is None or names[t.task_id] in args.task_ids or t.task_id in args.task_ids
    ][: args.limit]

    (args.out_dir / "logs").mkdir(parents=True, exist_ok=True)
    gate = asyncio.Semaphore(args.concurrency)
    failed = []

    async def run(task: GdpPdfTask) -> None:
        out = args.out_dir / f"{task.task_id}.md"
        if out.exists():
            logger.info("%s: already built", names[task.task_id])
            return
        async with gate:
            document = document_text(adapter._download(task.pdf_path))
            answer, log = await build_one(
                task, document, writer, writer_model, judge, judge_model, args.max_rounds, args.confirm
            )
        (args.out_dir / "logs" / f"{task.task_id}.json").write_text(
            json.dumps({"name": names[task.task_id], "accepted": answer is not None, "rounds": log}, indent=2)
        )
        if answer is None:
            failed.append(names[task.task_id])
            logger.warning("%s: no passing answer after %d rounds", names[task.task_id], args.max_rounds)
            return
        out.write_text(answer + "\n")
        logger.info("%s: accepted after %d round(s)", names[task.task_id], len(log))

    await asyncio.gather(*(run(t) for t in selected))
    logger.info("Done: %d tasks, %d without a passing answer %s", len(selected), len(failed), sorted(failed))
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--task-ids", nargs="+", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--max-rounds", type=int, default=4)
    parser.add_argument("--confirm", type=int, default=2, help="Extra full passes required")
    parser.add_argument("--concurrency", type=int, default=4)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
