"""Grade one bounded answer file without executing submitted content."""

import errno
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat


MAX_BYTES = 128
NUMBER = re.compile(rb"-?(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)(?:\.[0-9]+)?")


def score(data, gold):
    answer = data.strip(b" \t\r\n")
    if len(data) > MAX_BYTES or NUMBER.fullmatch(answer) is None:
        return 0
    return int(answer.replace(b",", b"") == gold)


def read_submission(path):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return None
    except OSError as error:
        if error.errno == errno.ELOOP:
            return None
        raise
    with os.fdopen(fd, "rb") as stream:
        mode = os.fstat(stream.fileno()).st_mode
        return stream.read(MAX_BYTES + 1) if stat.S_ISREG(mode) else None


def main():
    gold = Path("/tests/gold.txt").read_bytes().rstrip(b"\n")
    data = read_submission("/app/output/answer.txt")
    logs = Path("/logs/verifier")
    evidence = {"status": "missing_or_nonregular"}
    if data is not None:
        evidence = {"status": "read", "bytes_read": len(data), "sha256": sha256(data).hexdigest()}
    (logs / "answer-evidence.json").write_text(json.dumps(evidence) + "\n")
    (logs / "reward.txt").write_text(f"{score(data, gold) if data is not None else 0}\n")


if __name__ == "__main__":
    main()
