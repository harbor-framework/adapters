"""Create the same visible initial Git snapshot as upstream."""
import json
from pathlib import Path
import subprocess

excludes = json.loads(Path('/tmp/add-excludes.json').read_text())
def git(*args):
    subprocess.run(['git', '-c', 'user.name=platform', '-c', 'user.email=platform@internal', *args], check=True)
git('init', '-q')
git('add', '-A', *excludes)
git('commit', '-qm', 'initial import')
Path('/tmp/add-excludes.json').unlink()
