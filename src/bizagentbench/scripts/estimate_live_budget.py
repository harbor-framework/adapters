"""Offline planning estimate from cached request lengths; no model or grader imports."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PILOT = ['case_040', 'case_031', 'case_001', 'case_049', 'case_036']
EXTENSION = ['case_021', 'case_014', 'case_006', 'case_007', 'case_002']
PRICES = {'user': {'input': .75, 'output': 4.50},
          'assistant': {'input': 2.50, 'output': 15.00}}


def measure(folder):
    roles = {}
    for role in ('user', 'assistant'):
        files = sorted((folder / 'api_cache' / role).glob('*/request.json.gz'))
        if not files:
            raise ValueError(f'Missing cached requests: {folder}/{role}')
        sizes = []
        hashes = hashlib.sha256()
        for path in files:
            raw = path.read_bytes()
            hashes.update(path.parent.name.encode() + hashlib.sha256(raw).digest())
            request = json.loads(gzip.decompress(raw))
            # Count repeated history and tool schemas for every request. No text is exported.
            payload = {key: request[key] for key in ('messages', 'tools') if key in request}
            sizes.append(len(json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8')))
        proxy = sum(sizes) / 3  # Explicit heuristic, NOT a tokenizer or measured usage.
        output = len(files) * (512 if role == 'user' else 1536)
        base = (proxy * PRICES[role]['input'] + output * PRICES[role]['output']) / 1e6
        # The high scenario triples input and output, then reserves 25% for failed attempts.
        roles[role] = {'requests': len(files), 'serialized_input_bytes': sum(sizes),
                       'max_request_serialized_bytes': max(sizes), 'input_token_proxy': round(proxy),
                       'assumed_billed_output_tokens': output, 'base_usd': round(base, 4),
                       'high_with_retry_reserve_usd': round(base * 3 * 1.25, 4),
                       'cache_manifest_sha256': hashes.hexdigest()}
    return roles


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    selected = json.loads((ROOT / 'validation/scripted-reference-selection.json').read_text())['tasks']
    assert len(selected) == 50 and len({r['task_id'] for r in selected}) == 50
    rows = []
    for row in selected:
        task = row['task_id']
        folder = ROOT / 'validation/adaptive-native-final' / f'{task}__trial0' if task in PILOT else (ROOT / row['native_result']).parent
        rows.append({'task_id': task, 'source': folder.relative_to(ROOT).as_posix(),
                     'trace_kind': 'adaptive_scripted' if task in PILOT else 'linear_scripted',
                     'roles': measure(folder)})

    def stage(name, tasks, roles, repetitions):
        subset = [r for r in rows if r['task_id'] in tasks]
        assert len(subset) == len(tasks)
        factor = 2 * repetitions  # native + Harbor
        lo = sum(r['roles'][role]['base_usd'] for r in subset for role in roles) * factor
        hi = sum(r['roles'][role]['high_with_retry_reserve_usd'] for r in subset for role in roles) * factor
        return {'phase': name, 'tasks': len(tasks), 'sides': 2, 'repetitions_per_side': repetitions,
                'episodes': len(tasks) * factor, 'paid_roles': roles,
                'base_usd': round(lo, 2), 'high_with_retry_reserve_usd': round(hi, 2)}

    all_tasks = [r['task_id'] for r in rows]
    stages = [stage('oracle_pilot5', PILOT, ['user'], 1),
              stage('oracle_extension5', EXTENSION, ['user'], 1),
              stage('oracle_remaining40', [t for t in all_tasks if t not in PILOT + EXTENSION], ['user'], 1),
              stage('oracle_full50_total_including_pilot', all_tasks, ['user'], 1),
              stage('parity_sanity10', PILOT + EXTENSION, ['user', 'assistant'], 1),
              stage('parity_full50_first_round', all_tasks, ['user', 'assistant'], 1),
              stage('parity_full50_additional_two_rounds', all_tasks, ['user', 'assistant'], 2),
              stage('parity_full50_three_rounds_total_excluding_sanity', all_tasks, ['user', 'assistant'], 3)]
    result = {'kind': 'offline_budget_scenarios_not_billing_or_execution_authorization',
              'date_local': '2026-11-21', 'currency': 'USD', 'execution_enabled': False,
              'real_model_calls': 0, 'authorized_spend_usd': 0,
              'candidates': {'user': 'gpt-5.4-mini-2026-03-17', 'assistant': 'gpt-5.4-2026-03-05'},
              'prices_per_million_tokens': PRICES,
              'price_sources': ['https://developers.openai.com/api/docs/models/gpt-5.4-mini',
                                'https://developers.openai.com/api/docs/models/gpt-5.4'],
              'method': {'input_proxy': 'UTF-8 bytes of serialized messages and tools / 3, summed at every request; no cache discount.',
                         'output_assumption_per_request': {'user': 512, 'assistant': 1536},
                         'high_scenario': '3x baseline input and output, then 25% failed-attempt reserve; 3.75x total.',
                         'limitations': ['Not tokenizer counts, confidence intervals, a quote, or guaranteed bounds.',
                                         'Scripted paths do not predict live turn counts, reasoning usage or failures.',
                                         '45 task traces are older linear fixtures; full oracle awaits adaptive coverage.',
                                         'No cache, Batch, promotional or team discount assumed.',
                                         'Taxes, cloud compute, provider markups and long-context surcharges excluded; reprice if applicable.',
                                         'GPT-5.4 long-context pricing applies above 272K input tokens; inspect actual usage before scale-up.',
                                         'Recalibrate with billed input/output/cached/reasoning tokens after the approved pilot.']},
              'stages': stages, 'tasks': rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'stages': stages, 'max_serialized_request_bytes': max(v['max_request_serialized_bytes'] for r in rows for v in r['roles'].values())}, indent=2))


if __name__ == '__main__':
    main()
