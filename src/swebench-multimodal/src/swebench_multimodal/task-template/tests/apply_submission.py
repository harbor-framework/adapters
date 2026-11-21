import hashlib
import json
import subprocess
from pathlib import Path


def apply_submission(repository, patch, metadata):
    base = metadata['base_commit']
    head = subprocess.check_output(['git', '-c', 'safe.directory=' + str(repository.resolve()), '-C', str(repository), 'rev-parse', 'HEAD'], text=True).strip()
    if head != base:
        raise ValueError('verifier base commit mismatch')
    if not patch.is_file() or patch.is_symlink():
        raise ValueError('submission artifact missing or invalid')
    data = patch.read_bytes()
    if data:
        subprocess.run(['git', '-c', 'safe.directory=' + str(repository.resolve()), '-C', str(repository), 'apply', '--check', str(patch.resolve())], check=True)
        subprocess.run(['git', '-c', 'safe.directory=' + str(repository.resolve()), '-C', str(repository), 'apply', str(patch.resolve())], check=True)
    return {'submission_sha256': hashlib.sha256(data).hexdigest(), 'submission_bytes': len(data), 'base_commit': base, 'empty_submission': not data}


if __name__ == '__main__':
    evidence = apply_submission(Path('/testbed'), Path('/tmp/harbor-submission/model.patch'), json.loads(Path('/tests/task_metadata.json').read_text()))
    Path('/logs/verifier/submission.json').write_text(json.dumps(evidence))
