"""Public-response-only reference client. No world, contract or grader access."""
import json
from pathlib import Path
import subprocess
import sys


class PublicTools:
    def __init__(self, source, task_id, output):
        self.output = Path(output)
        self.dialogue = []
        self.finished = False
        self.process = subprocess.Popen([
            sys.executable, '-I', '-X', 'utf8', str(Path(__file__).with_name('reference_service.py')),
            '--source-dir', str(source), '--task-id', task_id, '--output', str(output),
        ], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding='utf-8')
        self.unlocked = {}

    def close(self):
        if self.process.poll() is not None:
            assert self.process.returncode == 0
            return
        self.process.stdin.write('null\n')
        self.process.stdin.flush()
        self.process.stdin.close()
        self.process.wait(timeout=20)
        assert self.process.returncode == 0

    def call(self, actor, tool, **arguments):
        self.process.stdin.write(json.dumps(dict(actor=actor, tool=tool, arguments=arguments)) + '\n')
        self.process.stdin.flush()
        line = self.process.stdout.readline()
        if not line:
            raise RuntimeError('Public tool service exited')
        result = json.loads(line)
        if not result['ok']:
            raise RuntimeError((tool, arguments, result))
        return result['data']

    def read(self, resource, record_id):
        return self.call('assistant', 'get_record', resource=resource, record_id=record_id)

    def rows(self, resource, filters=None):
        rows, cursor = [], None
        while True:
            parameters = dict(resource=resource, limit=100)
            if filters is not None:
                parameters['filters'] = filters
            if cursor:
                parameters['cursor'] = cursor
            page = self.call('assistant', 'search_records', **parameters)
            rows.extend(self.read(resource, row['id']) for row in page['records'])
            cursor = page.get('next_cursor')
            if not cursor:
                return rows

    def one(self, resource):
        rows = self.rows(resource)
        assert len(rows) == 1, (resource, rows)
        return rows[0]

    def docs(self, *ids):
        for document_id in ('PX-COMMON', 'PX-DATABASE', *ids):
            self.call('assistant', 'read_document', document_id=document_id)
        self.rows('xp_cases')

    def write(self, operation, **arguments):
        if operation not in self.unlocked:
            self.unlocked[operation] = self.call('assistant', 'unlock_discoverable_agent_tool', capability_name=operation)
        proposal = self.call('assistant', 'call_discoverable_agent_tool', capability_name=operation, arguments=arguments)
        if not self.unlocked[operation]['approval_required']:
            return proposal
        requests = self.call('user', 'get_my_requests')
        pending = next(row for row in requests if row['id'] == proposal['id'])
        assert pending['arguments'] == arguments and pending['status'] == 'PENDING'
        approval = self.call('user', 'decide_request', request_id=proposal['id'], decision='APPROVE')
        assert approval['status'] == 'APPROVED'
        return self.call('assistant', 'execute_request', request_id=proposal['id'])

    def wait(self):
        return self.call('user', 'wait_for_update')

    def finish(self, summary):
        result = self.call('assistant', 'record_case_outcome', outcome='COMPLETED', summary=summary)
        self.finished = True
        return result

    def customer_facts(self, question, answer):
        """Author a customer reply from customer instructions, never evaluator data."""
        self.dialogue.append({'question': question, 'answer': answer})
        self.output.mkdir(parents=True, exist_ok=True)
        (self.output / 'customer-dialogue.json').write_text(json.dumps(self.dialogue, indent=2), 'utf-8')
