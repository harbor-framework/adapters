import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from de_bench_upgrade.adapter import DeBenchUpgradeAdapter, TEMPLATE


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class OverlayTest(unittest.TestCase):
    def test_deleted_globs_and_overlay(self):
        apply = module(TEMPLATE / 'solution/apply.py', 'overlay').apply
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); work = root / 'work'; solution = root / 'solution'
            work.mkdir(); solution.mkdir()
            (work / 'old.py').write_text('old')
            (work / 'keep.txt').write_text('keep')
            (solution / '.deleted').write_text('# comment\n*.py\n')
            (solution / 'new.py').write_text('new')
            apply(solution, work)
            self.assertFalse((work / 'old.py').exists())
            self.assertFalse((work / '.deleted').exists())
            self.assertEqual((work / 'new.py').read_text(), 'new')
            self.assertEqual((work / 'keep.txt').read_text(), 'keep')

    def test_deletion_cannot_escape(self):
        apply = module(TEMPLATE / 'solution/apply.py', 'overlay').apply
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); work = root / 'work'; solution = root / 'solution'
            work.mkdir(); solution.mkdir()
            (solution / '.deleted').write_text('../outside')
            with self.assertRaises(ValueError): apply(solution, work)


@unittest.skipUnless(os.environ.get('DE_BENCH_ROOT'), 'Set DE_BENCH_ROOT to pinned checkout')
class CorpusTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / 'generated'
        self.root = Path(os.environ['DE_BENCH_ROOT'])

    def adapter(self, **kwargs):
        return DeBenchUpgradeAdapter(self.root, self.output, environment_profile='scoring-smoke', **kwargs)

    def test_inventory_and_deterministic_generation(self):
        adapter = self.adapter(split='smoke')
        inventory = adapter.inventory()
        self.assertEqual((inventory['total'], inventory['compatible']), (62,62))
        self.assertEqual(sum(len(t['checks']) for t in inventory['tasks']),214)
        adapter.run()
        def hashes():
            return {str(p.relative_to(self.output)):hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in self.output.rglob('*') if p.is_file()}
        before = hashes()
        self.adapter(split='smoke', overwrite=True).run()
        self.assertEqual(before, hashes())
        for task_id in json.loads((self.output / 'selection.json').read_text())['task_ids']:
            env = self.output / task_id / 'environment'
            self.assertFalse(list(env.rglob('solution')))
            self.assertFalse(list(env.rglob('checks.yaml')))
            self.assertNotIn('COPY . ', (env / 'Dockerfile').read_text())

    def test_unknown_task_and_existing_destination_rejected(self):
        with self.assertRaises(ValueError): self.adapter(task_ids=['../bad']).run()
        self.assertFalse(self.output.exists())
        self.adapter(limit=1).run()
        with self.assertRaises(FileExistsError): self.adapter(limit=1).run()
        (next(p for p in self.output.iterdir() if p.is_dir()) / 'provenance.json').unlink()
        with self.assertRaises(ValueError): self.adapter(limit=1, overwrite=True).run()

    def test_subset_generation_cannot_leave_stale_tasks(self):
        self.adapter(limit=1).run()
        with self.assertRaisesRegex(ValueError, 'Unselected tasks'):
            self.adapter(task_ids=['task-upgrade-v2-a1b2c3'], overwrite=True).run()

    def test_stashed_oracle_edits_are_recovered_without_mutating_agent(self):
        task_id = self.adapter(task_ids=['task-upgrade-v2-a1b2c3']).run()[0]
        task = self.output / task_id
        work = Path(self.temp.name) / 'work'
        shutil.copytree(task / 'environment/workspace', work)
        def git(*args):
            return subprocess.check_output(['git', '-C', str(work), *args], stderr=subprocess.PIPE)
        git('init', '-q'); git('add', '-A')
        git('-c','user.name=test','-c','user.email=test@localhost','commit','-qm','baseline')
        module(task / 'solution/apply.py', 'overlay').apply(task / 'solution/overlay', work)
        git('stash', 'push', '-u', '-m', 'unfinished validation')
        before = git('stash', 'list')
        result_dir = Path(self.temp.name) / 'result'
        subprocess.run([sys.executable, '-I', str(task / 'tests/verify.py'),
                        '--workspace',str(work),'--output-dir',str(result_dir)], check=True, capture_output=True)
        self.assertTrue(json.loads((result_dir / 'result.json').read_text())['pass'])
        self.assertEqual(before, git('stash', 'list'))
        self.assertEqual(git('status', '--porcelain'), b'')

    def security_workspace(self):
        task_id = self.adapter(task_ids=['task-upgrade-v2-a1b2c3']).run()[0]
        task = self.output / task_id
        work = Path(self.temp.name) / 'work'
        shutil.copytree(task / 'environment/workspace', work)
        def git(*args):
            return subprocess.check_output(['git', '-C', str(work), *args], stderr=subprocess.PIPE)
        git('init', '-q'); git('add', '-A')
        git('-c', 'user.name=test', '-c', 'user.email=test@localhost', 'commit', '-qm', 'baseline')
        return task, work, git

    def run_verifier(self, task, work, env=None):
        result = Path(self.temp.name) / 'result'
        result.mkdir(exist_ok=True)
        (result / 'reward.txt').write_text('1\n')  # failures must clear stale success
        proc = subprocess.run([sys.executable, '-I', str(task / 'tests/verify.py'),
                              '--workspace', str(work), '--output-dir', str(result)],
                              capture_output=True, text=True, env=env)
        return proc, result

    def test_stash_recovery_never_executes_submitted_git_configuration(self):
        task, work, git = self.security_workspace()
        module(task / 'solution/apply.py', 'overlay').apply(task / 'solution/overlay', work)
        git('stash', 'push', '-u', '-m', 'oracle')
        marker = Path(self.temp.name) / 'executed'
        script = Path(self.temp.name) / 'malicious-hook'
        script.write_text('#!/bin/sh\ntouch "' + str(marker) + '"\n')
        script.chmod(0o755)
        git('config', 'core.fsmonitor', str(script))
        git('config', 'filter.evil.clean', str(script))
        git('config', 'filter.evil.smudge', str(script))
        git('config', 'merge.evil.driver', str(script))
        (work / '.git/info/attributes').write_text('* filter=evil merge=evil\n')
        shutil.copyfile(script, work / '.git/hooks/post-index-change')
        (work / '.git/hooks/post-index-change').chmod(0o755)
        proc, result = self.run_verifier(task, work)
        self.assertFalse(marker.exists(), 'Submitted Git settings executed during verification')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual((result / 'reward.txt').read_text(), '1\n')

    def test_conflicting_stash_cannot_run_external_merge_driver(self):
        task, work, git = self.security_workspace()
        module(task / 'solution/apply.py', 'overlay').apply(task / 'solution/overlay', work)
        git('stash', 'push', '-u', '-m', 'oracle')
        (work / 'dags/daily_report.py').write_text('# conflicting current DAG\n')
        (work / '.gitattributes').write_text('dags/daily_report.py merge=evil\n')
        git('add', 'dags/daily_report.py', '.gitattributes')
        git('-c', 'user.name=test', '-c', 'user.email=test@localhost', 'commit', '-qm', 'conflicting edit')
        marker = Path(self.temp.name) / 'merge-executed'
        script = Path(self.temp.name) / 'malicious-merge'
        script.write_text('#!/bin/sh\ntouch "' + str(marker) + '"\n')
        script.chmod(0o755)
        git('config', 'merge.evil.driver', str(script))
        proc, result = self.run_verifier(task, work)
        self.assertFalse(marker.exists(), 'Submitted merge driver executed')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue((result / 'result.json').exists())

    def test_verifier_ignores_inherited_git_configuration(self):
        task, work, git = self.security_workspace()
        module(task / 'solution/apply.py', 'overlay').apply(task / 'solution/overlay', work)
        git('stash', 'push', '-u', '-m', 'oracle')
        marker = Path(self.temp.name) / 'executed'
        script = Path(self.temp.name) / 'malicious-hook'
        script.write_text('#!/bin/sh\ntouch "' + str(marker) + '"\n')
        script.chmod(0o755)
        config = Path(self.temp.name) / 'external.gitconfig'
        config.write_text('[core]\nfsmonitor = ' + str(script) + '\n')
        env = dict(os.environ, GIT_CONFIG_GLOBAL=str(config), GIT_CONFIG_SYSTEM=str(config),
                   GIT_CONFIG_COUNT='1', GIT_CONFIG_KEY_0='core.fsmonitor',
                   GIT_CONFIG_VALUE_0=str(script))
        proc, result = self.run_verifier(task, work, env)
        self.assertFalse(marker.exists(), 'Inherited Git settings executed during verification')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual((result / 'reward.txt').read_text(), '1\n')

    def test_escaping_file_directory_and_chained_symlinks_are_rejected(self):
        task, work, git = self.security_workspace()
        for target, name in [(task / 'tests/oracle/solution/dags/daily_report.py', 'leak.txt'),
                             (task / 'tests/oracle/solution', 'leak-dir'),
                             (Path('../generated'), 'relative-leak')]:
            with self.subTest(name=name):
                link = work / name
                link.symlink_to(target)
                (work / 'chained-leak').symlink_to(name)
                try:
                    proc, result = self.run_verifier(task, work)
                    self.assertNotEqual(proc.returncode, 0)
                    self.assertIn('Unsafe submission symlink', proc.stderr)
                    self.assertFalse((result / 'reward.txt').exists())
                finally:
                    link.unlink(); (work / 'chained-leak').unlink()

    def test_workspace_root_cannot_be_replaced_with_oracle_symlink(self):
        task, work, git = self.security_workspace()
        shutil.rmtree(work)
        work.symlink_to(task / 'tests/oracle/solution', target_is_directory=True)
        proc, result = self.run_verifier(task, work)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn('Unsafe submission symlink', proc.stderr)
        self.assertFalse((result / 'reward.txt').exists())

    def test_reference_symlink_cannot_turn_baseline_into_pass(self):
        task, work, git = self.security_workspace()
        dag = work / 'dags/daily_report.py'
        dag.unlink()
        dag.symlink_to(task / 'tests/oracle/solution/dags/daily_report.py')
        proc, result = self.run_verifier(task, work)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn('Unsafe submission symlink', proc.stderr)
        self.assertFalse((result / 'reward.txt').exists())

    def test_escaping_symlink_restored_from_stash_is_rejected(self):
        task, work, git = self.security_workspace()
        (work / 'leak').symlink_to(task / 'tests/oracle/solution')
        git('stash', 'push', '-u', '-m', 'hidden link')
        proc, result = self.run_verifier(task, work)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn('Unsafe submission symlink', proc.stderr)
        self.assertFalse((result / 'reward.txt').exists())

    def test_packed_stashes_recover_with_untrusted_metadata_ignored(self):
        task, work, git = self.security_workspace()
        module(task / 'solution/apply.py', 'overlay').apply(task / 'solution/overlay', work)
        git('stash', 'push', '-u', '-m', 'oracle')
        git('gc', '--prune=now')
        git('pack-refs', '--all')
        before = git('stash', 'list')
        # Importing any of these files would allow external objects/config.
        (work / '.git/objects/info/alternates').write_text('/nonexistent/untrusted/objects\n')
        (work / '.git/config').write_text('invalid agent controlled configuration\n')
        proc, result = self.run_verifier(task, work)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual((result / 'reward.txt').read_text(), '1\n')
        self.assertTrue(before)
        self.assertEqual((work / '.git/config').read_text(), 'invalid agent controlled configuration\n')

    def test_symlinked_git_objects_are_rejected(self):
        task, work, git = self.security_workspace()
        module(task / 'solution/apply.py', 'overlay').apply(task / 'solution/overlay', work)
        git('stash', 'push', '-u', '-m', 'oracle')
        objects = work / '.git/objects'
        outside = Path(self.temp.name) / 'outside-objects'
        objects.rename(outside)
        objects.symlink_to(outside, target_is_directory=True)
        proc, result = self.run_verifier(task, work)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn('Unsafe submitted Git object directory', proc.stderr)
        self.assertFalse((result / 'reward.txt').exists())

    def test_internal_relative_symlinks_still_score(self):
        task, work, git = self.security_workspace()
        module(task / 'solution/apply.py', 'overlay').apply(task / 'solution/overlay', work)
        (work / 'internal-link').symlink_to('dags/daily_report.py')
        (work / 'internal-directory').symlink_to('dags')
        proc, result = self.run_verifier(task, work)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual((result / 'reward.txt').read_text(), '1\n')

    def test_verifier_protected_paths_and_excluded_outputs(self):
        task_id = self.adapter(task_ids=['task-upgrade-v2-a1b2c3']).run()[0]
        task = self.output / task_id
        work = Path(self.temp.name) / 'work'
        shutil.copytree(task / 'environment/workspace', work)
        config_path = task / 'tests/config.json'
        config = json.loads(config_path.read_text())
        config['protected'] = ['NOTES.txt']
        config_path.write_text(json.dumps(config))
        (work / 'NOTES.txt').write_text('protected modification')
        result_dir = Path(self.temp.name) / 'result'
        def verify():
            subprocess.run([sys.executable, '-I', str(task / 'tests/verify.py'),
                            '--workspace',str(work),'--output-dir',str(result_dir)], check=True, capture_output=True)
            return json.loads((result_dir / 'result.json').read_text())
        self.assertFalse(verify()['checks']['do_not_modify']['passed'])
        (work / 'NOTES.txt').unlink()
        (work / 'logs').mkdir()
        (work / 'logs/generated.log').write_text('not delivered')
        self.assertFalse(verify()['checks']['delivered']['passed'])


if __name__ == '__main__': unittest.main()
