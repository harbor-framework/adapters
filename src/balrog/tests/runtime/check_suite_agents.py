"""Offline native/HTTP agent equivalence in a pinned Linux game image.

This uses scripted completions and synthetic tokens. It is not model parity.
Run separately for each environment; Docker --network none prevents API access.
Crafter is excluded from exact long-trajectory comparison because the original
game is nondeterministic across fresh worlds; see docs/crafter_scoring_review.md.
"""
import argparse
import json
from pathlib import Path
import tempfile

import test_parity as integration
from runtime_support import PACKAGE


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--environment', choices=('babyai', 'babaisai', 'textworld', 'nle', 'minihack'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    name = 'manifest.json' if args.environment == 'babyai' else args.environment + '_manifest.json'
    case = json.loads((PACKAGE / 'fixtures' / name).read_text())['cases'][0]
    integration.MANIFEST = case['episode']
    reference = case.get('oracle') or case.get('reference') or case.get('native_probe')
    actions = list(reference['actions'])
    # Partial references deliberately continue legally to native termination or
    # native budget; do not pretend the short reference completes the episode.
    if not case.get('oracle'):
        # NetHack's legal esc leaves game time unchanged; the original
        # no_progress_timeout ends the episode naturally after 150 such moves.
        actions += ['esc'] * case['episode']['expected_max_steps']
    test = integration.ParityTest()
    # Keep large per-call checkpoints on the container filesystem; Windows bind
    # mounts make these synthetic long-episode checks unnecessarily expensive.
    test.work = tempfile.TemporaryDirectory()
    test.path = Path(test.work.name)
    test.config = integration.load_config(integration.CONFIG_PATH, integration.SETTINGS)
    try:
        native, verified, calls = test.run_pair(actions)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps({
            'OFFLINE_TEST_ONLY': True, 'real_model_calls': 0,
            'env_name': args.environment, 'task_id': case['episode']['task_id'],
            'status': 'native_http_messages_actions_scores_equal',
            'steps': native['steps'], 'scripted_calls_per_side': len(calls),
            'native_progression': native['native_progression'],
            'verified_progression': verified['progression'],
            'terminated': native['terminated'], 'truncated': native['truncated'],
            'replay_verified': verified['replay_verified'],
            'note': 'Real upstream agent/evaluator and HTTP game service, scripted fake client. No model parity or real token usage.'
        }, indent=2) + '\n')
        print(args.output.read_text())
    finally:
        test.tearDown()


if __name__ == '__main__':
    main()
