"""Authoring and scripted-customer boundaries, not live-model success tests."""
import ast
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def test_all_fifty_planners_have_no_private_runtime_or_scoring_imports():
    tree=ast.parse((ROOT/'scripts/reference_plans.py').read_text('utf-8-sig'))
    functions={node.name for node in tree.body if isinstance(node,ast.FunctionDef)}
    assert {f'case_{i:03}' for i in range(1,51)} <= functions
    for name in ('reference_plans','reference_tools','build_references','reference_case040','explore_reference'):
        source=(ROOT/'scripts'/f'{name}.py').read_text('utf-8-sig')
        for node in ast.walk(ast.parse(source)):
            if isinstance(node,ast.ImportFrom):
                assert not (node.module or '').startswith('payment.')
            if isinstance(node,ast.Import):
                assert all(not alias.name.startswith('payment.') for alias in node.names)
        assert 'payment/data/private' not in source


def test_fixture_keeps_roles_explicit_approvals_actual_receipts_and_customer_stop():
    spec=importlib.util.spec_from_file_location('reference_fixture',ROOT/'tests/fixtures/reference_provider.py')
    fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
    proposal={'capability_name':'pay','arguments':{'amount_minor':100}}
    trace=[
        {'actor':'assistant','tool':'call_discoverable_agent_tool','arguments':proposal,'response':{'ok':True,'data':{'id':'R1'}}},
        {'actor':'user','tool':'get_my_requests','arguments':{},'response':{'ok':True,'data':[{'id':'R1','status':'PENDING'}]}},
        {'actor':'user','tool':'decide_request','arguments':{'request_id':'R1','decision':'APPROVE'},'response':{'ok':True,'data':{'status':'APPROVED'}}},
        {'actor':'assistant','tool':'execute_request','arguments':{'request_id':'R1'},'response':{'ok':True,'data':{'paid_minor':100}}},
        {'actor':'user','tool':'wait_for_update','arguments':{},'response':{'ok':True,'data':{'minute':2,'advanced':True}}},
        {'actor':'assistant','tool':'record_case_outcome','arguments':{'outcome':'COMPLETED','summary':'Paid once.'},'response':{'ok':True,'data':{}}},
    ]
    plans,messages=fixture.messages_from_trace(trace,'Opening',[{'question':'Fee limit?','answer':'USD 1.'}])
    assistant=list(plans['reference-agent']);user=list(plans['reference-user'])
    assert assistant==messages
    def calls(rows):return [c['function']['name'] for m in rows for c in m.get('tool_calls',[])]
    assert calls(assistant)==['call_discoverable_agent_tool','execute_request','record_case_outcome']
    assert calls(user)==['get_my_requests','decide_request','wait_for_update']
    assert any(json.dumps(proposal) in m.get('content','') for m in assistant)
    assert any('wait/update button once' in m.get('content','') for m in assistant)
    assert any('APPROVED' in m.get('content','') for m in user)
    assert any('"minute": 2' in m.get('content','') for m in user)
    assert user[-1]=={'content':'Thank you. ###STOP###'}
    assert assistant[-1]=={'content':'Paid once.'}
