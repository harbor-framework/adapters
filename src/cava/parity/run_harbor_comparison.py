"""Run Harbor CAVA parity comparison using the third-party API.

Calls gpt-6.1-sol on the parity subset (551 items) using the same pipeline
messages that CavaPipelineAgent sends, then scores with the Harbor scorer.
Compares against the upstream prediction-file scores from CAVA@1af23b1.

Usage:
    uv run python parity/run_harbor_comparison.py [--limit N] [--subtasks a,b]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PARITY_DIR = Path(__file__).resolve().parent

# Path setup: cava package, scoring helpers (upstream_function_calling etc.), and
# the parity/ offline stub (replaces Docker-only offline.py).
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "src" / "cava" / "scoring"))
sys.path.insert(0, str(PARITY_DIR))

from cava.subtasks import SUBTASKS  # noqa: E402

MANIFESTS = REPO / "src" / "cava" / "manifests"
DATA = REPO / "src" / "cava" / "data"
PARITY_IDS_FILE = DATA / "parity_ids.json"
FUNCTIONS_FILE = DATA / "functions.json"

# Upstream scores from CAVA@1af23b1 committed prediction files (scorer check done)
UPSTREAM_SCORES = {
    "deception_detection": {"score": 14.6, "n": 151, "source": "pipeline gpt-4o-mini-transcribe→gpt-4o"},
    "function_calling":    {"score": 27.0, "n": 1000, "source": "pipeline gpt-4o-mini-transcribe→gpt-4o"},
    "jailbreak":           {"score": 21.0, "n": 520, "source": "refusal rate (100-ASR=79.0%)"},
    "jeopardy":            {"score": 96.9, "n": 1000, "source": "pipeline gpt-4o-mini-transcribe→gpt-4o"},
    "multimodal_instruction_following": {"score": None, "n": 1000, "source": "random upstream scoring (not usable)"},
}

import os

API_BASE = os.environ.get("CAVA_PARITY_API_BASE", "https://api.openai.com/v1")
API_KEY = os.environ.get("CAVA_PARITY_API_KEY", "")
MODEL = os.environ.get("CAVA_PARITY_MODEL", "gpt-4o")
MAX_CONCURRENCY = int(os.environ.get("CAVA_PARITY_CONCURRENCY", "4"))


def load_parity_manifests(subtask: str, parity_ids: list) -> list[dict]:
    """Load parity manifest rows for a subtask."""
    rows = {}
    with open(MANIFESTS / f"{subtask}.jsonl") as f:
        for line in f:
            rec = json.loads(line)
            rows[rec["item_id"]] = rec
    result = []
    for item_id in parity_ids:
        if item_id not in rows:
            raise ValueError(f"parity id {item_id} not found in {subtask}.jsonl")
        result.append(rows[item_id])
    return result


def build_pipeline_messages(subtask: str, row: dict) -> list[dict]:
    """Build the two pipeline user messages for this item (same as CavaPipelineAgent)."""
    st = SUBTASKS[subtask]
    return st.pipeline_messages(row["record"], row["transcript"])


async def call_api(client, messages: list[dict], tools=None) -> tuple[str, list[dict]]:
    """Call the API, handle tool call loop for function_calling subtask.
    Returns (text_response, function_calls_list).
    """
    api_args = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0,
    }
    if tools:
        api_args["tools"] = tools
        api_args["tool_choice"] = "required"

    llm_response = ""
    all_function_calls: list[dict] = []
    conversation = list(messages)

    for attempt in range(5):
        try:
            completion = await client.chat.completions.create(**api_args)
            all_function_calls = []

            # Tool call loop (function_calling subtask)
            while (
                tools
                and completion.choices[0].message.tool_calls
                and len(all_function_calls) < 10
            ):
                assistant_message = completion.choices[0].message
                final_response = assistant_message.content or ""
                conversation.append({
                    "role": "assistant",
                    "content": assistant_message.content,
                    "tool_calls": [tc.model_dump() for tc in assistant_message.tool_calls],
                })
                for tool_call in assistant_message.tool_calls:
                    try:
                        arguments = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        arguments = {"error": "Failed to parse arguments",
                                     "raw": tool_call.function.arguments}
                    all_function_calls.append(
                        {"name": tool_call.function.name, "arguments": arguments}
                    )
                    conversation.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": f"MOCK_RESPONSE({tool_call.function.name})",
                    })
                completion = await client.chat.completions.create(
                    model=MODEL, messages=conversation, temperature=0,
                    tools=tools, tool_choice="auto",
                )

            if not all_function_calls:
                llm_response = completion.choices[0].message.content or ""
            else:
                llm_response = final_response

            break
        except Exception as exc:
            if attempt == 4:
                raise RuntimeError(f"API call exhausted retries: {exc}") from exc
            await asyncio.sleep(0.1 * (2 ** attempt))

    # Blank response if >= 10 function calls (upstream behavior)
    if tools and len(all_function_calls) >= 10:
        llm_response = ""

    return llm_response, all_function_calls


async def score_response(subtask: str, record: dict, response: str, function_calls: list[dict]) -> float:
    """Score using the Harbor scorer (cava_score.py logic)."""
    # Import here so path is set up before first import
    from cava.scoring import cava_score  # noqa: PLC0415

    correct, _ = cava_score.score_record(subtask, record, response, function_calls)
    return float(correct)


async def run_subtask(client, subtask: str, rows: list[dict], sem: asyncio.Semaphore,
                      tools=None, results_dir: Path | None = None) -> dict:
    """Run all parity items for a subtask, return {item_id: score}."""
    total = len(rows)
    scores = {}
    exceptions = {}

    async def process_one(row):
        item_id = row["item_id"]
        messages = build_pipeline_messages(subtask, row)
        async with sem:
            try:
                response, function_calls = await call_api(client, messages, tools)
                score = await score_response(subtask, row["record"], response, function_calls)
                scores[item_id] = score
                if results_dir:
                    (results_dir / f"{item_id}.json").write_text(json.dumps({
                        "item_id": item_id,
                        "response": response,
                        "function_calls": function_calls,
                        "score": score,
                    }))
            except Exception as exc:
                exceptions[item_id] = str(exc)
                scores[item_id] = None
                print(f"  ERROR {item_id}: {exc}", file=sys.stderr)

    tasks = [process_one(row) for row in rows]
    done = 0
    for coro in asyncio.as_completed(tasks):
        await coro
        done += 1
        if done % 20 == 0:
            valid = [s for s in scores.values() if s is not None]
            mean = 100 * sum(valid) / len(valid) if valid else float("nan")
            print(f"  {subtask}: {done}/{total} done, running mean={mean:.1f}%", flush=True)

    return {"scores": scores, "exceptions": exceptions}


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subtasks", default=",".join(SUBTASKS.keys()))
    ap.add_argument("--limit", type=int, default=None,
                    help="limit items per subtask (for a quick sanity check)")
    ap.add_argument("--output", type=Path, default=Path("/tmp/cava_comparison_results"))
    args = ap.parse_args()

    from openai import AsyncOpenAI
    client = AsyncOpenAI(base_url=API_BASE, api_key=API_KEY)
    tools = json.loads(FUNCTIONS_FILE.read_text())
    parity_ids = json.loads(PARITY_IDS_FILE.read_text())
    sem = asyncio.Semaphore(MAX_CONCURRENCY)

    args.output.mkdir(parents=True, exist_ok=True)
    selected = [s for s in args.subtasks.split(",") if s.strip()]

    results_summary = {}
    for subtask in selected:
        ids = parity_ids[subtask]
        rows = load_parity_manifests(subtask, ids)
        if args.limit:
            rows = rows[:args.limit]
            print(f"\n=== {subtask}: running {len(rows)}/{len(ids)} items (limited) ===")
        else:
            print(f"\n=== {subtask}: running all {len(rows)} parity items ===")

        sub_dir = args.output / subtask
        sub_dir.mkdir(exist_ok=True)
        sub_tools = tools if subtask == "function_calling" else None

        result = await run_subtask(client, subtask, rows, sem, sub_tools, sub_dir)
        (args.output / f"{subtask}_result.json").write_text(json.dumps(result, indent=2))

        valid = [s for s in result["scores"].values() if s is not None]
        if valid:
            mean = 100 * sum(valid) / len(valid)
            if subtask == "jailbreak":
                harbor_score = 100 - mean  # ASR
                score_label = f"ASR={harbor_score:.1f}% (refusal={mean:.1f}%)"
            else:
                harbor_score = mean
                score_label = f"{harbor_score:.1f}%"
        else:
            harbor_score = None
            score_label = "N/A"

        upstream = UPSTREAM_SCORES.get(subtask, {})
        results_summary[subtask] = {
            "n": len(rows),
            "complete": len(valid),
            "exceptions": len(result["exceptions"]),
            "harbor_score": harbor_score,
            "upstream_score": upstream.get("score"),
            "upstream_n": upstream.get("n"),
            "upstream_source": upstream.get("source"),
        }
        print(f"  {subtask}: Harbor={score_label}  |  Upstream={upstream.get('score', 'N/A')}%")

    # Print summary table
    print("\n" + "=" * 80)
    print("CAVA Parity Comparison: Harbor (gpt-6.1-sol) vs Upstream (CAVA@1af23b1)")
    print("=" * 80)
    print(f"{'Subtask':<36} {'Harbor':<12} {'Upstream':<12} {'Delta':<10} {'Source'}")
    print("-" * 100)
    for subtask, r in results_summary.items():
        h = r["harbor_score"]
        u = r["upstream_score"]
        h_str = f"{h:.1f}%" if h is not None else "N/A"
        u_str = f"{u:.1f}%" if u is not None else "N/A"
        delta = f"{(h - u):+.1f}%" if (h is not None and u is not None) else "N/A"
        print(f"{subtask:<36} {h_str:<12} {u_str:<12} {delta:<10} {r['upstream_source'] or ''}")

    (args.output / "summary.json").write_text(json.dumps(results_summary, indent=2))
    print(f"\nResults saved to {args.output}/")


if __name__ == "__main__":
    asyncio.run(main())
