"""Capture delivered changes, rebuild a clean tree, then invoke upstream scoring."""
import argparse
import json
import os
import re
import stat
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'upstream'))
from de_bench.scoring import score_workspace


# Never inherit Git configuration, helpers, or executable search paths from the
# submitted repository or the agent environment. All repositories we operate on
# are initialized here; no submitted config, hooks, index, or attributes are used.
GIT_ENV = {
    'PATH': '/usr/bin:/bin', 'LC_ALL': 'C',
    'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_SYSTEM': '/dev/null',
    'GIT_CONFIG_GLOBAL': '/dev/null', 'GIT_ATTR_NOSYSTEM': '1',
    'GIT_TERMINAL_PROMPT': '0',
}
GIT_COMMAND = [
    '/usr/bin/git', '--no-replace-objects',
    '-c', 'core.hooksPath=/dev/null', '-c', 'core.fsmonitor=false',
    '-c', 'core.attributesFile=/dev/null', '-c', 'core.excludesFile=/dev/null',
    '-c', 'core.sshCommand=false', '-c', 'credential.helper=',
    '-c', 'protocol.allow=never', '-c', 'gc.auto=0', '-c', 'maintenance.auto=false',
    '-c', 'user.name=bench', '-c', 'user.email=bench@localhost',
]
OID = re.compile(r'[0-9a-f]{40}')


def git_run(root, *args):
    return subprocess.run(GIT_COMMAND + ['-C', str(root), *args], env=GIT_ENV,
                          capture_output=True)


def git(root, *args):
    result = git_run(root, *args)
    result.check_returncode()
    return result.stdout


def validate_symlinks(root):
    """Check files AND directory links without following directory links."""
    root = root.resolve()
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            path = Path(directory) / name
            if path.is_symlink():
                try:
                    target = path.resolve()
                except (OSError, RuntimeError) as error:
                    raise ValueError(f'Unsafe submission symlink: {path}') from error
                if not target.is_relative_to(root):
                    raise ValueError(f'Unsafe submission symlink: {path}')
        # Agent Git metadata is handled separately, never as submitted code.
        if Path(directory) == root and '.git' in dirs:
            dirs.remove('.git')


def regular_git_path(repo, relative):
    """Read metadata as data only, never traversing metadata symlinks."""
    relative = Path(relative)
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Unsafe Git metadata path')
    path = repo
    for part in relative.parts:
        path = path / part
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode) or not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
            raise ValueError(f'Unsafe Git metadata path: {path}')
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError(f'Expected regular Git metadata file: {path}')
    return path


def git_text(repo, relative):
    return regular_git_path(repo, relative).read_text()


def submitted_head(repo):
    value = git_text(repo, 'HEAD').strip()
    if value.startswith('ref: refs/'):
        ref = value[5:]
        try:
            value = git_text(repo, ref).strip()
        except FileNotFoundError:
            value = ''
            for line in git_text(repo, 'packed-refs').splitlines():
                fields = line.split()
                if len(fields) == 2 and fields[1] == ref:
                    value = fields[0]
                    break
    if not OID.fullmatch(value):
        raise ValueError('Unsupported submitted Git HEAD')
    return value


def copy_git_objects(source, destination):
    """Import only SHA-1 objects/packs, never alternates or executable metadata."""
    objects = source / 'objects'
    if objects.is_symlink() or not objects.is_dir():
        raise ValueError('Unsafe submitted Git object directory')
    for directory in objects.iterdir():
        if not (re.fullmatch(r'[0-9a-f]{2}', directory.name) or directory.name == 'pack'):
            continue
        if directory.is_symlink() or not directory.is_dir():
            raise ValueError('Unsafe submitted Git object directory')
        for path in directory.iterdir():
            pattern = r'pack-[0-9a-f]{40}\.(pack|idx)' if directory.name == 'pack' else r'[0-9a-f]{38}'
            if not re.fullmatch(pattern, path.name):
                continue
            relative = path.relative_to(source)
            regular_git_path(source, relative)
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)


def recover_stashes(workspace, destination):
    """Restore stashes in an isolated scratch repository with trusted metadata."""
    source = workspace / '.git'
    if source.is_symlink():
        raise ValueError('Unsafe submitted Git directory')
    if not source.is_dir():
        return
    try:
        lines = git_text(source, 'logs/refs/stash').splitlines()
    except FileNotFoundError:
        return
    stashes = []
    for line in reversed(lines):
        fields = line.split()
        if len(fields) < 2 or not OID.fullmatch(fields[1]):
            raise ValueError('Invalid submitted stash reflog')
        stashes.append(fields[1])
    if not stashes:
        return
    # No original/scorer/oracle files live in this recovery directory. Only
    # validated objects and commit IDs cross into the newly initialized Git repo.
    with tempfile.TemporaryDirectory(prefix='de-bench-recovery-') as temporary:
        recovery = Path(temporary)
        shutil.copytree(destination, recovery, dirs_exist_ok=True, symlinks=True,
                        ignore=shutil.ignore_patterns('.git'))
        git(recovery, 'init', '-q', '--template=')
        copy_git_objects(source, recovery / '.git')
        head = submitted_head(source)
        git(recovery, 'update-ref', 'HEAD', head)
        git(recovery, 'read-tree', head)
        for stash in stashes:
            if git_run(recovery, 'stash', 'apply', '-q', stash).returncode:
                # Match upstream conflict recovery, with NUL-safe filenames.
                for path in git(recovery, 'diff', '--name-only', '--diff-filter=U', '-z').split(b'\0'):
                    if path:
                        git(recovery, 'checkout', '--ours', '--', os.fsdecode(path))
            validate_symlinks(recovery)
        # Replace the submitted tree, preserving the private baseline's Git dir.
        clear_tree(destination, keep_git=True)
        shutil.copytree(recovery, destination, dirs_exist_ok=True, symlinks=True,
                        ignore=shutil.ignore_patterns('.git'))


def clear_tree(root, keep_git=False):
    for child in root.iterdir():
        if keep_git and child.name == '.git':
            continue
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()


def unpack(root):
    with tarfile.open(HERE / 'workspace.tar') as archive:
        archive.extractall(root, filter='data')


def verify(workspace, output):
    workspace, output = Path(workspace), Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / 'reward.txt').unlink(missing_ok=True)
    if workspace.is_symlink():
        raise ValueError(f'Unsafe submission symlink: {workspace}')
    workspace = workspace.resolve()
    config = json.loads((HERE / 'config.json').read_text())
    if any(c['kind'] != 'scoring_primitive' for c in config['checks']):
        raise ValueError('Unsupported check: refusing to omit runtime semantics')
    with tempfile.TemporaryDirectory(prefix='de-bench-score-') as temporary:
        root = Path(temporary)
        unpack(root)
        git(root, 'init', '-q', '--template=')
        git(root, 'add', '-A', *config['add_excludes'])
        git(root, '-c', 'user.name=bench', '-c', 'user.email=bench@localhost', 'commit', '-qm', 'baseline')
        # Use the private original tree as the baseline, never the agent's HEAD.
        validate_symlinks(workspace)
        clear_tree(root, keep_git=True)
        shutil.copytree(workspace, root, dirs_exist_ok=True, symlinks=True,
                        ignore=shutil.ignore_patterns('.git'))
        recover_stashes(workspace, root)
        validate_symlinks(root)
        git(root, 'add', '-A', *config['add_excludes'])
        patch = git(root, 'diff', '--cached', '--binary', 'HEAD')
        (output / 'changes.patch').write_bytes(patch)
        # Upstream discards runtime outputs and grades only a fresh tree + patch.
        clear_tree(root)
        unpack(root)
        if patch.strip():
            git(root, 'init', '-q', '--template=')
            git(root, 'apply', '--binary', '--whitespace=nowarn', str((output / 'changes.patch').resolve()))
        validate_symlinks(root)
        result = score_workspace(str(root), config['checks'], config['protected'],
                    patch.decode(errors='replace'), baseline_dags=[], replay_dags=config['replay_dags'],
                    oracle_dir=str(HERE / 'oracle'))
        (output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        (output / 'reward.txt').write_text('1\n' if result['pass'] else '0\n')
        return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args()
    verify(args.workspace, args.output_dir)
