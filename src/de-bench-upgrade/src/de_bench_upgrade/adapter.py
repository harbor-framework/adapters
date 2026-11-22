"""Translate the pinned upgrade-v2 corpus without changing its checks."""
from __future__ import annotations

import ast
import hashlib
import io
import json
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

UPSTREAM_COMMIT = '5dcfc2b81b13dcf58cff49e192e97f1ae05f8dbc'
TEMPLATE = Path(__file__).parent / 'task-template'
SMOKE_IDS = ('task-upgrade-v2-a1b2c3', 'task-upgrade-v2-23f2a0',
             'task-upgrade-v2-2c5f8a', 'task-upgrade-v2-cosme01', 'task-upgrade-v2-dgfh01')


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def extract(data, destination):
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
        archive.extractall(destination, filter='data')


class DeBenchUpgradeAdapter:
    def __init__(self, upstream_root, output_dir, *, limit=None, overwrite=False,
                 task_ids=None, split='full', environment_profile='upstream-runtime',
                 package_index_url='https://pypi.org/simple/'):
        self.root = Path(upstream_root).resolve()
        self.output_dir = Path(output_dir).resolve()
        self.limit, self.overwrite = limit, overwrite
        self.task_ids, self.split = task_ids, split
        if environment_profile not in {'scoring-smoke', 'upstream-runtime'}:
            raise ValueError(f'Unknown environment profile: {environment_profile}')
        if not re.fullmatch(r'https?://[A-Za-z0-9._:/-]+', package_index_url):
            raise ValueError('Package index must be a plain HTTP(S) URL without credentials or shell syntax')
        self.package_index_url = package_index_url
        self.profile = environment_profile
        revision = subprocess.check_output(['git', '-C', str(self.root), 'rev-parse', 'HEAD'], text=True).strip()
        if revision != UPSTREAM_COMMIT:
            raise ValueError(f'Expected upstream {UPSTREAM_COMMIT}, got {revision}; review before updating the pin')
        if subprocess.check_output(['git', '-C', str(self.root), 'status', '--porcelain', '--untracked-files=all'], text=True).strip():
            raise ValueError('Upstream checkout must be clean (including untracked files)')
        sys.path.insert(0, str(self.root / 'src'))
        from de_bench import tasks
        if Path(tasks.__file__).resolve() != self.root / 'src/de_bench/tasks.py':
            raise ValueError('A different de_bench package is already loaded')
        self.api = tasks
        self.tasks = [t for t in tasks.load_tasks(self.root, include_drafts=True) if t.world.name == 'upgrade-v2']
        tree = ast.parse((self.root / 'src/de_bench/modal_app.py').read_text())
        self.excludes = next(ast.literal_eval(n.value) for n in ast.walk(tree)
                             if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == '_add_excludes' for t in n.targets))

    @staticmethod
    def exclusions(task):
        reasons = []
        if task.status != 'ready': reasons.append('not ready')
        if not task.own_workspace or not task.oracle_dir: reasons.append('missing workspace/oracle')
        if any(c['kind'] != 'scoring_primitive' for c in task.checks): reasons.append('non-static checks')
        if task.live_env: reasons.append('live_env')
        if task.history or task.replay_dags: reasons.append('history/replay')
        if task.verifier_dir: reasons.append('external verifier')
        if task.setup_sql or task.workspace_data or task.world.generated: reasons.append('runtime data setup')
        if task.image != 'default' or task.env: reasons.append('custom image/environment')
        return reasons

    def inventory(self):
        import yaml
        rows = []
        for t in self.tasks:
            spec = yaml.safe_load((t.dir / 'task.yaml').read_text())
            rows.append(dict(task_id=t.id, status=t.status, difficulty=t.difficulty,
                checks=list(t.checks), source=spec.get('source'), target=spec.get('target'),
                live_env=t.live_env, start_airflow=t.start_airflow, boot_airflow=t.boot_airflow,
                history=list(t.history), replay_dags=t.replay_dags, protected=list(t.do_not_modify),
                has_solution=bool(t.oracle_dir), has_deletions=(t.dir / 'solution/.deleted').exists(),
                workspace_sha=self.api.workspace_sha(t), exclusions=self.exclusions(t),
                requirements=(t.dir / 'workspace/requirements.txt').read_text() if (t.dir / 'workspace/requirements.txt').exists() else None))
        return dict(upstream_commit=UPSTREAM_COMMIT, total=len(rows),
                    compatible=sum(not r['exclusions'] for r in rows), tasks=rows)

    def run(self):
        if self.limit is not None and self.limit < 1:
            raise ValueError('--limit must be positive')
        wanted = set(self.task_ids or (SMOKE_IDS if self.split == 'smoke' else ()))
        known = {t.id for t in self.tasks}
        if wanted - known: raise ValueError(f'Unknown task IDs: {sorted(wanted - known)}')
        selected = [t for t in self.tasks if not wanted or t.id in wanted]
        rejected = [t.id for t in selected if self.exclusions(t)]
        if wanted and rejected: raise ValueError(f'Unsupported requested tasks: {rejected}')
        selected = [t for t in selected if not self.exclusions(t)]
        if self.limit: selected = selected[:self.limit]
        if self.output_dir.exists():
            selected_ids = {t.id for t in selected}
            stale = sorted(p.name for p in self.output_dir.iterdir()
                           if p.is_dir() and (p / 'task.toml').exists() and p.name not in selected_ids)
            if stale:
                raise ValueError(f'Unselected tasks would remain in output: {stale}; use a fresh output directory')
        # Preflight every destination before writing anything; never erase unrelated files.
        for t in selected:
            dest = self.output_dir / t.id
            if dest.exists():
                if not self.overwrite: raise FileExistsError(dest)
                marker = dest / 'provenance.json'
                if not marker.exists() or json.loads(marker.read_text()).get('adapter') != 'de-bench-upgrade':
                    raise ValueError(f'Refusing to overwrite non-adapter directory: {dest}')
        self.output_dir.mkdir(parents=True, exist_ok=True)
        dump(self.output_dir / 'inventory.json', self.inventory())
        for t in selected:
            self.generate(t)
        dump(self.output_dir / 'selection.json', dict(upstream_commit=UPSTREAM_COMMIT,
            environment_profile=self.profile, package_index_url=self.package_index_url, split=self.split, task_ids=[t.id for t in selected],
            excluded={t.id:self.exclusions(t) for t in self.tasks if self.exclusions(t)}))
        return [t.id for t in selected]

    def generate(self, task):
        out = self.output_dir / task.id
        if out.exists(): shutil.rmtree(out)
        shutil.copytree(TEMPLATE, out)
        dump(out / 'environment/add-excludes.json', self.excludes)
        if self.profile == 'upstream-runtime':
            runtime = (TEMPLATE.parent / 'runtime/Dockerfile').read_text()
            runtime = runtime.replace('ARG UV_DEFAULT_INDEX=https://pypi.org/simple/',
                                      f'ARG UV_DEFAULT_INDEX={self.package_index_url}')
            (out / 'environment/Dockerfile').write_text(runtime)
            shutil.copyfile(TEMPLATE.parent / 'runtime/requirements.lock',
                            out / 'environment/runtime-requirements.txt')
            script = out / 'tests/test.sh'
            script.write_text(script.read_text().replace('${VERIFIER_PYTHON:-python}', '/opt/verifier-venv/bin/python'))
        workspace = self.api.workspace_tar(task)
        extract(workspace, out / 'environment/workspace')
        # Original bytes are private and used to reconstruct the scorer's fresh workspace.
        # Normalize tar metadata for deterministic generated artifacts.
        with tarfile.open(fileobj=io.BytesIO(workspace), mode='r:gz') as src:
            with tarfile.open(out / 'tests/workspace.tar', 'w') as dst:
                for member in src:
                    member.mtime = 0
                    dst.addfile(member, src.extractfile(member) if member.isfile() else None)
        extract(self.api.oracle_tar(task), out / 'tests/oracle')
        shutil.copytree(task.dir / 'solution', out / 'solution/overlay')
        (out / 'instruction.md').write_text(self.api.system_prompt(task).rstrip() + '\n\n' + task.prompt + '\n')
        config = dict(task_id=task.id, checks=list(task.checks), protected=list(task.do_not_modify),
                      replay_dags=list(task.replay_dags or ()), add_excludes=self.excludes)
        dump(out / 'tests/config.json', config)
        shutil.copyfile(task.dir / 'checks.yaml', out / 'tests/checks.yaml')
        source = out / 'tests/upstream/de_bench'
        source.mkdir(parents=True)
        for name in ('__init__.py','scoring.py'):
            shutil.copyfile(self.root / 'src/de_bench' / name, source / name)
        shutil.copytree(self.root / 'src/de_bench/upgrade_v2_scoring', source / 'upgrade_v2_scoring', ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copyfile(self.root / 'LICENSE', out / 'tests/upstream/LICENSE')
        hashes = {str(p.relative_to(out / 'tests/upstream')): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in sorted((out / 'tests/upstream').rglob('*')) if p.is_file()}
        dump(out / 'provenance.json', dict(adapter='de-bench-upgrade', upstream_commit=UPSTREAM_COMMIT,
             task_id=task.id, environment_profile=self.profile, package_index_url=self.package_index_url,
             dockerfile_sha256=hashlib.sha256((out / 'environment/Dockerfile').read_bytes()).hexdigest(),
             runtime_lock_sha256=hashlib.sha256((out / 'environment/runtime-requirements.txt').read_bytes()).hexdigest() if self.profile == 'upstream-runtime' else None,
             source_sha256=hashes))
        config_text = (out / 'task.toml').read_text().replace('__TASK_ID__', task.id).replace('__TIMEOUT__', str(task.max_wall_seconds)).replace('scoring-smoke', self.profile)
        if self.profile == 'upstream-runtime':
            config_text = config_text.replace('build_timeout_sec = 600', 'build_timeout_sec = 1800')
        (out / 'task.toml').write_text(config_text)
