"""Public-response reference controller. No user-role execution or grader access.

Business plans run in a worker and yield assistant tool calls / customer questions.
Customer portal receipts are reports, not authorization: the native engine remains
the authority and rejects executions without real approval. Unsupported prose or
changed business requirements stop safely; no model is used to parse responses.
"""
from copy import deepcopy
import json
import queue
import re
import threading


class ReferenceStopped(RuntimeError):
    pass


def json_value(text):
    if isinstance(text, (dict, list)):
        return text
    decoder = json.JSONDecoder()
    for match in re.finditer(r'[\[{]', str(text)):
        try:
            value, _ = decoder.raw_decode(str(text)[match.start():])
            return value
        except ValueError:
            pass
    return None


class PublicSession:
    def __init__(self, emit):
        self.emit = emit
        self.unlocked = {}
        self.finished = False
        self.idle_waits = 0

    def tool(self, tool, **arguments):
        result = self.emit({'kind': 'tool', 'tool': tool, 'arguments': arguments})
        if not isinstance(result, dict) or result.get('ok') is not True:
            raise ReferenceStopped(f'{tool} failed: {result}')
        return result['data']

    def customer(self, kind, **arguments):
        request = {'kind': kind, **arguments}
        for attempt in range(3):
            reply = self.emit({'kind': 'customer', 'request': request, 'attempt': attempt})
            text = str(reply)
            value = json_value(reply)
            if isinstance(value, dict) and value.get('ok') is False:
                raise ReferenceStopped(f'Customer portal action unavailable: {value.get("error", "unknown")}')
            if re.search(r'\b(decline[ds]?|reject(?:ed)?|refuse[ds]?|do not execute|withdraw consent)\b|拒绝|撤销授权', text, re.I):
                raise ReferenceStopped('Customer declined or withdrew consent.')
            if isinstance(value, dict) and value.get('ok') is True and 'data' in value:
                return value['data']
            if isinstance(value, dict) and kind == 'facts':
                return value
            # Clarification/pending/plain approval are never treated as receipts.
        raise ReferenceStopped('Could not verify the customer response after three requests; no further action taken.')

    def call(self, actor, tool, **arguments):
        if actor == 'assistant':
            return self.tool(tool, **arguments)
        if actor == 'user' and tool in ('list_my_files', 'upload_file'):
            data = self.customer('portal', tool=tool, arguments=arguments)
            if tool == 'list_my_files' and not isinstance(data, list):
                raise ReferenceStopped('Expected the actual file listing.')
            if tool == 'upload_file' and (not isinstance(data, dict) or not data.get('id')):
                raise ReferenceStopped('No actual upload receipt was provided.')
            return data
        raise ReferenceStopped('The assistant cannot execute a user-role tool.')

    def read(self, resource, record_id):
        return self.tool('get_record', resource=resource, record_id=record_id)

    def rows(self, resource, filters=None):
        rows, cursor, seen = [], None, set()
        while True:
            arguments = {'resource': resource, 'limit': 100}
            if filters is not None: arguments['filters'] = filters
            if cursor: arguments['cursor'] = cursor
            page = self.tool('search_records', **arguments)
            rows.extend(self.read(resource, row['id']) for row in page['records'])
            cursor = page.get('next_cursor')
            if not cursor: return rows
            if cursor in seen: raise ReferenceStopped('Repeated pagination cursor.')
            seen.add(cursor)

    def one(self, resource):
        rows = self.rows(resource)
        if len(rows) != 1: raise ReferenceStopped(f'Expected one public {resource} record.')
        return rows[0]

    def docs(self, *ids):
        for document_id in ('PX-COMMON', 'PX-DATABASE', *ids):
            self.tool('read_document', document_id=document_id)
        self.rows('xp_cases')

    def write(self, operation, **arguments):
        if operation not in self.unlocked:
            self.unlocked[operation] = self.tool('unlock_discoverable_agent_tool', capability_name=operation)
        proposal = self.tool('call_discoverable_agent_tool', capability_name=operation, arguments=arguments)
        if not self.unlocked[operation]['approval_required']:
            return proposal
        for _ in range(3):
            receipt = self.customer('approval', request_id=proposal['id'], operation=operation, arguments=arguments)
            if not isinstance(receipt, dict) or receipt.get('id', receipt.get('request_id')) != proposal['id']:
                raise ReferenceStopped('Approval receipt identifies a different request; terms must be reviewed again.')
            status = receipt.get('status')
            if status in ('DECLINED', 'REVOKED', 'REJECTED'):
                raise ReferenceStopped('Customer declined or revoked this proposal.')
            if status == 'APPROVED':
                # The receipt cannot grant consent; this native action enforces it.
                return self.tool('execute_request', request_id=proposal['id'])
            if status != 'PENDING':
                raise ReferenceStopped('Unknown proposal status; refusing to execute.')
        raise ReferenceStopped('Approval remains pending; no execution or completion recorded.')

    def wait(self):
        before = self.tool('get_clock')['minute']
        receipt = self.customer('portal', tool='wait_for_update', arguments={})
        if not isinstance(receipt, dict) or type(receipt.get('advanced')) is not bool:
            raise ReferenceStopped('Missing actual bank update receipt.')
        after = self.tool('get_clock')['minute']
        self.idle_waits = self.idle_waits + 1 if after <= before else 0
        if self.idle_waits >= 2:
            raise ReferenceStopped('Two bank updates made no clock progress; re-planning is required.')
        return receipt

    def require(self, condition, reason):
        if not condition: raise ReferenceStopped(reason)

    def finish(self, summary):
        self.tool('record_case_outcome', outcome='COMPLETED', summary=summary)
        self.finished = True


class AdaptiveController:
    def __init__(self, task_id):
        from .adaptive_plans import PLANS
        if task_id not in PLANS: raise ValueError('Only the five pilot tasks are supported.')
        self.events, self.answers = queue.Queue(), queue.Queue()
        self.pending = None
        self.serial = 0
        self.state = 'running'
        self.reason = ''
        self.thread = threading.Thread(target=self._run, args=(PLANS[task_id],), daemon=True)
        self.thread.start()

    def _emit(self, event):
        self.events.put(event)
        answer = self.answers.get()
        if isinstance(answer, ReferenceStopped): raise answer
        return answer

    def close(self, reason='Native episode ended before controller completion.'):
        if self.thread.is_alive():
            self.answers.put(ReferenceStopped(reason))
            self.thread.join(timeout=2)

    def _run(self, plan):
        session = PublicSession(self._emit)
        try:
            plan(session)
            self.state = 'completed' if session.finished else 'halted'
            self.reason = 'Public-tool workflow completed.' if session.finished else 'No completion recorded.'
        except Exception as error:
            self.state = 'halted'
            self.reason = str(error) or type(error).__name__
        self.events.put({'kind': 'done'})

    def next(self, request):
        messages = request.get('messages', [])
        if self.pending is not None:
            if self.pending['kind'] == 'tool':
                matches = [m for m in messages if m.get('role') == 'tool' and m.get('tool_call_id') == self.pending['id']]
                if not matches:
                    raise ReferenceStopped('Native request lacks the pending tool receipt.')
                answer = json_value(matches[-1].get('content', ''))
            else:
                matches = [m for m in messages if m.get('role') == 'user']
                if not matches: raise ReferenceStopped('Native request lacks a customer reply.')
                answer = matches[-1].get('content', '')
            self.answers.put(answer)
            self.pending = None
        if self.state != 'running' and self.events.empty():
            return self._final()
        event = self.events.get(timeout=30)
        if event['kind'] == 'done': return self._final()
        self.serial += 1
        event['id'] = f'adaptive-{self.serial}'
        self.pending = event
        if event['kind'] == 'tool':
            return {'tool_calls': [{'id': event['id'], 'type': 'function', 'function': {
                'name': event['tool'], 'arguments': json.dumps(event['arguments'])}}]}
        detail = deepcopy(event['request']); detail['request_token'] = event['id']
        prefix = ('Please review the exact target, amount, fees and terms below. Use your own portal only if they match your requirements. '
                  'You may decline or ask questions. Return the actual portal receipt as JSON {"ok": true, "data": ...}; '
                  'if unavailable, explain or return {"ok": false, "error": ...}. ')
        if detail['kind'] == 'facts':
            prefix = 'Please provide your actual requirements as JSON using these fields; do not infer missing values. '
        if event['attempt']:
            prefix = ('I have not executed the pending action. Here are the exact requested terms/actions for clarification. '
                      'Please return the actual receipt when ready, or decline; I will stop if it cannot be verified. ') + prefix
        return {'content': prefix + '<portal_request>' + json.dumps(detail) + '</portal_request>'}

    def _final(self):
        return {'content': ('The workflow is complete. ' if self.state == 'completed' else 'I stopped without recording completion. ') + self.reason}
