#!/usr/bin/env bash
# Optional standalone BM25 download; the installed adapter uses the same SDK.
set -euo pipefail

python - "${1:-./indexes}" <<'PY'
import sys
from huggingface_hub import snapshot_download

snapshot_download(
    repo_id="Tevatron/browsecomp-plus-indexes",
    repo_type="dataset",
    allow_patterns=["bm25/*"],
    local_dir=sys.argv[1],
)
PY
