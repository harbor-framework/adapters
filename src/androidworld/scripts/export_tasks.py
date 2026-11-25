#!/usr/bin/env python3
"""Export AndroidWorld's 116 tasks (fixed seed scheme) to tasks.json.

Requires the upstream `android_world` package importable (see README). The seed scheme
mirrors `suite_utils.create_suite(n_task_combinations=1, seed=30)`:
    seed_i = int(sha256(f"{SUITE_SEED}_{name}_<idx>").hexdigest(), 16) % 2**32
Usage: python export_tasks.py --aw-path /path/to/android_world --out ../src/androidworld/tasks.json
"""
import argparse, base64, hashlib, json, pickle, random, sys
from pathlib import Path

SUITE_SEED = 30


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--aw-path", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    sys.path.insert(0, a.aw_path)
    from android_world import registry

    reg = registry.TaskRegistry().get_registry("android_world")
    out = []
    for name, cls in sorted(reg.items()):
        # Instance 0 of upstream's suite, except that degenerate instances (a task whose
        # reference rows are empty, e.g. RecipeDeleteMultipleRecipesWithConstraint at seed index 0:
        # nothing to delete, so "doing nothing" scores 1.0) are skipped to the next index.
        for idx in range(50):
            seed = int(hashlib.sha256(f"{SUITE_SEED}_{name}_{idx}".encode()).hexdigest(), 16) % 2**32
            random.seed(seed)
            params = cls.generate_random_params()
            params["seed"] = seed
            if "row_objects" in params and not params["row_objects"]:
                continue
            break
        blob = pickle.dumps(params, protocol=4)  # params may hold dataclasses (Expense, Recipe...)
        t = cls(params)
        t2 = cls(pickle.loads(blob))
        assert t.goal == t2.goal, name
        out.append(
            {
                "name": name,
                "module": cls.__module__,
                "family": cls.__module__.split(".")[-1],
                "seed": seed,
                "seed_index": idx,
                "params_pickle_b64": base64.b64encode(blob).decode(),
                "params_repr": repr(params),
                "goal": t.goal,
                "complexity": float(getattr(cls, "complexity", 1) or 1),
                "app_names": list(getattr(cls, "app_names", ())),
                "tags": list(getattr(cls, "tags", ())),
            }
        )
    Path(a.out).write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {len(out)} tasks")


if __name__ == "__main__":
    main()
