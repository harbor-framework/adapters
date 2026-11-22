import os
from pathlib import Path
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
configured = os.environ.get("BIZ_UPSTREAM_ROOT")
SOURCE = (Path(configured) if configured else Path(__file__).resolve().parents[4] / "research/bizagentbench-upstream").resolve()
sys.path[:0] = [str(SOURCE), str(SOURCE / "third_party/tau2-bench/src")]
