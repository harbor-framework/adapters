"""Encode native metrics as finite sufficient statistics without rescaling."""
import math


def numeric_leaves(value: dict, prefix: str = "") -> dict[str, float]:
    result = {}
    for key, item in value.items():
        name = f"{prefix}__{key}" if prefix else key
        if isinstance(item, dict):
            result.update(numeric_leaves(item, name))
        elif isinstance(item, (int, float)) and math.isfinite(item):
            result[name] = float(item)
    return result


def encode_metrics(case: dict, metrics: dict) -> dict[str, float]:
    """Use a per-field denominator; missing errors must not become zero."""
    protocol = case["benchmark"]
    valid = bool(metrics.get("submission_valid"))
    result = {f"{protocol}__cases": 1.0, f"{protocol}__valid": float(valid)}
    if valid:
        for name, value in numeric_leaves(metrics).items():
            if name in {"submission_valid", "evaluation_valid"}:
                continue
            result[f"{protocol}__{name}__sum"] = value
            result[f"{protocol}__{name}__n"] = 1.0
    return result
