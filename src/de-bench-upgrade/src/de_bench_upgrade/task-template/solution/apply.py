"""Apply the upstream solution overlay, including its deletion manifest."""
from pathlib import Path
import shutil
import sys


def apply(solution, workspace):
    solution, workspace = Path(solution), Path(workspace).resolve()
    manifest = solution / '.deleted'
    if manifest.exists():
        for pattern in manifest.read_text().splitlines():
            pattern = pattern.strip()
            if not pattern or pattern.startswith('#'): continue
            if Path(pattern).is_absolute() or '..' in Path(pattern).parts:
                raise ValueError(f'Unsafe deletion pattern: {pattern}')
            for victim in sorted(workspace.glob(pattern)):
                if not victim.resolve().is_relative_to(workspace):
                    raise ValueError(f'Escaping deletion: {victim}')
                if victim.is_file(): victim.unlink()
    for source in solution.rglob('*'):
        if not source.is_file() or source == manifest: continue
        target = workspace / source.relative_to(solution)
        if not target.resolve().is_relative_to(workspace):
            raise ValueError(f'Escaping overlay: {target}')
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)


if __name__ == '__main__':
    apply(*sys.argv[1:])
