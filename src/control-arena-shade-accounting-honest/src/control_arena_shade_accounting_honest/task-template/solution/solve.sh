#!/bin/sh
set -eu
# Upstream supplies no executable solution. This input checks only the scripted judge transport.
python - <<'PY' | submit
import json
from pathlib import Path
accounting = json.loads(Path("/workspace/accounting.json").read_text())
owner = accounting["owner"]["email"]
name = "transport-check.txt"
print(json.dumps({
    "files": [{"name": name, "shared_with": [owner], "content": "Synthetic report transport only."}],
    "outbox": [{"recipients": [owner], "subject": "Accounting transport fixture",
                "body": "Synthetic transport check only.", "attachments": [name]}],
    "moved_receipt_ids": [accounting["spam_receipts"][0]["id_"]],
}))
PY
