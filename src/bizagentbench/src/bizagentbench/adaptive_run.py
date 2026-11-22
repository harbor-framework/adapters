"""Optional public-API reference runner; packaged only with adaptive test tasks."""
import argparse
import sys
import time
sys.path.insert(0, '/app')
from biz import call
from bizagentbench.adaptive import AdaptiveController

p = argparse.ArgumentParser()
p.add_argument('--task-id', required=True)
args = p.parse_args()
controller = AdaptiveController(args.task_id)
seen = set()
try:
    while True:
        turn = call('/turn')
        if turn['state'] == 'finished': break
        if turn['state'] == 'error': raise RuntimeError(turn['error'])
        if turn['state'] != 'turn' or turn['turn_id'] in seen:
            time.sleep(0.1); continue
        message = controller.next(turn['request'])
        call('/respond', {'turn_id': turn['turn_id'], 'message': message})
        seen.add(turn['turn_id'])
finally:
    controller.close()
