"""Shared accounting: interrupted evaluations are not incorrect chess answers."""
import json
from pathlib import Path
from .token_counting import count_settings


class IncompleteEvaluation(RuntimeError):
    def __init__(self, result):
        self.result = result
        super().__init__("Evaluation incomplete; inspect outcome.json and native logs")


def usage_summary(model_usage):
    raw = {name: usage.model_dump(mode="json") for name, usage in (model_usage or {}).items()}
    def total(field):
        return sum(row.get(field) or 0 for row in raw.values())
    uncached = total("input_tokens")
    read, write = total("input_tokens_cache_read"), total("input_tokens_cache_write")
    return {"input_tokens": uncached + read + write, "uncached_input_tokens": uncached,
            "cache_read_tokens": read, "cache_write_tokens": write,
            "output_tokens": total("output_tokens"), "by_model": raw}


def evaluation_outcome(log, ids, log_dir, token_count_mode="provider"):
    rows = []
    for sample in log.samples or []:
        limit = sample.limit.model_dump(mode="json") if sample.limit else None
        error = sample.error.model_dump(mode="json") if sample.error else None
        rows.append({"id": sample.id, "status": "error" if error else "limited" if limit else "complete",
                     "limit": limit, "error": error, "reward": None,
                     "answer": sample.output.completion, "metadata": sample.metadata,
                     "usage": usage_summary(sample.model_usage),
                     "compactions": [event.model_dump(mode="json", include={
                         "type", "tokens_before", "tokens_after", "source"})
                         for event in sample.events if event.event == "compaction"]})
    complete = (log.status == "success" and sorted(row["id"] for row in rows) == sorted(ids)
                and all(row["status"] == "complete" for row in rows))
    result = {"status": "complete" if complete else "incomplete", "inspect_log": log.location,
              "samples": rows, "usage": usage_summary(log.stats.model_usage if log.stats else None),
              "token_counting": count_settings(token_count_mode)}
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    Path(log_dir, "outcome.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def require_complete(result):
    if result["status"] != "complete":
        raise IncompleteEvaluation(result)
