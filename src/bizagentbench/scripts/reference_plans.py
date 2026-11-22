"""Authored business flows using exclusively the PublicTools interface.

No private contracts, world snapshots, scoring imports or direct state writes.
The test customer approves exact proposals; this is not LLM consent validation.
"""


def inspect(p, docs, resources):
    p.docs(*docs)
    for resource in resources:
        p.rows(resource)


def manager(p, operation, record_id):
    def act(action, reference='', amount_minor=0):
        return p.write(operation, record_id=record_id, action=action, reference=reference, amount_minor=amount_minor)
    return act


def desk_docs(p, *ids):
    for document_id in ('PAYMENT-CATALOG', 'DB-index', *ids):
        document = p.call('assistant', 'read_document', document_id=document_id)


def case_001(p):
    p.customer_facts('Please confirm the supplier amounts, retained balances, funding permissions and fee limits for both matters.',
        'The suppliers need EUR 1,000 and GBP 500. Keep EUR 100 and USD 10 in the Jasmine wallet. I cannot add money or authorize unrelated-account transfers. Currency route fees may total USD 2.50; separate delivery fees are acceptable. Correct existing Cypress tax payments and bank references wherever still possible without sending tax again. The authority fee account is reserved; bank correction may cost USD 2 from its designated fee wallet.')
    desk_docs(p, 'DESK-fx', 'DESK-tax', 'DESK-collateral', 'DESK-protocol')
    obligations = p.rows('currency_obligations')
    wallet = next(x for x in p.rows('desk_accounts') if 'EUR' in x['wallet'])
    routes = p.rows('fx_routes')
    for obligation in obligations:
        # Customer's disclosed retained-funds requirement: EUR 100 and USD 10.
        retained = 10000 if obligation['currency'] == 'EUR' else 0
        needed = obligation['amount_minor'] + obligation['delivery_fee_minor'] + retained - wallet['wallet'].get(obligation['currency'], 0)
        candidates = []
        for route in routes:
            if route['source_currency'] != 'USD' or route['target_currency'] != obligation['currency'] or route['review_status'] != 'FINAL':
                continue
            for amount in range(route['minimum_minor'], wallet['wallet']['USD']+1):
                value = amount
                for segment in route['segments']:
                    value = value*segment['numerator']//segment['denominator']
                if value >= needed:
                    candidates.append((amount+route['fee_minor'], amount, route))
                    break
        _, amount, route = min(candidates, key=lambda x:x[0])
        quote = p.write('inspect_multicurrency_quote', account_id=wallet['id'], route_id=route['id'], source_minor=amount)
        print('FXQUOTE', quote, flush=True)
        p.write('propose_fx_execution', quote_id=quote['id'])
    files = p.call('user', 'list_my_files')
    certificates = {}
    for f in files:
        if 'current' in f['label']:
            uploaded = p.call('user', 'upload_file', file_id=f['id'], target_id=f['target_id'], purpose=f['purpose'])
            certificates[f['target_id']] = p.write('assess_evidence', submission_id=uploaded['id'])
    while p.call('assistant','get_clock')['minute'] < 5:
        p.wait()
    for obligation in obligations:
        p.write('propose_currency_payment', obligation_id=obligation['id'], account_id=wallet['id'], net_minor=obligation['amount_minor'])
    transfers = p.rows('tax_transfers')
    amendable = next(t for t in transfers if t['amend_until_minute'] >= p.call('assistant','get_clock')['minute'])
    routes = p.rows('reserve_routes')
    p.rows('business_documents')
    route = min((r for r in routes if r['destination_account_id']==amendable['amendment_fee_account_id'] and r['net_minor']>=amendable['amendment_fee_minor'] and r['settlement_delay']==0), key=lambda r:r['fee_minor'])
    p.write('propose_reserve_disbursement', route_id=route['id'])
    cert = certificates[amendable['id']]['contents']
    p.write('propose_bank_message_amendment', transfer_id=amendable['id'], tax_period=cert['declared_bank_period'], tax_reference=cert['tax_reference'])
    initial_posting = p.call('assistant','get_clock')['minute']+amendable['amendment_delay']+amendable['allocation_delay']
    allocated = set()
    for _ in range(25):
        for f in p.call('user','list_my_files'):
            if 'current' in f['label'] and f['target_id'] not in certificates:
                uploaded = p.call('user','upload_file', file_id=f['id'], target_id=f['target_id'], purpose=f['purpose'])
                certificates[f['target_id']] = p.write('assess_evidence', submission_id=uploaded['id'])
        for transfer in transfers:
            key = transfer['id']
            if key in certificates and key not in allocated and (key != amendable['id'] or p.call('assistant','get_clock')['minute']>=initial_posting):
                certificate = certificates[key]
                p.write('propose_tax_allocation', transfer_id=key, allocations=certificate['contents']['allocations'], submission_id=certificate['id'])
                allocated.add(key)
        if len(allocated)==len(transfers):
            break
        p.wait()
    p.wait()
    p.rows('tax_allocations')
    periods = p.rows('tax_periods')
    while p.call('assistant','get_clock')['minute'] < max(x['filing_cutoff_minute'] for x in periods):
        p.wait()
    assert all(x.get('filing_status') == 'DISCHARGED' for x in p.rows('tax_periods'))
    p.finish('Delivered both supplier currencies with actual settled funds, funded the timely bank reference amendment from the authorized reserve, and reconciled both existing tax transfers to their current certificate allocations without paying tax twice.')


def case_002(p):
    from itertools import combinations, product
    p.customer_facts('Please confirm the storefront scope, account limits, fixed future billing destinations and funding preferences.',
        'Connect all nine Elder storefronts and retain the existing collection account. Open at most three new accounts for at most USD 30 issuance fees. Close Indigo old operating and cancel Legacy within an hour, but keep Commerce billed to main operating and Analytics billed to second site. Transfer only from the old account, with its final remainder to main. No new money or unrelated transfers. Choose the lowest total drawing fees; unnecessary extra cash is not a benefit.')
    desk_docs(p,'DESK-rails','DESK-exit','DESK-collateral')
    docs = p.rows('business_documents')
    profiles = p.rows('rail_profiles')
    sites = p.rows('rail_sites')
    accounts = p.rows('desk_accounts')
    existing = next(a for a in accounts if a.get('profile_id'))
    terms = {a['id']:next(d['body'] for d in docs if d['reference']==a['commercial_reference'] and d['kind']=='collection_product_terms') for a in profiles}
    covered = set(terms[existing['profile_id']]['settlement_markets'])
    required = {s['market'] for s in sites}-covered
    eligible = [a for a in profiles if terms[a['id']]['new_issuance']]
    combos = [cs for count in range(1,4) for cs in combinations(eligible,count) if required<=set().union(*(set(terms[a['id']]['settlement_markets']) for a in cs)) and sum(a['issuance_fee_minor'] for a in cs)<=3000]
    chosen = min(combos,key=lambda cs:sum(a['issuance_fee_minor'] for a in cs))
    fee_account = chosen[0]['billing_account_id']
    old = next(a for a in accounts if a.get('name')=='Indigo old operating account')
    main = next(a for a in accounts if a.get('name')=='Indigo main operating account')
    second = next(a for a in accounts if a.get('name')=='Indigo second site account')
    routes = p.rows('reserve_routes')
    reserve = p.read('desk_accounts',routes[0]['reserve_account_id'])['wallet']['USD']
    # Both contractual draws are needed. Evaluate the shared reserve jointly.
    pairs = [(a,b) for a,b in product(routes,routes) if a['destination_account_id']==fee_account and b['destination_account_id']==old['id'] and a['net_minor']>=sum(x['issuance_fee_minor'] for x in chosen) and a['debit_minor']+b['debit_minor']<=reserve]
    draw1,draw2 = min(pairs,key=lambda pair:sum(r['fee_minor'] for r in pair))
    p.write('propose_reserve_disbursement',route_id=draw1['id'])
    opened = {existing['profile_id']:existing}
    for profile in chosen:
        opened[profile['id']] = p.write('propose_desk_account_opening',profile_id=profile['id'],entity_id=sites[0]['entity_id'])
    services = p.rows('desk_services')
    for s in services:
        if 'Legacy' in s['name']:
            p.write('propose_service_termination',service_id=s['id'])
        else:
            destination = second if 'Analytics' in s['name'] else main
            p.write('propose_billing_migration',service_id=s['id'],account_id=destination['id'])
    bindings, tested, funded = {}, set(), False
    while True:
        sites = p.rows('rail_sites')
        for site in sites:
            if site['id'] not in bindings and site['sender_configuration']=='FINAL':
                profile_id = next(k for k in opened if site['market'] in terms[k]['settlement_markets'] and site['sender_rail'] in terms[k]['payment_networks'])
                bindings[site['id']] = p.write('propose_rail_binding',site_id=site['id'],account_id=opened[profile_id]['id'],rail=site['sender_rail'])
        for binding in bindings.values():
            current = p.read('rail_bindings',binding['id'])
            if current['status']=='ACCEPTED' and current['id'] not in tested:
                p.write('propose_payout_validation',binding_id=current['id'])
                tested.add(current['id'])
        if not funded and any(s['market']=='CA' and s['status']=='COLLECTING' for s in sites):
            p.write('propose_reserve_disbursement',route_id=draw2['id'])
            funded = True
        bills = p.rows('billing_instances')
        if funded:
            for account in (main,second):
                pending = sum(b['amount_minor'] for b in bills if b['account_id']==account['id'] and b['status']=='ACCEPTED')
                balance = p.read('desk_accounts',account['id'])['wallet']['USD']
                if pending>balance:
                    p.write('propose_account_sweep',source_account_id=old['id'],destination_account_id=account['id'],amount_minor=pending-balance)
        update = p.wait()
        if not update['advanced']:
            break
    assert all(s['status']=='COLLECTING' for s in p.rows('rail_sites'))
    assert all(b['status'] not in ('ACCEPTED','RETURN_PENDING','FAILED') for b in p.rows('billing_instances'))
    balance = p.read('desk_accounts',old['id'])['wallet']['USD']
    if balance:
        p.write('propose_account_sweep',source_account_id=old['id'],destination_account_id=main['id'],amount_minor=balance)
    p.write('propose_desk_account_close',account_id=old['id'])
    p.finish('Connected and test-settled all nine stores using three permitted new profiles and the existing account, selected jointly feasible reserve drawings at minimum total fee, preserved the fixed subscription billing destinations and paid accepted bills before retiring the old account and sweeping its remainder.')


def case_003(p):
    from fractions import Fraction
    p.customer_facts('Please confirm the affected period, company application, review fee limit and available funding.',
        'Finish Acacia September receipt reconciliation and make the Durian Trading Limited company account ready. I control Durian and can provide the actual registry and identity documents. The total application review budget is USD 50. No extra money or transfers from unrelated accounts are authorized.')
    desk_docs(p,'DESK-reconciliation','DESK-onboarding','DESK-collateral')
    remittances = p.rows('remittances')
    docs = p.rows('business_documents')
    for r in remittances:
        notice = next(d['body'] for d in docs if d['reference']==r['commercial_reference'] and d['kind']=='payer_dispatch_notice')
        if notice['dispatched_revision']>r['revision']:
            p.write('propose_remittance_advice',remittance_id=r['id'])
    app = p.one('onboarding_applications')
    while p.call('assistant','get_clock')['minute']<app['published_registry_review_minute']:
        p.wait()
    invoices = [r for r in p.rows('trade_invoices') if r['portfolio_id']==remittances[0]['portfolio_id']]
    advice = p.rows('remittance_advice')
    chosen = {r['id']:max((a for a in advice if a['remittance_id']==r['id']),key=lambda a:(a['revision'],a.get('received_minute',-1))) for r in remittances}
    maps = {r['id']:{} for r in remittances}
    remaining_i = {i['id']:i['amount_minor'] for i in invoices}
    remaining_r = {r['id']:r['gross_minor'] for r in remittances}
    allowed = {}
    for r in remittances:
        terms = next(d['body'] for d in docs if d['kind']=='buyer_payment_terms' and d['reference']==r['commercial_reference'])
        allowed[r['id']] = [i['id'] for i in invoices if i['buyer_name']==terms['buyer_name'] and i['purchase_order'] in terms['purchase_orders'] and i['invoice_date'].startswith(terms['invoice_month'])]
        for fixed in chosen[r['id']]['payer_letter']['designations']:
            invoice = next(i for i in invoices if i['purchase_order']==fixed['purchase_order'] and i['buyer_name']==fixed['buyer_name'] and i['invoice_date'].startswith(fixed['invoice_month']))
            maps[r['id']][invoice['id']] = fixed['amount_minor']
            remaining_i[invoice['id']] -= fixed['amount_minor']
            remaining_r[r['id']] -= fixed['amount_minor']
            allowed[r['id']].remove(invoice['id'])
    # Integral bipartite maximum flow reconciles all permitted residual scope.
    capacity = {}
    def edge(a,b,n):
        capacity[a,b]=n
        capacity[b,a]=0
    for r,n in remaining_r.items():
        edge('SOURCE',r,n)
        for i in allowed[r]:edge(r,i,n)
    for i,n in remaining_i.items():edge(i,'SINK',n)
    while True:
        prev,queue = {'SOURCE':None},['SOURCE']
        for a in queue:
            for (x,b),n in list(capacity.items()):
                if x==a and n>0 and b not in prev:
                    prev[b]=a;queue.append(b)
            if 'SINK' in prev:break
        if 'SINK' not in prev:break
        b,n='SINK',10**12
        while prev[b] is not None:n=min(n,capacity[prev[b],b]);b=prev[b]
        b='SINK'
        while prev[b] is not None:
            a=prev[b];capacity[a,b]-=n;capacity[b,a]+=n;b=a
    assert all(capacity['SOURCE',r]==0 for r in remaining_r)
    assert all(capacity[i,'SINK']==0 for i in remaining_i)
    for r in remittances:
        for i in allowed[r['id']]:
            amount=capacity[i,r['id']]
            if amount:maps[r['id']][i]=amount
        p.write('propose_invoice_allocation',remittance_id=r['id'],advice_id=chosen[r['id']]['id'],allocations=maps[r['id']])
    p.write('propose_receivable_close',portfolio_id=remittances[0]['portfolio_id'])
    routes = p.rows('reserve_routes')
    minute = p.call('assistant','get_clock')['minute']
    route = min((r for r in routes if r['net_minor']>=app['submission_fee_minor'] and minute+r['settlement_delay']+app['review_delay']<=app['review_due_minute']),key=lambda r:r['fee_minor'])
    p.write('propose_reserve_disbursement',route_id=route['id'])
    profiles = p.rows('company_profiles')
    edges = p.rows('ownership_edges')
    def ownership(subject,target):
        return sum((Fraction(e['ownership_bp'],10000)*(1 if e['owner_id']==subject else ownership(subject,e['owner_id'])) for e in edges if e['owned_id']==target),Fraction(0))
    required = {r['id'] for r in profiles if r['kind']=='PERSON' and ownership(r['id'],app['entity_id'])>=Fraction(app['ownership_threshold_bp'],10000)}|set(app['direct_controllers'])|{app['entity_id']}
    expected = {r['id']:r.get('published_next_version',r['version']) if r.get('published_revision_minute',10**9)<=minute+app['review_delay'] else r['version'] for r in profiles}
    submissions = {}
    for f in p.call('user','list_my_files'):
        if f['target_id']!=app['id']:continue
        u=p.call('user','upload_file',file_id=f['id'],target_id=f['target_id'],purpose=f['purpose'])
        assessed=p.write('assess_evidence',submission_id=u['id'])
        if assessed['status']=='APPROVED' and assessed['contents'].get('valid_until',10**9)>=minute+app['review_delay']:
            for subject,claim in assessed['contents'].get('claims',{}).items():
                kind='registry' if subject==app['entity_id'] else 'identity'
                if subject in required and claim['version']==expected[subject] and claim['kind']==kind:
                    submissions[subject]=assessed['id']
    assert set(submissions)==required
    bundle=p.write('propose_onboarding_bundle',application_id=app['id'],submission_ids={key:True for key in set(submissions.values())})
    p.write('propose_onboarding_submission',bundle_id=bundle['id'])
    while p.read('onboarding_applications',app['id'])['status']!='APPROVED':p.wait()
    p.finish('Reconciled every September gross receipt and invoice using current payer advice and scoped integral allocations, retained merchant fees separately, closed the receivable file, funded the timely review and supplied the exact aggregate beneficial owners and controller with evidence valid at institutional review.')


def case_004(p):
    p.customer_facts('Please confirm the outstanding payments, partial-payment permission and supplier bank changes.',
        'Complete the listed payroll, supplier and other business payments; payments in parts are fine if fully received on time. Reconcile the previously submitted Birch payments before sending more. Birch Office Supplies sent a new bank letter, and I can upload the actual restriction and assignee correspondence. No extra funding or unrelated-account transfers are authorized.')
    desk_docs(p,'DESK-restrictions','DESK-batches','DESK-collateral')
    docs=p.rows('business_documents')
    instructions=p.rows('purpose_instructions')
    attempts=p.rows('submission_attempts')
    for attempt in attempts:p.write('propose_attempt_trace',attempt_id=attempt['id'])
    traced_at=max(a['trace_delay'] for a in attempts)
    purposes={'PAYROLL':'employee payroll','VENDOR':'supplier invoices','CUSTOMS':'customs duties','LOGISTICS':'freight services','INSURANCE':'insurance premiums'}
    paid={r['id']:0 for r in instructions}
    uploaded,applied=set(),set()
    evidence=[]
    batch_done=False
    batch_settle=None
    while True:
        minute=p.call('assistant','get_clock')['minute']
        for f in p.call('user','list_my_files'):
            if f['id'] in uploaded or 'former' in f['label']:continue
            u=p.call('user','upload_file',file_id=f['id'],target_id=f['target_id'],purpose=f['purpose'])
            e=p.write('assess_evidence',submission_id=u['id'])
            uploaded.add(f['id'])
            if e['status']=='APPROVED':evidence.append(e)
        for e in evidence:
            if e['id'] in applied:continue
            if e['purpose']=='bank_details':
                p.write('propose_batch_recipient_update',item_id=e['target_id'],submission_id=e['id'])
            elif e['purpose']=='restriction':
                p.write('propose_restriction_review',restriction_id=e['target_id'],submission_id=e['id'])
            elif e['purpose']=='rights_release':
                right=p.read('receivable_rights',e['target_id'])
                required=right.get('release_requires')
                if required and paid[required['instruction_id']]<required['paid_minor']:continue
                p.write('propose_receivable_release',right_id=e['target_id'],submission_id=e['id'])
            applied.add(e['id'])
        restrictions=p.rows('fund_restrictions')+p.rows('receivable_rights')
        blocked=set().union(*(set(r['lot_ids'])-set(r['released_lot_ids']) for r in restrictions))
        lots=p.rows('restricted_lots')
        for instruction in sorted(instructions,key=lambda r:r['due_minute']):
            due=instruction['amount_minor']-paid[instruction['id']]
            allocations={}
            candidates=[]
            for lot in lots:
                assignment=next(d['body']['permitted_expenditure'] for d in docs if d['kind']=='proceeds_assignment' and d['reference']==lot['commercial_reference'])
                if lot['id'] not in blocked and lot['remaining_minor']>0 and purposes[instruction['purpose']] in assignment and instruction['purpose'] in lot['bank_permitted_purposes']:
                    candidates.append((len(assignment),lot))
            for _,lot in sorted(candidates,key=lambda row:row[0]):
                n=min(due,lot['remaining_minor'])
                if n:allocations[lot['id']]=n;lot['remaining_minor']-=n;due-=n
            if allocations:
                p.write('propose_purpose_payment',instruction_id=instruction['id'],allocations=allocations)
                paid[instruction['id']]+=sum(allocations.values())
        # Newly settled prerequisites can be lodged before advancing time.
        for e in evidence:
            if e['id'] not in applied and e['purpose']=='rights_release':
                right=p.read('receivable_rights',e['target_id']);required=right.get('release_requires')
                if not required or paid[required['instruction_id']]>=required['paid_minor']:
                    p.write('propose_receivable_release',right_id=e['target_id'],submission_id=e['id']);applied.add(e['id'])
        if minute>=traced_at and not batch_done:
            items=[r for r in p.rows('payment_batch_items') if r['status']!='VOID']
            receipts=p.rows('bank_receipts')
            actual={}
            for r in receipts:
                if r['status']=='SETTLED':actual[r['attempt_id']]=r
            residual={i['id']:i['amount_minor']-sum(r['amount_minor'] for r in actual.values() if r['item_id']==i['id']) for i in items}
            account=p.read('desk_accounts',items[0]['account_id'])
            deficit=sum(residual.values())-account['wallet']['USD']
            routes=p.rows('reserve_routes')
            if deficit>0 and all(r['status']=='AVAILABLE' for r in routes):
                route=min((r for r in routes if not r['pending_assessment'] and r['net_minor']>=deficit),key=lambda r:r['fee_minor'])
                p.write('propose_reserve_disbursement',route_id=route['id'])
                account=p.read('desk_accounts',items[0]['account_id'])
            if account['wallet']['USD']>=sum(residual.values()):
                for item in items:
                    if residual[item['id']]>0:
                        p.write('propose_batch_residual_payment',item_id=item['id'],bank_version=item['bank_version'],submission_key='reconciled-residual-'+item['id'],amount_minor=residual[item['id']])
                batch_done=True
                batch_settle=minute+max(i['settlement_delay'] for i in items)
        if batch_done and minute>=batch_settle and all(paid[i['id']]==i['amount_minor'] for i in instructions):break
        update=p.wait()
        assert update['advanced'],'Required release or payment result is still absent'
    p.rows('bank_receipts')
    p.finish('Resolved each overlapping restriction and assignment independently, paid from commercially designated proceeds in prerequisite order, reconciled unique actual bank acceptances before paying only Birch residuals to current recipients, and used the assessed reserve terms without duplicate or void-item payments.')


def case_005(p):
    p.customer_facts('Please confirm who may pay each company invoice, dispute permissions and funding limits.',
        'Only our group treasurer may pay, and each company must pay its own bills with its own money. No local accounts staff, cross-company payment or unrelated transfer is authorized. I can provide available signed delegations and the actual Gardenia delivery statement. Recover the missing goods within an hour, with at most USD 5 dispute filing fees. I cannot add new money.')
    desk_docs(p,'DESK-treasury','DESK-disputes','DESK-collateral')
    docs = p.rows('business_documents')
    entities = p.rows('entities')
    accounts = p.rows('desk_accounts')
    obligations = p.rows('treasury_obligations')
    case = p.one('card_loss_cases')
    losses = p.rows('loss_components')
    evidence = None
    paid, uploaded = set(),set()
    dispute = None
    finalized = False
    while True:
        minute = p.call('assistant','get_clock')['minute']
        for f in p.call('user','list_my_files'):
            if f['id'] in uploaded:continue
            u=p.call('user','upload_file',file_id=f['id'],target_id=f['target_id'],purpose=f['purpose'])
            assessed=p.write('assess_evidence',submission_id=u['id'])
            uploaded.add(f['id'])
            if assessed['status']=='APPROVED':
                if f['purpose']=='delivery':evidence=assessed
                else:p.write('propose_treasury_mandate',mandate_id=f['target_id'],submission_id=assessed['id'])
        mandates = p.rows('treasury_mandates')
        choices = {}
        for bill in obligations:
            if bill['id'] in paid:continue
            invoice = next(d['body'] for d in docs if d['reference']==bill['commercial_reference'] and d['kind']=='supplier_invoice')
            owner = next(e for e in entities if e['registration_number']==invoice['bill_to_registration'])
            account = next(a for a in accounts if a['entity_id']==owner['id'] and a.get('business_area')=='treasury')
            options = [(m,account) for m in mandates if m['status']=='EFFECTIVE' and m['payer_entity']==owner['id'] and m['executor_name']=='Group treasurer' and bill['beneficiary_id'] in m['beneficiaries'] and bill['purpose'] in m['purposes'] and m['valid_from']<=minute<=m['valid_until']]
            if options:choices[bill['id']]=(bill,options)
        def assign(remaining,used,plan):
            if not remaining:return plan
            bill,options=remaining[0]
            for m,a in options:
                # Current public mandate capacity plus the planned batch.
                available=m['limit_minor']-m.get('used_minor',0)-used.get(m['id'],0)
                if available>=bill['amount_minor']:
                    found=assign(remaining[1:],{**used,m['id']:used.get(m['id'],0)+bill['amount_minor']},plan+[(bill,m,a)])
                    if found is not None:return found
            return None
        plan=assign(list(choices.values()),{},[])
        assert plan is not None
        for bill,m,a in plan:
            p.write('propose_treasury_payment',obligation_id=bill['id'],account_id=a['id'],mandate_id=m['id'],executor_id=m['executor_id'],amount_minor=bill['amount_minor'])
            paid.add(bill['id'])
        if dispute is None:
            routes = p.rows('reserve_routes')
            ready=[r for r in routes if not r.get('pending_assessment') and r['net_minor']>=case['filing_fee_minor'] and minute+r['settlement_delay']<=case['filing_deadline_minute']]
            if ready and all(r['status']=='AVAILABLE' for r in routes):
                p.write('propose_reserve_disbursement',route_id=min(ready,key=lambda r:r['fee_minor'])['id'])
            if p.read('desk_accounts',case['billing_account_id'])['wallet']['USD']>=case['filing_fee_minor']:
                # Register every evidenced loss component before the fixed window,
                # including those whose current compensation may be withdrawn.
                claims={}
                for loss in losses:
                    receipt=next(d['body'] for d in docs if d['reference']==loss['commercial_reference'] and d['kind']=='warehouse_receipt')
                    amount=(receipt['ordered_units']-receipt['accepted_units'])*receipt['unit_price_minor']
                    if amount:claims[loss['id']]=amount
                dispute=p.write('propose_card_dispute',case_id=case['id'],claims=claims,submission_id=evidence['id'])
        entries=p.rows('compensation_entries')
        last_update=max([case['review_minute']]+[u['minute'] for r in entries for u in r.get('published_status_updates',[])])
        if dispute and not finalized and minute>=last_update:
            claims={}
            for loss in losses:
                receipt=next(d['body'] for d in docs if d['reference']==loss['commercial_reference'] and d['kind']=='warehouse_receipt')
                value=(receipt['ordered_units']-receipt['accepted_units'])*receipt['unit_price_minor']
                compensated=sum(r['amount_minor'] for r in entries if r['shipment_reference']==loss['delivery_reference'] and r['status']=='SETTLED')
                if value>compensated:claims[loss['id']]=value-compensated
            p.write('propose_dispute_adjustment',dispute_id=dispute['id'],claims=claims)
            p.write('propose_dispute_finalization',dispute_id=dispute['id'])
            finalized=True
        if finalized and len(paid)==len(obligations) and minute>=last_update+case['settlement_delay']:break
        update=p.wait()
        assert update['advanced'], 'Waiting for missing actual business outcome'
    p.finish('Paid every supplier from the commercially responsible company using only the effective group treasurer mandate and feasible cumulative capacities, funded one timely dispute registration, preserved all potentially uncompensated components, and finalized exact net losses only after all actual refund corrections.')


def service_context(p, *documents):
    desk_docs(p, 'TRADE-common', *documents)
    cases = p.rows('service_cases')
    for link in p.rows('link_contracts'):
        p.call('assistant', 'read_document', document_id=link['public_rule_document'])
        if link.get('process_rule_document'):
            p.call('assistant', 'read_document', document_id=link['process_rule_document'])
    return {c['kind']:c for c in cases}


def service_rows(p, case_id):
    return p.rows('service_records', {'case_id':case_id})


def service_action(p, operation, case_id, action, **data):
    return p.write(operation, case_id=case_id, action=action, data=data)


def joint_context(p):
    p.call('assistant','read_document',document_id='JOINT-CASH-delivery')
    agreement = p.one('joint_agreements')
    sources = p.rows('joint_sources')
    initial = {}
    for case_id,capital in agreement['capital_by_case'].items():
        earmarked = sum(s['balance_minor'] for s in sources if s['permitted_case_ids']==[case_id])
        initial[case_id] = capital-agreement['initial_operating_by_case'][case_id]-earmarked
    return agreement, initial


def joint_deliver(p, agreement, case_id, allocations):
    if not allocations:
        return
    route = min((r for r in p.rows('joint_routes') if r['case_id']==case_id and r['status']=='AVAILABLE'),key=lambda r:r['fee_minor'])
    p.write('propose_joint_capital_delivery',agreement_id=agreement['id'],case_id=case_id,route_id=route['id'],allocations=allocations,terms_version=route['terms_version'])


def joint_initial(p, agreement, initial, case_id):
    if initial[case_id]:
        joint_deliver(p,agreement,case_id,{agreement['fee_source_id']:initial[case_id]})


def joint_flush(p, agreement):
    for source in p.rows('joint_sources'):
        if len(source['permitted_case_ids'])==1 and source['status']=='AVAILABLE' and source['balance_minor']>0:
            joint_deliver(p,agreement,source['permitted_case_ids'][0],{source['id']:source['balance_minor']})


def collateral_options(loans, assets, increment):
    options=[]
    for loan in loans:
        eligible=[i for i,a in enumerate(assets) if a['security_class'] in loan['accepted_classes'] and a['owner']==loan['borrower'] and a['currency']==loan['currency']]
        choices=[]
        for subset in range(1<<len(eligible)):
            mask=0;issuers={}
            for j,i in enumerate(eligible):
                if subset&(1<<j):
                    a=assets[i];mask|=1<<i
                    issuers[a['issuer']]=issuers.get(a['issuer'],0)+a['face_minor']*(10000-a['haircut_bp'])//10000
            cover=sum(min(value,loan['issuer_caps_minor'].get(issuer,value)) for issuer,value in issuers.items())
            repay=(max(0,loan['debt_minor']-cover)+increment-1)//increment*increment
            if repay<=loan['debt_minor']:choices.append((mask,repay,loan['repayment_fee_minor'] if repay else 0))
        options.append(choices)
    return options


def collateral_policy(loans, assets, terms, early_budget, total_budget):
    from functools import lru_cache
    pending=next((a for a in assets if a['status']=='PENDING'),None)
    scenarios=pending['possible_settlement_values_minor'] if pending else [None]
    solutions=[]
    for value in scenarios:
        valued=[{**a,'face_minor':value} if pending and a['id']==pending['id'] else a for a in assets]
        options=collateral_options(loans,valued,terms['repayment_increment_minor'])
        @lru_cache(None)
        def suffix(index,used,fee_room):
            if index==len(loans):return (0,0,())
            best=None
            for mask,repay,fee in options[index]:
                if mask&used or fee>fee_room:continue
                tail=suffix(index+1,used|mask,fee_room-fee)
                if tail is None:continue
                candidate=(repay+tail[0],fee+tail[1],((mask,repay,fee),)+tail[2])
                if best is None or candidate[:2]<best[:2]:best=candidate
            return best
        candidates={}
        for mask,repay,fee in options[0]:
            if repay+fee>early_budget or any(mask&(1<<i) and a['status']!='SETTLED' for i,a in enumerate(assets)):continue
            tail=suffix(1,mask,terms['repayment_fee_cap_minor']-fee)
            if tail is not None and repay+fee+tail[0]+tail[1]<=total_budget:
                candidates[mask]=(repay+tail[0],fee+tail[1],((mask,repay,fee),)+tail[2])
        optimum=min(v[:2] for v in candidates.values())
        solutions.append({m:v for m,v in candidates.items() if v[:2]==optimum})
    common=set.intersection(*(set(s) for s in solutions))
    assert common,'No common first delivery preserving the public-scenario optimum'
    first=min(common,key=lambda mask:solutions[0][mask][2][0][1])
    return first,solutions[0][first][2]


def case_006(p):
    p.customer_facts('Please confirm collateral delivery, repayment priorities, reserves and shared-capital permissions.',
        'Deliver the ordered securities on time, preserve protected collateral and continuous loan cover, pay the supplier and scheduled debit and retain USD 100. Minimize principal repayment, then servicing fees, within the USD 15 servicing-fee cap. Pay only actual shipments, pay the courier and release unused holds while retaining USD 50. No extra or cross-service funds. Delivery fees may total USD 5 with USD 4 uncommitted; deliver final earmarks to their own wallets.')
    cases=service_context(p,'DIVERSE-dated_collateral','PAYMENT-payment_split_capture')
    primary=cases['dated_collateral']['id'];secondary=cases['payment_split_capture']['id']
    agreement,initial=joint_context(p)
    joint_initial(p,agreement,initial,secondary);shipment_start(p,secondary)
    joint_initial(p,agreement,initial,primary)
    rows=service_rows(p,primary)
    source=next(r for r in rows if r['kind']=='external_correspondence')
    p.write('propose_service_inquiry',case_id=primary,record_id=source['id']);p.wait()
    terms=p.read('service_records',source['id'])['receipt']
    deliveries=sorted((r for r in rows if r['kind']=='asset' and r['delivery_order']),key=lambda r:r['delivery_order']['due_minute'])
    loans=[next(r for r in rows if r['kind']=='loan' and r['reference']==a['pledged_to']) for a in deliveries]
    assets=[r for r in rows if r['kind']=='asset' and not r['protected'] and not r['delivery_order'] and r['eligible_through']>=terms['scheduled_debit_minute'] and any(r['owner']==loan['borrower'] and r['currency']==loan['currency'] and r['security_class'] in loan['accepted_classes'] for loan in loans)]
    bill=next(r for r in rows if r['kind']=='bill')
    cash=p.read('service_cases',primary)['cash_minor']
    early_budget=cash-bill['amount_minor']-terms['minimum_cash_reserve_minor']
    total_budget=agreement['capital_by_case'][primary]-bill['amount_minor']-terms['scheduled_debit_minor']-terms['minimum_cash_reserve_minor']
    first,plan=collateral_policy(loans,assets,terms,early_budget,total_budget)
    def implement(index,choice):
        mask,repay,_=choice;loan=loans[index]
        for i,asset in enumerate(assets):
            if mask&(1<<i):service_action(p,'propose_dated_collateral',primary,'pledge',record_id=asset['id'],loan_id=loan['id'])
        if repay:service_action(p,'propose_dated_collateral',primary,'repay',record_id=loan['id'],amount_minor=repay)
        service_action(p,'propose_dated_collateral',primary,'release',record_id=deliveries[index]['id'])
    implement(0,plan[0])
    service_action(p,'propose_dated_collateral',primary,'pay_bill',record_id=bill['id'],amount_minor=bill['amount_minor'])
    joint_flush(p,agreement)
    p.wait();shipment_complete_capture(p,secondary)
    p.wait();joint_flush(p,agreement)
    # The common early allocation stays fixed; optimize the remaining loans
    # using only the now-settled custodian value.
    current={r['id']:r for r in service_rows(p,primary)}
    actual=[current[a['id']] for a in assets]
    from functools import lru_cache
    options=collateral_options(loans,actual,terms['repayment_increment_minor'])
    @lru_cache(None)
    def remaining(index,used,fees):
        if index==len(loans):return (0,0,())
        best=None
        for mask,repay,fee in options[index]:
            if mask&used or fee>fees:continue
            tail=remaining(index+1,used|mask,fees-fee)
            if tail is None:continue
            candidate=(repay+tail[0],fee+tail[1],((mask,repay,fee),)+tail[2])
            if best is None or candidate[:2]<best[:2]:best=candidate
        return best
    final=remaining(1,first,terms['repayment_fee_cap_minor']-plan[0][2])
    for index,choice in enumerate(final[2],1):implement(index,choice)
    while p.call('assistant','get_clock')['minute']<terms['scheduled_debit_minute']:assert p.wait()['advanced']
    joint_flush(p,agreement)
    p.finish('Computed the minimum total repayment then servicing fees under ownership, currency, whole-security eligibility and per-issuer caps; used an early allocation optimal across every published pending-custody outcome, completed later substitutions after actual custody and earned capital, and preserved protected cover, deadlines, scheduled debit and both wallet reserves.')


def case_007(p):
    from datetime import datetime,timedelta,time
    from zoneinfo import ZoneInfo
    p.customer_facts('Please confirm documentary deliveries, foreign suppliers and cash permissions.',
        'Pay the actual remaining import obligations to the currently entitled beneficiaries, deliver each shipment to its agreed depot on time and recover temporary guarantee collateral. Complete both overseas supplier payments by their actual local deadlines using current quotes and permitted route fees. No new or cross-service funds. Capital delivery fees may total USD 5 with USD 4 uncommitted; deliver final earmarks to their designated wallets.')
    cases=service_context(p,'DIVERSE-documentary_imports','PAYMENT-payment_cross_calendar_delivery')
    primary=cases['documentary_imports']['id'];secondary=cases['payment_cross_calendar_delivery']['id']
    agreement,initial=joint_context(p)
    joint_initial(p,agreement,initial,secondary)
    rows=service_rows(p,secondary)
    calendar=next(r for r in rows if r['kind']=='calendar_terms')
    invoices=[r for r in rows if r['kind']=='calendar_invoice']
    def arrival(route):
        local=datetime.fromisoformat(calendar['booking_utc']).astimezone(ZoneInfo(route['zone']))
        day=local.date()
        if local.hour>=route['cutoff_hour']:day+=timedelta(days=1)
        def banking(d,holidays):return d.weekday()<5 and d.isoformat() not in holidays
        while not banking(day,route.get('origin_holidays',calendar['bank_holidays'])):day+=timedelta(days=1)
        remaining=route['settlement_business_days']
        if remaining:
            while remaining:
                day+=timedelta(days=1)
                if banking(day,route['recipient_holidays']):remaining-=1
        else:
            while not banking(day,route['recipient_holidays']):day+=timedelta(days=1)
        return datetime.combine(day,time(route['arrival_hour']),ZoneInfo(route['recipient_zone']))
    for invoice in invoices:
        route=min((r for r in rows if r['kind']=='calendar_route' and r['currency']==invoice['currency'] and arrival(r)<=datetime.fromisoformat(invoice['deadline_utc'])),key=lambda r:r['fee_minor'])
        service_action(p,'propose_payment_cross_calendar_delivery',secondary,'reserve_route',invoice_id=invoice['id'],route_id=route['id'])
    joint_initial(p,agreement,initial,primary)
    rows=service_rows(p,primary)
    orders=[r for r in rows if r['kind']=='import_order']
    titles={r['reference']:r for r in rows if r['kind']=='original_title'}
    in_flight={r['id'] for r in rows if r['kind']=='documentary_drawing' and r['status']=='ACCEPTED'}
    history={o['id']:sum(r['amount_minor'] for r in rows if r['kind']=='cash_posting' and r['status']=='POSTED' and r['order_ref']==o['reference']) for o in orders}
    paid=set();delivered=set();lodged=set()
    for order in orders:
        if order['delivery_due_minute']<max([0]+[r.get('confirmation_minute',0) for r in rows if r['kind']=='documentary_drawing' and r['title_ref']==order['title_ref']]):
            service_action(p,'propose_documentary_import',primary,'issue_guarantee',order_id=order['id'])
            depot=next(r for r in rows if r['kind']=='delivery_depot' and r['reference']==order['agreed_depot_ref'])
            service_action(p,'propose_documentary_import',primary,'deliver',order_id=order['id'],depot_id=depot['id'],quantity_units=order['quantity_units']);delivered.add(order['id'])
    joint_flush(p,agreement)
    sent=False
    while True:
        minute=p.call('assistant','get_clock')['minute']
        rows=service_rows(p,primary)
        for drawing in (r for r in rows if r['kind']=='documentary_drawing' and r['status']=='CONFIRMED_UNPAID'):
            service_action(p,'propose_documentary_import',primary,'settle_confirmed',drawing_id=drawing['id'])
        rows=service_rows(p,primary)
        for order in orders:
            drawings=[r for r in rows if r['kind']=='documentary_drawing' and r['order_ref']==order['reference']]
            if order['id'] not in paid and all(r['status'] in ('SETTLED','RETURNED','FINAL') for r in drawings):
                credit=sum(r['amount_minor'] for r in rows if r['kind']=='commercial_credit' and r['status']=='SIGNED' and r['order_ref']==order['reference'] and r['invoice_period']==order['invoice_period'])
                actual=history[order['id']]+sum(r['actual_minor'] for r in drawings if r['id'] in in_flight and r['status'] in ('SETTLED','FINAL'))
                direction=next(r for r in rows if r['kind']=='payment_direction' and r['status']=='SIGNED' and r['order_ref']==order['reference'] and r['effective_from']<=minute<=r['effective_through'])
                beneficiary=next(r for r in rows if r['kind']=='beneficiary' and r['reference']==direction['beneficiary_ref'])
                service_action(p,'propose_documentary_import',primary,'direct_pay',order_id=order['id'],beneficiary_id=beneficiary['id'],amount_minor=order['face_minor']-credit-actual);paid.add(order['id'])
        for title in titles.values():
            if title['id'] not in lodged and all(r['status'] in ('SETTLED','RETURNED','FINAL') for r in rows if r['kind']=='documentary_drawing' and r['title_ref']==title['reference']):
                service_action(p,'propose_documentary_import',primary,'lodge_originals',title_id=title['id']);lodged.add(title['id'])
        for order in orders:
            if order['id'] not in delivered and titles[order['title_ref']]['id'] in lodged:
                depot=next(r for r in rows if r['kind']=='delivery_depot' and r['reference']==order['agreed_depot_ref'])
                service_action(p,'propose_documentary_import',primary,'deliver',order_id=order['id'],depot_id=depot['id'],quantity_units=order['quantity_units']);delivered.add(order['id'])
        joint_flush(p,agreement)
        currency_rows=service_rows(p,secondary)
        if not sent and all(r['rate_numerator'] is not None for r in currency_rows if r['kind']=='calendar_invoice'):
            for invoice in invoices:service_action(p,'propose_payment_cross_calendar_delivery',secondary,'send_currency',invoice_id=invoice['id'],amount_minor=invoice['amount_minor'])
            sent=True
        if len(paid)==len(orders) and len(delivered)==len(orders) and all(r.get('status')=='SETTLED' for r in currency_rows if r['kind']=='calendar_invoice'):break
        assert p.wait()['advanced']
    joint_flush(p,agreement)
    p.finish('Reserved the least-cost routes that satisfy actual timezone, cutoff and recipient holiday calendars, sent exact supplier currencies at executable quotes, reconciled real documentary drawing receipts and signed period credits, used a temporary guarantee only for the early shipment and recovered its collateral by lodging genuine originals.')


def case_008(p):
    p.customer_facts('Please confirm the direct-debit, installment and shared-capital instructions.',
        'Recover only actual excess supplier debits, keep legitimate invoices paid and the new utility mandate working, and retire the old mandate in its notice window. Keep USD 100 in that wallet. Complete the new purchase, settle the accepted installment return with two earned service fees, cancel future collection and refund actual overcollection; retain USD 150 there. No cross-service transfers or new funds. Delivery fees may total USD 5, with USD 4 uncommitted; deliver remaining earmarks to their own wallets.')
    cases=service_context(p,'DIVERSE-reconciled_debits','PAYMENT-payment_installment_return')
    primary=cases['reconciled_debits']['id'];secondary=cases['payment_installment_return']['id']
    agreement,initial=joint_context(p)
    joint_initial(p,agreement,initial,secondary)
    installment_start(p,secondary)
    source=next(r for r in service_rows(p,primary) if r['kind']=='external_correspondence')
    p.write('propose_service_inquiry',case_id=primary,record_id=source['id'])
    p.wait()
    installment_finish(p,secondary)
    joint_flush(p,agreement)
    source=p.read('service_records',source['id'])
    print('DEBITCORRESPONDENCE',source,flush=True)
    rows=service_rows(p,primary)
    # The old utility mandate is identified by the actual correspondence.
    receipt=source['receipt']
    retired=next(r for r in rows if r['reference']==receipt['retiring_mandate'])
    service_action(p,'propose_debit_reconciliation',primary,'revoke_mandate',record_id=retired['id'])
    while p.call('assistant','get_clock')['minute']<3:
        p.wait();joint_flush(p,agreement)
    rows=service_rows(p,primary)
    assert all(r['status']=='POSTED' for r in rows if r['kind']=='bank_credit')
    instructions={r['reference']:r for r in rows if r['kind']=='collection_instruction'}
    for invoice in (r for r in rows if r['kind']=='invoice_obligation'):
        debits=[r for r in rows if r['kind']=='bank_debit' and instructions[r['instruction']]['obligation']==invoice['reference']]
        balances={r['id']:r['amount_minor']-r['returned_minor']-sum(c['amount_minor'] for c in rows if c['kind']=='bank_credit' and c['status']=='POSTED' and c['debit']==r['reference']) for r in debits}
        net=sum(balances.values())+invoice['manual_paid_minor']
        excess=max(0,net-invoice['amount_minor'])
        for debit in debits:
            amount=min(excess,balances[debit['id']])
            if amount:
                service_action(p,'propose_debit_reconciliation',primary,'return_debit',record_id=debit['id'],amount_minor=amount);excess-=amount
        # Already locked legitimate collections remain pending at minute 3.
        pending=sum(r['amount_minor'] for r in rows if r['kind']=='queued_collection' and r['status'] in ('ACCEPTED','LOCKED') and instructions[r['instruction']]['obligation']==invoice['reference'])
        shortfall=invoice['amount_minor']-net-pending
        if shortfall>0:service_action(p,'propose_debit_reconciliation',primary,'pay_invoice',record_id=invoice['id'],amount_minor=shortfall)
    p.wait();joint_flush(p,agreement)
    service_rows(p,primary)
    p.finish('Reconciled unique physical debit entries and actual credits by debtor and invoice, returned only residual excess, preserved accepted legitimate utility collections while retiring the old mandate, completed installment settlement and delivered all earmarked capital with continuous reserves.')


def escrow_step(p, case_id, returned):
    rows=service_rows(p,case_id)
    parties={r['reference']:r['id'] for r in rows if r['kind']=='escrow_party'}
    for lot in (r for r in rows if r['kind']=='escrow_lot'):
        reports=[r for r in rows if r['kind']=='acceptance_report' and r['lot_ref']==lot['reference'] and r['status']=='FINAL' and r['issued_minute'] is not None]
        if not reports:continue
        report=max(reports,key=lambda r:r['revision'])
        prices=report['accepted_prices_minor'];accepted=sum(prices.values())
        distributable=accepted-accepted*lot['retention_bp']//10000
        entitlements={}
        for assignment in sorted((r for r in rows if r['kind']=='receivable_assignment' and r['lot_ref']==lot['reference'] and r['status']=='EFFECTIVE'),key=lambda r:r['priority']):
            if assignment['basis']=='ELIGIBLE_GROSS_CAPPED':amount=min(assignment['cap_minor'],sum(prices[k] for k in assignment['eligible_unit_refs']),distributable)
            else:amount=distributable*assignment['share_bp']//10000
            entitlements[assignment['party_ref']]=entitlements.get(assignment['party_ref'],0)+amount
            distributable-=amount
        entitlements[lot['seller_ref']]=distributable
        remaining={}
        for party in set(entitlements)|set(lot['distributions_minor']):
            paid=lot['distributions_minor'].get(party,0)-lot['returned_minor'].get(party,0)
            delta=entitlements.get(party,0)-paid
            if delta<0 and (lot['id'],party) not in returned:
                service_action(p,'propose_escrow_settlement',case_id,'return_distribution',lot_id=lot['id'],recipient_id=parties[party],amount_minor=-delta)
                returned.add((lot['id'],party))
            elif delta>0:remaining[party]=delta
        refund_total=lot['original_funded_minor']-accepted
        deposits=sorted((r for r in rows if r['kind']=='escrow_deposit' and r['lot_ref']==lot['reference'] and r['posted']),key=lambda r:r['refund_order'])
        shares=[refund_total*d['amount_minor']//sum(x['amount_minor'] for x in deposits) for d in deposits]
        for i in range(refund_total-sum(shares)):shares[i]+=1
        refunds={}
        for d,amount in zip(deposits,shares):refunds[d['remitter_ref']]=refunds.get(d['remitter_ref'],0)+amount
        refunds={k:v-lot['refunds_minor'].get(k,0) for k,v in refunds.items() if v>lot['refunds_minor'].get(k,0)}
        if lot['available_minor']<sum(remaining.values())+sum(refunds.values()):continue
        for party,amount in remaining.items():service_action(p,'propose_escrow_settlement',case_id,'distribute',lot_id=lot['id'],recipient_id=parties[party],amount_minor=amount)
        for party,amount in refunds.items():service_action(p,'propose_escrow_settlement',case_id,'refund_buyer',lot_id=lot['id'],recipient_id=parties[party],amount_minor=amount)


def case_009(p):
    p.customer_facts('Please confirm the escrow, marketplace and shared-capital settlement goals.',
        'Settle each equipment escrow by its recorded deadline using final inspection prices, correct excess prior distributions, return money to the actual buyers and retain contractual warranty funds. Complete the marketplace buyer return and sellers’ exact remaining entitlements without duplicating pending refunds. No extra or cross-service money; at most USD 5 delivery fees and USD 4 uncommitted, with final earmarks delivered to their own wallets.')
    cases=service_context(p,'DIVERSE-inspection_escrow','PAYMENT-payment_marketplace_split_refund')
    primary=cases['inspection_escrow']['id'];secondary=cases['payment_marketplace_split_refund']['id']
    agreement,initial=joint_context(p)
    joint_initial(p,agreement,initial,secondary);marketplace_settle(p,secondary)
    joint_initial(p,agreement,initial,primary)
    returned=set()
    escrow_step(p,primary,returned);joint_flush(p,agreement)
    p.wait()
    marketplace_settle(p,secondary,final=True);joint_flush(p,agreement)
    while p.call('assistant','get_clock')['minute']<4:
        escrow_step(p,primary,returned)
        update=p.wait();joint_flush(p,agreement)
        if not update['advanced']:break
    escrow_step(p,primary,returned)
    p.finish('Settled each independently funded escrow from its highest issued final inspection, respected assignment priority and lot warranty, recovered excess prior distributions before paying remaining entitlements, refunded original remitters proportionately and completed the linked marketplace return and earmarked funding.')


def case_010(p):
    p.customer_facts('Please confirm supplier settlement, currency closure, shipment and shared-cash requirements.',
        'Pay the Lyon deposit and remaining equipment balance, Bristol logistics and domestic services on time, counting prior payments. Keep USD 40 continuously, close unused currency contracts and convert all leftover EUR and GBP to USD. Pay only actual shipments, pay the courier, release unused holds and retain USD 50 in that wallet. No new money or cross-service transfers. Delivery fees may total USD 5 with USD 4 uncommitted; deliver all remaining earmarks to their own wallets.')
    cases=service_context(p,'DIVERSE-contingent_forwards','PAYMENT-payment_split_capture')
    primary=cases['contingent_forwards']['id'];secondary=cases['payment_split_capture']['id']
    agreement,initial=joint_context(p)
    joint_initial(p,agreement,initial,secondary);shipment_start(p,secondary)
    joint_initial(p,agreement,initial,primary)
    rows=service_rows(p,primary)
    forwards=[r for r in rows if r['kind']=='currency_forward']
    flex=next(r for r in forwards if r['input_currency']=='USD' and r['status']=='OPEN')
    pending=next(r for r in forwards if r['status']=='IN_FLIGHT')
    sterling=next(r for r in forwards if r['input_currency']=='EUR')
    invoices=[r for r in rows if r['kind']=='treasury_invoice']
    gbp=sum(r['face_minor']-r['paid_minor'] for r in invoices if r['currency']=='GBP')
    nomination=((gbp*sterling['rate_denominator']+sterling['rate_numerator']-1)//sterling['rate_numerator']+sterling['lot_minor']-1)//sterling['lot_minor']*sterling['lot_minor']
    service_action(p,'propose_forward_delivery',primary,'exercise',record_id=flex['id'],amount_minor=flex['notional_minor'])
    joint_flush(p,agreement)
    # Buy the small worst-case deficit while the published early quote applies.
    # This also leaves insufficient free cash for the larger pending outcome,
    # whose actual confirmed amount is settled after the earned capital release.
    euros=sum(r['face_minor']-r['paid_minor'] for r in invoices if r['currency']=='EUR')
    current=p.read('service_cases',primary)
    shortage=max(0,euros+nomination-current['state']['eur_minor']-min(pending['possible_delivery_minor']))
    if shortage:service_action(p,'propose_forward_delivery',primary,'spot',currency='EUR',side='BUY',amount_minor=shortage)
    service_action(p,'propose_forward_delivery',primary,'nominate',record_id=sterling['id'],amount_minor=nomination)
    for invoice in invoices:
        if invoice['due_minute']<=1:service_action(p,'propose_forward_delivery',primary,'pay_invoice',record_id=invoice['id'],amount_minor=invoice['face_minor']-invoice['paid_minor'])
    while p.call('assistant','get_clock')['minute']<2:p.wait()
    shipment_complete_capture(p,secondary)
    p.wait();joint_flush(p,agreement)
    pending=p.read('service_records',pending['id'])
    if pending['status']=='CONFIRMED_UNPAID':service_action(p,'propose_forward_delivery',primary,'settle_confirmed',record_id=pending['id'])
    for forward in forwards:
        current=p.read('service_records',forward['id'])
        if current['notional_minor']>current['delivered_minor']+current['closed_minor']:
            service_action(p,'propose_forward_delivery',primary,'close_remainder',record_id=current['id'])
    for invoice in invoices:
        if invoice['currency']!='USD' and invoice['due_minute']>1:service_action(p,'propose_forward_delivery',primary,'pay_invoice',record_id=invoice['id'],amount_minor=invoice['face_minor']-invoice['paid_minor'])
    current=p.read('service_cases',primary)
    for currency in ('EUR','GBP'):
        amount=current['state'][currency.lower()+'_minor']
        if amount:service_action(p,'propose_forward_delivery',primary,'spot',currency=currency,side='SELL',amount_minor=amount)
    for invoice in invoices:
        if invoice['currency']=='USD':service_action(p,'propose_forward_delivery',primary,'pay_invoice',record_id=invoice['id'],amount_minor=invoice['face_minor']-invoice['paid_minor'])
    joint_flush(p,agreement)
    p.finish('Used actual currency wallets and proportional margin releases, bought the disclosed worst-case EUR deficit at the early quote, settled the actual pending delivery after available capital, paid all remaining invoices without double-counting history, closed residual contracts and currencies and completed actual shipment captures and hold release with continuous reserves.')


def remedy_step(p, case_id, provisional=False):
    rows=service_rows(p,case_id)
    for purchase in (r for r in rows if r['kind']=='disputed_purchase'):
        memos=[r for r in rows if r['kind']=='concession_memo' and r['purchase_ref']==purchase['reference'] and r['status']=='FINAL']
        if not memos:continue
        memo=max(memos,key=lambda r:r['available_minute'])
        accepted=purchase['historical_defense_minor']+sum(r['amount_minor'] for r in purchase['responses'])
        defense=purchase['original_minor']-memo['concession_minor']-accepted
        if defense:service_action(p,'propose_merchant_remedy',case_id,'respond',purchase_id=purchase['id'],evidence_id=memo['id'],amount_minor=defense)
        remedies=[r for r in rows if r['kind']=='buyer_remedy' and r['purchase_ref']==purchase['reference']]
        recovery=purchase['new_refund_minor']+sum(r['amount_minor'] for r in remedies if r['status']=='POSTED')
        pending=sum(r['amount_minor'] for r in remedies if r['status']=='PENDING')
        if not provisional:assert pending==0
        needed=max(0,memo['concession_minor']-recovery-pending)
        if needed:service_action(p,'propose_merchant_remedy',case_id,'refund',purchase_id=purchase['id'],amount_minor=needed)


def case_015(p):
    p.customer_facts('Please confirm concessions, defense rights, marketplace settlement and capital limits.',
        'Complete the authorized final concessions on each purchase without duplicate recovery, preserve the remaining timely defense and count already accepted responses. Settle the accepted marketplace return and remaining seller entitlements without duplicating pending refunds. No new or cross-service money. Use at most USD 5 delivery fees, retain USD 4 uncommitted and deliver final earmarks to their own wallets.')
    cases=service_context(p,'DIVERSE-overlapping_remedies','PAYMENT-payment_marketplace_split_refund')
    primary=cases['overlapping_remedies']['id'];secondary=cases['payment_marketplace_split_refund']['id']
    agreement,initial=joint_context(p)
    joint_initial(p,agreement,initial,secondary);marketplace_settle(p,secondary)
    joint_initial(p,agreement,initial,primary)
    remedy_step(p,primary,provisional=True);joint_flush(p,agreement)
    p.wait()
    marketplace_settle(p,secondary,final=True);joint_flush(p,agreement)
    remedy_step(p,primary)
    joint_flush(p,agreement)
    p.finish('Preserved each timely final-memo defense exactly once, counted historical accepted responses and actual scheme and merchant recoveries, paid only guaranteed residual loss before pending results and the final remainder afterward, and completed marketplace settlement and earmarked cash delivery without duplicate recovery.')


def group_commit_ready(p, case_id):
    rows=service_rows(p,case_id)
    for group in (r for r in rows if r['kind']=='purchase_group' and not r['committed']):
        contributors=[r for r in rows if r['kind']=='group_contribution' and r['group']==group['reference'] and r['received_minor']>0 and not r['withdrawn']]
        if len(contributors)>=group['minimum_people'] and sum(r['received_minor'] for r in contributors)>=group['minimum_contribution_minor']:
            service_action(p,'propose_payment_group_purchase_commitment',case_id,'commit_group',group_id=group['id'],offer='GROUP')


def group_finish(p, case_id):
    rows=service_rows(p,case_id)
    for group in (r for r in rows if r['kind']=='purchase_group'):
        assert group['committed']
        remaining=group['price_minor']-group['merchant_paid_minor']
        if remaining:service_action(p,'propose_payment_group_purchase_commitment',case_id,'pay_merchant',group_id=group['id'],amount_minor=remaining)
        contributors=[r for r in rows if r['kind']=='group_contribution' and r['group']==group['reference']]
        continuing={r['reference']:r['received_minor'] for r in contributors if not r['withdrawn']}
        refunds=proportional(sum(continuing.values())-group['price_minor'],continuing)
        for person in contributors:
            amount=(person['received_minor'] if person['withdrawn'] else refunds[person['reference']])-person['refund_minor']
            if amount:service_action(p,'propose_payment_group_purchase_commitment',case_id,'refund_participant',participant_id=person['id'],amount_minor=amount)


def case_011(p):
    from itertools import product
    p.customer_facts('Please confirm destinations, cost preferences, group entitlements and shared-capital limits.',
        'Deliver Alpha and Gamma to production and Beta and Delta to returns, using current title rights and the arranged pickup windows at the lowest complete cost. Retain USD 10 in that wallet. Obtain both group prices, refund withdrawn contributions and distribute each group’s savings among its own continuing contributors. No new money or cross-group/service funding. Delivery fees may total USD 5 with USD 4 uncommitted; deliver the remaining earmarks to their wallets.')
    cases=service_context(p,'DIVERSE-document_title_allocation','PAYMENT-payment_group_purchase_commitment')
    primary=cases['document_title_allocation']['id'];secondary=cases['payment_group_purchase_commitment']['id']
    agreement,initial=joint_context(p)
    joint_initial(p,agreement,initial,secondary);group_commit_ready(p,secondary)
    joint_initial(p,agreement,initial,primary)
    rows=service_rows(p,primary)
    lots=[r for r in rows if r['kind']=='titled_cargo_lot']
    windows=[r for r in rows if r['kind']=='pickup_window']
    tariffs={r['reference']:r for r in rows if r['kind']=='title_storage_tariff'}
    candidates=[]
    for assignments in product(windows,repeat=len(lots)):
        if any(w['minute']>lot['due_minute'] for lot,w in zip(lots,assignments)):continue
        if any(sum(lot['handling_units'] for lot,w in zip(lots,assignments) if w['id']==window['id'])>window['capacity_units'] for window in windows):continue
        cost=0
        for lot,window in zip(lots,assignments):
            tariff=tariffs[lot['tariff_ref']];days=max(0,window['minute']-tariff['free_through'])
            cost+=tariff['loading_fees_minor'][str(window['minute'])]+lot['handling_units']*(tariff['first_window_rate_minor']+max(0,days-1)*tariff['later_window_rate_minor'] if days else 0)
        candidates.append((cost,assignments))
    _,schedule=min(candidates,key=lambda x:x[0])
    for title in (r for r in rows if r['kind']=='title_document' and r['status']=='ACTIVE' and r['split_child_refs']):
        destinations={lot['expected_destination_ref'] for lot in lots if lot['reference'] in title['covers']}
        if len(destinations)>1:service_action(p,'propose_title_release',primary,'activate_split',title_id=title['id'])
    joint_flush(p,agreement)
    rows=service_rows(p,primary)
    destinations={r['reference']:r['id'] for r in rows if r['kind']=='cargo_destination'}
    for lot in lots:
        title=next(r for r in rows if r['kind']=='title_document' and r['status']=='ACTIVE' and lot['reference'] in r['covers'])
        if title['endorsed_destination_ref'] is None:service_action(p,'propose_title_release',primary,'endorse_title',title_id=title['id'],destination_id=destinations[lot['expected_destination_ref']])
    for minute in range(3):
        assert p.call('assistant','get_clock')['minute']==minute
        if minute==2:
            group_commit_ready(p,secondary);group_finish(p,secondary);joint_flush(p,agreement)
        for lot,window in zip(lots,schedule):
            if window['minute']==minute:service_action(p,'propose_title_release',primary,'dispatch',lot_id=lot['id'],window_id=window['id'],destination_id=destinations[lot['expected_destination_ref']])
        if minute<2:p.wait()
    joint_flush(p,agreement)
    p.finish('Split the operative joint title for distinct destinations, endorsed current child rights and dispatched all indivisible lots in the globally least-cost feasible pickup schedule, preserved reserves, and settled both group-price purchases and contributor refunds using each group’s own actual money.')


def case_012(p):
    from itertools import product
    p.customer_facts('Please confirm continuous cover, fee optimization, reserves and authentication availability.',
        'Keep all three guarantees continuously effective through minute 5, pay the supplier and insurance on time and retain USD 10 throughout. Renewal and bridge fees may total USD 25; choose the lowest fee feasible plan. Complete both checkouts at actual final prices; one USD 2 new verification is permitted and I am available for private authentication only at minute zero. No new money or cross-service transfers. Capital delivery fees may total USD 5, with USD 4 uncommitted; deliver final earmarks to their wallets.')
    cases=service_context(p,'DIVERSE-continuous_guarantees','PAYMENT-payment_authentication_binding')
    primary=cases['continuous_guarantees']['id'];secondary=cases['payment_authentication_binding']['id']
    agreement,initial=joint_context(p)
    joint_initial(p,agreement,initial,secondary);authentication_start(p,secondary)
    joint_initial(p,agreement,initial,primary)
    rows=service_rows(p,primary)
    guarantees=[r for r in rows if r['kind']=='continuing_guarantee']
    early=min(guarantees,key=lambda r:r['submission_deadline'])
    standard=min((r for r in rows if r['kind']=='guarantee_renewal_offer' and r['guarantee_ref']==early['reference']),key=lambda r:r['fee_minor'])
    service_action(p,'propose_guarantee_continuity',primary,'submit_renewal',offer_id=standard['id'])
    joint_flush(p,agreement)
    p.wait()
    for order in service_rows(p,secondary):
        if order['kind']=='checkout_order':authentication_pay(p,secondary,order)
    joint_flush(p,agreement)
    rows=service_rows(p,primary)
    standard=next(r for r in rows if r['id']==standard['id'])
    bridge=next(r for r in rows if r['kind']=='temporary_guarantee_offer')
    needs_bridge=standard['activation_minute']>early['old_through']+1
    later=[g for g in guarantees if g['id']!=early['id']]
    options=[[r for r in rows if r['kind']=='guarantee_renewal_offer' and r['guarantee_ref']==g['reference']] for g in later]
    supplier=next(r for r in rows if r['kind']=='guarantee_bill')
    insurance=next(r for r in rows if r['kind']=='guarantee_automatic_debit')
    cash=p.read('service_cases',primary)['cash_minor']
    possible=[]
    for combo in product(*options):
        fees=sum(r['fee_minor'] for r in combo)+(bridge['fee_minor'] if needs_bridge else 0)
        margin=max(0,standard['required_margin_minor']-early['margin_minor'])+sum(max(0,r['required_margin_minor']-g['margin_minor']) for g,r in zip(later,combo))
        if fees+standard['fee_minor']<=2500 and cash-fees-margin-supplier['amount_minor']-insurance['amount_minor']>=1000:possible.append((fees,combo))
    _,combo=min(possible,key=lambda x:x[0])
    if needs_bridge:service_action(p,'propose_guarantee_continuity',primary,'buy_bridge',offer_id=bridge['id'])
    for offer in combo:service_action(p,'propose_guarantee_continuity',primary,'submit_renewal',offer_id=offer['id'])
    for guarantee,offer in [(early,standard),*zip(later,combo)]:
        shortfall=max(0,offer['required_margin_minor']-guarantee['margin_minor'])
        if shortfall:service_action(p,'propose_guarantee_continuity',primary,'add_margin',guarantee_id=guarantee['id'],amount_minor=shortfall)
    service_action(p,'propose_guarantee_continuity',primary,'pay_supplier',bill_id=supplier['id'],amount_minor=supplier['amount_minor'])
    while p.call('assistant','get_clock')['minute']<5:
        update=p.wait()
        if not update['advanced']:break
    joint_flush(p,agreement)
    p.finish('Submitted the port renewal before cutoff, used its actual admission decision to choose the minimum-fee feasible remaining renewals and bridge, lodged every required margin without interrupting cover, preserved the insurance and cash reserve, and completed privately verified final checkouts and earmarked capital delivery.')


def indemnity_allocate(p, case_id):
    rows=service_rows(p,case_id)
    losses={r['reference']:r for r in rows if r['kind']=='insured_loss'}
    for policy in (r for r in rows if r['kind']=='indemnity_policy'):
        remaining=policy['aggregate_cap_minor'];targets=[]
        for position in (r for r in rows if r['kind']=='insurance_position' and r['policy']==policy['reference']):
            loss=losses[position['loss']]
            covered=policy['insured']==loss['owner'] and policy['asset_type']==loss['asset_type'] and loss['reported_day']<=policy['report_through_day']
            if policy['basis']=='OCCURRENCE':covered=covered and policy['from_day']<=loss['incident_day']<=policy['through_day']
            else:covered=covered and policy['from_day']<=loss['reported_day']<=policy['through_day'] and loss['incident_day']>=policy['retroactive_day']
            net=max(0,loss['gross_minor']-loss['deductible_minor']-(loss['salvage_minor'] if loss['salvage_realized'] else 0)-loss['merchant_received_minor'])
            allowed=min(policy['per_loss_cap_minor'],max(0,net-policy['attachment_minor'])) if covered else 0
            target=min(remaining,allowed);remaining-=target
            retained=position['requested_minor']-position['returned_minor']
            targets.append((position,target-retained))
        # Return to the exact originating policy before reusing its aggregate.
        for position,delta in targets:
            if delta<0:service_action(p,'propose_indemnity_reconciliation',case_id,'return_indemnity',record_id=position['id'],amount_minor=-delta)
        for position,delta in targets:
            if delta>0:service_action(p,'propose_indemnity_reconciliation',case_id,'claim',record_id=position['id'],amount_minor=delta)


def case_013(p):
    p.customer_facts('Please confirm insurance recovery, wallet tender and shared-capital instructions.',
        'Obtain the maximum indemnity under actual policy dates and layers, realize salvage, pay replacements on time and reconcile final supplier recoveries. Preserve USD 100 including its dedicated reserve allocation. Restore cancelled purchases to their original cash and promotion lots, correct only confirmed duplicate top-ups, complete the retained order and retain USD 200 ordinary cash at completion. No new or cross-service funds. Capital delivery fees may total USD 5 with USD 4 uncommitted; deliver final earmarks to their own wallets.')
    cases=service_context(p,'DIVERSE-shared_indemnity','PAYMENT-payment_stored_value_restitution')
    primary=cases['shared_indemnity']['id'];secondary=cases['payment_stored_value_restitution']['id']
    agreement,initial=joint_context(p)
    joint_initial(p,agreement,initial,secondary)
    rows=service_rows(p,secondary)
    cancelled=next(r for r in rows if r['kind']=='wallet_order' and r['status']=='CANCELLED')
    lots={r['reference']:r for r in rows if r['kind']=='wallet_lot'}
    for reference,amount in cancelled['original_tender'].items():
        service_action(p,'propose_payment_stored_value_restitution',secondary,'restore_tender',lot_id=lots[reference]['id'],amount_minor=amount)
    order=next(r for r in rows if r['kind']=='wallet_order' and r['status']=='OPEN')
    promo=min(order['promotion_limit_minor'],lots['PROMO']['available_minor']+cancelled['original_tender'].get('PROMO',0))
    service_action(p,'propose_payment_stored_value_restitution',secondary,'pay_order',allocations={lots['PROMO']['id']:promo,lots['CASH']['id']:order['amount_minor']-promo})
    rows=service_rows(p,primary)
    source=next(r for r in rows if r['kind']=='external_correspondence')
    p.write('propose_service_inquiry',case_id=primary,record_id=source['id'])
    for loss in (r for r in rows if r['kind']=='insured_loss' and r['salvage_minor']):service_action(p,'propose_indemnity_reconciliation',primary,'sell_salvage',record_id=loss['id'])
    indemnity_allocate(p,primary)
    p.wait()
    rows=service_rows(p,primary)
    for bill in (r for r in rows if r['kind']=='replacement_bill' and r['due_minute']<=2):service_action(p,'propose_indemnity_reconciliation',primary,'pay_replacement',record_id=bill['id'],amount_minor=bill['amount_minor'])
    joint_flush(p,agreement)
    topup=p.read('service_records',lots['TOPUP']['id'])
    assert topup['duplicate_minor'] is not None
    service_action(p,'propose_payment_stored_value_restitution',secondary,'return_topup',amount_minor=topup['duplicate_minor'])
    joint_flush(p,agreement)
    while p.call('assistant','get_clock')['minute']<max(r['merchant_review_minute'] or 0 for r in rows if r['kind']=='insured_loss'):p.wait()
    indemnity_allocate(p,primary)
    p.wait()
    rows=service_rows(p,primary)
    for bill in (r for r in rows if r['kind']=='replacement_bill' and r['amount_minor']>r['paid_minor']):service_action(p,'propose_indemnity_reconciliation',primary,'pay_replacement',record_id=bill['id'],amount_minor=bill['amount_minor']-bill['paid_minor'])
    for loss in (r for r in rows if r['kind']=='insured_loss'):
        recovery=(loss['salvage_minor'] if loss['salvage_realized'] else 0)+loss['merchant_received_minor']
        service_action(p,'propose_indemnity_reconciliation',primary,'record_recovery',record_id=loss['id'],external_recovery_minor=recovery)
    joint_flush(p,agreement)
    p.finish('Matched occurrence and claims-made cover to actual loss and reporting dates, maximized separate primary and excess aggregates, returned superseded indemnity to its own layer before reallocating capacity, paid all replacements and recorded actual recoveries; restored exact wallet tender and corrected only the bank-confirmed duplicate.')


def case_014(p):
    p.customer_facts('Please confirm clearing scope, brokerage payer, internal signatures and funding limits.',
        'Settle only agreed intercompany invoices on time and pay Copper’s USD 200 brokerage bill from Copper’s own account. Leave the disputed quality invoice outside. Clearing fees may total USD 20 and every participating company needs two distinct authorized people covering director and treasury capacities. Settle the actual cheque holders and urgent inspection without duplicate payment, retaining USD 50 at completion. No borrowing or cross-service funds. Capital delivery fees may total USD 5 with USD 4 uncommitted; deliver final company earmarks.')
    cases=service_context(p,'DIVERSE-revised_netting','PAYMENT-payment_cheque_stop_and_replacement')
    primary=cases['revised_netting']['id'];secondary=cases['payment_cheque_stop_and_replacement']['id']
    agreement,initial=joint_context(p)
    joint_initial(p,agreement,initial,secondary);cheque_start(p,secondary)
    rows=service_rows(p,primary)
    accounts={r['reference']:r for r in rows if r['kind']=='clearing_account'}
    routes=p.rows('joint_routes')
    delivered={a['id']:0 for a in accounts.values()}
    def fund(account,amount,source):
        if not amount:return
        route=min((r for r in p.rows('joint_routes') if r['case_id']==primary and r.get('destination_account_id')==account['id']),key=lambda r:r['fee_minor'])
        p.write('propose_joint_capital_delivery',agreement_id=agreement['id'],case_id=primary,route_id=route['id'],allocations={source:amount},terms_version=route['terms_version'])
        delivered[account['id']]+=amount
    # Fund the first debtor and the broker from their own registered allocations.
    fund(accounts['A'],81000,agreement['fee_source_id'])
    fund(accounts['B'],56000,agreement['fee_source_id'])
    def execute_signed(cycle):
        cycle=cycle['receipt']['cycle']
        minute=p.call('assistant','get_clock')['minute']
        current=service_rows(p,primary)
        persons={r['reference']:r for r in current if r['kind']=='clearing_person'}
        participants=set(cycle['participant_refs'])
        selected=[]
        for capacity in ('DIRECTOR','TREASURY'):
            login=next(r for r in current if r['kind']=='clearing_staff_login' and r['status']=='ACTIVE' and r['capacity']==capacity and r['person_ref'] not in selected and participants<=set(persons[r['person_ref']]['company_refs']) and persons[r['person_ref']]['effective_from']<=minute<persons[r['person_ref']]['effective_until'])
            service_action(p,'propose_group_clearing',primary,'collect_signature',cycle_id=cycle['id'],login_id=login['id']);selected.append(login['person_ref'])
        service_action(p,'propose_group_clearing',primary,'execute',cycle_id=cycle['id'])
    invoices=[r for r in rows if r['kind']=='intercompany_invoice' and r['agreement_status']=='AGREED']
    first=[r['id'] for r in invoices if r['due_minute']==0 or r['reference']=='AB_LATER']
    cycle=service_action(p,'propose_group_clearing',primary,'prepare_cycle',invoice_ids=first)
    execute_signed(cycle)
    joint_flush(p,agreement)
    broker=next(r for r in rows if r['kind']=='clearing_external_obligation')
    recipient=next(r for r in rows if r['kind']=='clearing_recipient' and r['reference']==broker['recipient_ref'])
    external=service_action(p,'propose_group_clearing',primary,'prepare_external',obligation_id=broker['id'],payer_account_id=accounts[broker['payer_ref']]['id'],recipient_id=recipient['id'],amount_minor=broker['amount_minor'])
    execute_signed(external)
    while p.call('assistant','get_clock')['minute']<2:p.wait()
    cheque_finish(p,secondary)
    source=next(s for s in p.rows('joint_sources') if s['permitted_case_ids']==[primary])
    assert source['status']=='AVAILABLE'
    for account in accounts.values():fund(account,agreement['capital_by_account'][account['id']]-delivered[account['id']],source['id'])
    # Current signed invoice balances include real final credit-note versions.
    final=service_action(p,'propose_group_clearing',primary,'prepare_cycle',invoice_ids=[r['id'] for r in invoices])
    execute_signed(final)
    p.finish('Settled the early agreed invoices and Copper’s own brokerage payment before their deadlines, obtained distinct director and treasury signatures on each captured instruction, settled final signed balances after genuine credit confirmations, kept the disputed invoice outside and reconciled current cheque-holder entitlements and each company’s earmarked capital.')


def case_016(p):
    p.customer_facts('Please confirm deposit, installment and shared-capital preferences and reserves.',
        'Pay all four business obligations and the automatic rent on time, retain USD 10 throughout and maximize final cash using existing deposits and actual reimbursement only. Complete the new purchase, reconcile the actual installment return and earned fees, cancel future collection, refund real overcollection and retain USD 150 in that wallet. Respect the registered capital earmarks, at most USD 5 delivery fees and USD 4 uncommitted cash, and finally deliver remaining earmarked capital to its own service.')
    cases = service_context(p,'DIVERSE-tiered_deposit_calendar','PAYMENT-common','PAYMENT-payment_installment_return')
    deposit_case = cases['tiered_deposit_calendar']['id']
    installment = cases['payment_installment_return']['id']
    agreement,initial = joint_context(p)
    joint_initial(p,agreement,initial,installment)
    installment_start(p,installment)
    joint_initial(p,agreement,initial,deposit_case)
    rows = service_rows(p,deposit_case)
    payroll = next(r for r in rows if r['kind']=='deposit_obligation' and r['due_minute']==0)
    cash = p.read('service_cases',deposit_case)['cash_minor']
    need = payroll['amount_minor']+1000-cash
    candidates = [r for r in rows if r['kind']=='dated_term_deposit' and r['principal_minor']-r['break_charge_minor']>=need and r['tier_group']=='STANDARD']
    chosen = min(candidates,key=lambda r:r['base_interest_minor']+r['break_charge_minor'])
    service_action(p,'propose_deposit_calendar',deposit_case,'redeem_early',deposit_id=chosen['id'])
    service_action(p,'propose_deposit_calendar',deposit_case,'pay_obligation',obligation_id=payroll['id'],amount_minor=payroll['amount_minor'])
    joint_flush(p,agreement)
    p.wait()
    installment_finish(p,installment)
    joint_flush(p,agreement)
    rows = service_rows(p,deposit_case)
    supplier = next(r for r in rows if r['kind']=='deposit_obligation' and r['due_minute']==1)
    cash = p.read('service_cases',deposit_case)['cash_minor']
    if cash<supplier['amount_minor']+1000:
        # Breaking a remaining standard deposit preserves the premium tier.
        remaining = [r for r in rows if r['kind']=='dated_term_deposit' and r['status']=='ACTIVE' and r['tier_group']=='STANDARD' and r['principal_minor']-r['break_charge_minor']>=supplier['amount_minor']+1000-cash]
        chosen = min(remaining,key=lambda r:r['base_interest_minor']+r['break_charge_minor'])
        service_action(p,'propose_deposit_calendar',deposit_case,'redeem_early',deposit_id=chosen['id'])
    service_action(p,'propose_deposit_calendar',deposit_case,'pay_obligation',obligation_id=supplier['id'],amount_minor=supplier['amount_minor'])
    for _ in range(10):
        p.wait()
        minute = p.call('assistant','get_clock')['minute']
        rows = service_rows(p,deposit_case)
        for bill in (r for r in rows if r['kind']=='deposit_obligation' and r['due_minute']==minute and r['paid_minor']<r['amount_minor']):
            service_action(p,'propose_deposit_calendar',deposit_case,'pay_obligation',obligation_id=bill['id'],amount_minor=bill['amount_minor']-bill['paid_minor'])
        if minute>=max(r['maturity_minute'] for r in rows if r['kind']=='dated_term_deposit'):
            break
    joint_flush(p,agreement)
    service_rows(p,deposit_case)
    p.finish('Paid all dated obligations and automatic rent with continuous cash coverage, preserved the premium relationship and selected the lowest-loss required early redemptions after the actual reimbursement result, reconciled installment returns and real collections, and delivered the correctly earmarked remaining capital within the shared fee and reserve terms.')


def case_017(p):
    p.customer_facts('Please confirm financing preferences, retained funds and both collection and refund goals.',
        'Pay the supplier and shipping charges on time, deliver accepted goods documents and return rejected documents, and keep USD 50 throughout. Minimize financed bill principal, then fees; financing may cost at most USD 20. There is no extra funding. Refund exactly accepted returned items and settle both marketplace sellers on time without duplicate buyer refund or unrelated reversal.')
    cases = service_context(p,'DIVERSE-actual_collections','PAYMENT-payment_marketplace_split_refund')
    collection = cases['actual_collections']['id']
    marketplace = cases['payment_marketplace_split_refund']['id']
    marketplace_settle(p,marketplace)
    rows = service_rows(p,collection)
    terms = next(r for r in rows if r['kind']=='collection_cash_terms')
    p.wait()
    rows = service_rows(p,collection)
    current = p.read('service_cases',collection)
    early = [r for r in rows if r['kind']=='payable' and r['due_minute']==p.call('assistant','get_clock')['minute']]
    needed = sum(r['amount_minor']-r['paid_minor'] for r in early)+terms['minimum_cash_minor']-current['cash_minor']
    if needed>0:
        candidates = [(needed+r['discount_fee_minor'],r) for r in rows if r['kind']=='collection_bill' and r['accepted_minor']-r['received_minor']>=needed+r['discount_fee_minor'] and r['discount_fee_minor']<=2000]
        principal,bill = min(candidates,key=lambda x:(x[0],x[1]['discount_fee_minor']))
        service_action(p,'propose_actual_collection',collection,'discount',bill_id=bill['id'],amount_minor=principal)
    for payable in early:
        service_action(p,'propose_actual_collection',collection,'pay',payable_id=payable['id'],amount_minor=payable['amount_minor']-payable['paid_minor'])
    marketplace_settle(p,marketplace,final=True)
    while True:
        rows = service_rows(p,collection)
        minute = p.call('assistant','get_clock')['minute']
        for bill in (r for r in rows if r['kind']=='collection_bill'):
            eligible = bill['accepted_minor'] if bill['document_mode']=='DA' else bill['received_minor']
            units = eligible//bill['unit_price_minor']-bill['delivered_units']
            if units:
                service_action(p,'propose_actual_collection',collection,'deliver',bill_id=bill['id'],quantity_units=units)
            rejected = (bill['face_minor']-bill['accepted_minor'])//bill['unit_price_minor']-bill['returned_units']
            if rejected:
                service_action(p,'propose_actual_collection',collection,'return_documents',bill_id=bill['id'],quantity_units=rejected)
        for payable in (r for r in rows if r['kind']=='payable' and r['paid_minor']<r['amount_minor'] and r['due_minute']<=minute):
            service_action(p,'propose_actual_collection',collection,'pay',payable_id=payable['id'],amount_minor=payable['amount_minor']-payable['paid_minor'])
        if minute>=terms['final_receipt_minute']:
            break
        p.wait()
    p.finish('Financed the minimum feasible accepted bill principal within the fee cap, paid supplier and agency on time, released DA documents only after acceptance and DP documents only against actual buyer receipts, returned rejected originals, and settled the linked buyer return and seller entitlements.')


def cheque_start(p, case_id):
    operation = 'propose_payment_cheque_stop_and_replacement'
    rows = service_rows(p,case_id)
    bill = next(r for r in rows if r['kind']=='bill')
    service_action(p,operation,case_id,'pay_bill',record_id=bill['id'],amount_minor=bill['amount_minor'])
    issued = next(r for r in rows if r['kind']=='electronic_cheque' and r['status']=='ISSUED')
    service_action(p,operation,case_id,'request_stop',cheque_id=issued['id'])


def cheque_finish(p, case_id):
    rows = service_rows(p,case_id)
    assert all(r.get('held_minor',0)==0 for r in rows if r['kind']=='electronic_cheque')
    for invoice in (r for r in rows if r['kind']=='cheque_invoice'):
        due = invoice['face_minor']-invoice['paid_minor']
        if due:
            service_action(p,'propose_payment_cheque_stop_and_replacement',case_id,'replacement_payment',invoice_id=invoice['id'],payee=invoice['current_holder'],amount_minor=due)


def interest_entitlements(rows):
    result = {}
    for statement in (r for r in rows if r['kind']=='signed_interest_statement'):
        charge = 0
        for daily in statement['daily_balances']:
            day, balance = daily['day'],daily['balance_minor']
            for item in (r for r in rows if r['kind']=='dated_bank_item' and r['account_ref']==statement['account_ref']):
                original,economic = item['original_value_day'],item['current_economic_day']
                if economic<=day<original:
                    balance += item['principal_minor']
                elif original<=day<economic:
                    balance -= item['principal_minor']
            if balance>=0:
                continue
            rate = next(r for r in rows if r['kind']=='debit_interest_rate' and r['account_ref']==statement['account_ref'] and r['effective_from_day']<=day<r['effective_until_day'])
            debt = -balance
            charge += (min(debt,rate['tier_limit_minor'])*rate['first_annual_bp']+max(0,debt-rate['tier_limit_minor'])*rate['excess_annual_bp'])//(10000*rate['basis_days'])
        result[statement['reference']] = statement['interest_charged_minor']-charge
    return result


def case_018(p):
    p.customer_facts('Please confirm the accounting-period, fee-payment and reserve requirements for both matters.',
        'Correct both Rivergate interest accounts in the current accounting period without altering the signed June accounts. Pay the USD 60 retainer now and USD 40 balance from operating on time; keep USD 20 operating and USD 10 sales throughout. Correct interest credits and recovery of actual excess refunds are authorized, with no new funding. Stop and replace the equipment cheque if possible; otherwise count actual presentment. Pay lawful holders and the inspection fee, retaining USD 50 at completion.')
    cases = service_context(p,'DIVERSE-dated_interest','PAYMENT-common','PAYMENT-payment_cheque_stop_and_replacement')
    interest = cases['dated_interest']['id']
    cheque = cases['payment_cheque_stop_and_replacement']['id']
    rows = service_rows(p,interest)
    for item in (r for r in rows if r['kind']=='dated_bank_item'):
        keys = ['sender_bank','currency','principal_minor','settlement_reference','settlement_day','receiving_route_token']
        messages = [r for r in rows if r['kind']=='bank_value_confirmation' and r['status']=='FINAL' and r['verified_genuine'] and all(r[k]==item[k] for k in keys)]
        message = max(messages,key=lambda r:r['version'])
        route = next(r for r in rows if r['kind']=='historical_bank_routing' and r['route_token']==message['receiving_route_token'] and r['effective_from_day']<=message['settlement_day']<r['effective_until_day'])
        assert route['account_ref']==item['account_ref']
        if item['current_economic_day']!=message['confirmed_value_day']:
            service_action(p,'propose_interest_correction',interest,'record_value_date',item_id=item['id'],bank_message_id=message['id'],value_day=message['confirmed_value_day'])
    rows = service_rows(p,interest)
    entitlements = interest_entitlements(rows)
    period = next(r for r in rows if r['kind']=='accounting_period' and r['current'] and r['status']=='OPEN')
    for statement in (r for r in rows if r['kind']=='signed_interest_statement'):
        adjustments = [r for r in rows if r['kind']=='interest_cash_adjustment' and r['statement_ref']==statement['reference']]
        actual = sum(r['amount_minor'] for r in adjustments if r['status'] in ('POSTED','SETTLED'))
        pending = sum(r['amount_minor'] for r in adjustments if r['status']=='PROCESSING')
        amount = max(0,entitlements[statement['reference']]-actual-pending)+min(0,entitlements[statement['reference']]-actual)
        if amount:
            service_action(p,'propose_interest_correction',interest,'post_adjustment',statement_id=statement['id'],period_id=period['id'],amount_minor=amount)
    def pay_fees(due):
        for obligation in (r for r in service_rows(p,interest) if r['kind']=='accounting_fee_obligation' and r['due_minute']==due):
            payer = next(r for r in rows if r['kind']=='interest_account' and r['reference']==obligation['payer_ref'])
            recipient = next(r for r in rows if r['kind']=='interest_recipient' and r['reference']==obligation['recipient_ref'])
            service_action(p,'propose_interest_correction',interest,'pay_accountant',obligation_id=obligation['id'],payer_account_id=payer['id'],recipient_id=recipient['id'],amount_minor=obligation['amount_minor']-obligation['paid_minor'])
    pay_fees(0)
    cheque_start(p,cheque)
    p.wait()
    rows = service_rows(p,interest)
    assert all(r['status']!='PROCESSING' for r in rows if r['kind']=='interest_cash_adjustment')
    for statement in (r for r in rows if r['kind']=='signed_interest_statement'):
        actual = sum(r['amount_minor'] for r in rows if r['kind']=='interest_cash_adjustment' and r['statement_ref']==statement['reference'] and r['status'] in ('POSTED','SETTLED'))
        amount = entitlements[statement['reference']]-actual
        if amount:
            service_action(p,'propose_interest_correction',interest,'post_adjustment',statement_id=statement['id'],period_id=period['id'],amount_minor=amount)
    pay_fees(2)
    while any(r.get('held_minor',0)>0 for r in service_rows(p,cheque) if r['kind']=='electronic_cheque'):
        p.wait()
    cheque_finish(p,cheque)
    service_rows(p,interest)
    p.finish('Matched final bank confirmations to original transfers and historical routes, corrected economic dates without reposting principal, recomputed daily tiered interest including prior amendments, reconciled actual refunds in the current period and paid the accountant with reserves intact, then settled cheques from their actual bank outcomes.')


def certificate_valid(certificate, reliance, notices, acceptance_day):
    if certificate['entity']!=reliance['entity'] or certificate['account']!=reliance['account'] or not set(reliance['attributes'])<=set(certificate['attributes']):
        return False
    if certificate['covers_from_day']>reliance['period_from_day'] or certificate['covers_through_day']<reliance['period_through_day']:
        return False
    for notice in notices:
        if notice['status']!='PUBLISHED':
            continue
        if notice['mode']=='WITHDRAWAL' and notice['target_certificate']==certificate['reference'] and acceptance_day>=notice['effective_day']:
            return False
        if notice['mode']=='ANNULMENT' and notice['signing_key']==certificate['signing_key'] and certificate['issued_day'] is not None:
            low,high = notice['invalid_issue_interval']
            if low<=certificate['issued_day']<=high:
                return False
    return True


def case_019(p):
    p.customer_facts('Please confirm evidence-remediation, fee and retained-funds requirements.',
        'Complete the new file on time, correct only files actually affected by the issuer notices, preserve valid historical approvals, and keep the export guarantee and platform access supported. Replacement certificates may cost USD 20; retain USD 100. For the related marketplace return, pay exactly accepted returns and remaining seller entitlements without duplicating a pending refund.')
    cases = service_context(p,'DIVERSE-temporal_certificates','PAYMENT-payment_marketplace_split_refund')
    certificate_case = cases['temporal_certificates']['id']
    marketplace = cases['payment_marketplace_split_refund']['id']
    rows = service_rows(p,certificate_case)
    source = next(r for r in rows if r['kind']=='external_correspondence')
    p.write('propose_service_inquiry',case_id=certificate_case,record_id=source['id'])
    marketplace_settle(p,marketplace)
    day = p.read('service_cases',certificate_case)['bank_day']
    notices = [r for r in rows if r['kind']=='issuer_notice']
    operation = 'propose_certificate_remediation'
    for reliance in (r for r in rows if r['kind']=='evidence_reliance' and r['status']=='OPEN'):
        certificate = next(c for c in rows if c['kind']=='evidence_certificate' and c['status']=='ISSUED' and certificate_valid(c,reliance,notices,day) and not any(n['status']=='PENDING' and n.get('signing_key')==c['signing_key'] for n in notices))
        service_action(p,operation,certificate_case,'submit_evidence',record_id=reliance['id'],certificate_id=certificate['id'])
    p.wait()
    marketplace_settle(p,marketplace,final=True)
    pending = [n for n in notices if n['status']=='PENDING']
    while p.call('assistant','get_clock')['minute']<max(n['expected_minute'] for n in pending):
        p.wait()
    rows = service_rows(p,certificate_case)
    notices = [r for r in rows if r['kind']=='issuer_notice']
    certificates = {r['reference']:r for r in rows if r['kind']=='evidence_certificate'}
    repairs = []
    for reliance in (r for r in rows if r['kind']=='evidence_reliance'):
        if certificate_valid(certificates[reliance['certificate']],reliance,notices,reliance['accepted_day']):
            continue
        replacement = min((c for c in certificates.values() if c['status'] in ('ISSUED','AVAILABLE') and certificate_valid(c,reliance,notices,day)),key=lambda c:c['fee_minor'])
        if replacement['status']=='AVAILABLE':
            service_action(p,operation,certificate_case,'order_certificate',record_id=replacement['id'])
        service_action(p,operation,certificate_case,'reopen_reliance',record_id=reliance['id'])
        repairs.append((reliance,replacement))
    if repairs:
        p.wait()
        for reliance,certificate in repairs:
            assert p.read('service_records',certificate['id'])['status']=='ISSUED'
            service_action(p,operation,certificate_case,'submit_evidence',record_id=reliance['id'],certificate_id=certificate['id'])
        p.wait()
        rows = service_rows(p,certificate_case)
        files = {r['reference']:r for r in rows if r['kind']=='evidence_reliance'}
        for authority in (r for r in rows if r['kind']=='dependent_authority'):
            if any(authority['bound_versions'][ref]!=files[ref]['version'] for ref in authority['requires']):
                service_action(p,operation,certificate_case,'rebind_authority',record_id=authority['id'],versions={files[ref]['id']:files[ref]['version'] for ref in authority['requires']})
    p.finish('Submitted valid current evidence on time, distinguished prospective withdrawal from actual signing-key annulment, repaired only affected files and dependent authority versions within grace and fee limits, and completed the linked buyer refund and seller payments.')


def shipment_start(p, case_id):
    rows = service_rows(p,case_id)
    operation = 'propose_payment_split_capture'
    bill = next(r for r in rows if r['kind']=='bill')
    service_action(p,operation,case_id,'pay_bill',record_id=bill['id'],amount_minor=bill['amount_minor'])
    authorization = next(r for r in rows if r['kind']=='capture_authorization')
    first = next(r for r in rows if r['kind']=='fulfillment_line' and r['fulfilled'])
    service_action(p,operation,case_id,'capture',authorization_id=authorization['id'],line_id=first['id'],amount_minor=first['final_minor'])


def shipment_complete_capture(p, case_id):
    rows = service_rows(p,case_id)
    authorization = next(r for r in rows if r['kind']=='capture_authorization')
    operation = 'propose_payment_split_capture'
    for line in (r for r in rows if r['kind']=='fulfillment_line'):
        assert line['fulfilled'] and line['final_minor'] is not None
        amount = line['final_minor']-line['captured_minor']-line['cash_paid_minor']
        if amount:
            service_action(p,operation,case_id,'capture',authorization_id=authorization['id'],line_id=line['id'],amount_minor=amount)
    authorization = p.read('service_records',authorization['id'])
    if authorization['remaining_minor']:
        service_action(p,operation,case_id,'release',authorization_id=authorization['id'],amount_minor=authorization['remaining_minor'])


def authentication_start(p, case_id):
    rows = service_rows(p,case_id)
    operation = 'propose_payment_authentication_binding'
    for order in (r for r in rows if r['kind']=='checkout_order'):
        auths = [r for r in rows if r['kind']=='authentication' and r['order_ref']==order['reference'] and r['verified'] and not r['cancelled']]
        maximum = max(order.get('possible_final_minor',[]) or [order['final_minor']])
        if not any(a['maximum_minor']-a['captured_minor']>=maximum for a in auths):
            service_action(p,operation,case_id,'prepare_verification',order_id=order['id'],maximum_minor=maximum)
            for auth in service_rows(p,case_id):
                if auth['kind']=='authentication' and auth['order_ref']==order['reference'] and not auth['verified'] and not auth['cancelled']:
                    p.call('user','authenticate_payment',authentication_id=auth['id'])
        if order['final_minor'] is not None:
            authentication_pay(p,case_id,order)


def authentication_pay(p, case_id, order):
    due = order['final_minor']-order['paid_minor']
    if due:
        auth = next(r for r in service_rows(p,case_id) if r['kind']=='authentication' and r['order_ref']==order['reference'] and r['verified'] and not r['cancelled'] and r['maximum_minor']-r['captured_minor']>=due)
        service_action(p,'propose_payment_authentication_binding',case_id,'pay_checkout',order_id=order['id'],authentication_id=auth['id'],amount_minor=due)


def case_020(p):
    p.customer_facts('Please confirm card reconciliation permissions and availability for the linked checkouts.',
        'Pay both card statements by their deadlines using only the operating account, keep USD 100 there continuously, leave the tax reserve untouched and spend at most USD 10 on disputes. Recover only uncompensated unauthorized charges. Complete both purchases at their final prices, with at most one USD 2 new verification. I can complete private issuer challenges only at minute zero; please use the possible camera price range when arranging verification.')
    cases = service_context(p,'DIVERSE-late_card_reconciliation','PAYMENT-payment_authentication_binding')
    card = cases['late_card_reconciliation']['id']
    auth = cases['payment_authentication_binding']['id']
    authentication_start(p,auth)
    # The pending credit must become an actual bank result before claims.
    while any(r['kind']=='merchant_card_credit' and r['status']=='PROCESSING' for r in service_rows(p,card)):
        p.wait()
    rows = service_rows(p,card)
    evidence = {}
    for r in rows:
        if r['kind']=='merchant_purchase_evidence' and r['verified_genuine'] and r['status']=='FINAL':
            if r['series'] not in evidence or evidence[r['series']]['version']<r['version']:
                evidence[r['series']] = r
    presentments = [r for r in rows if r['kind']=='card_presentment']
    supported = set()
    for doc in evidence.values():
        matched = [r for r in presentments if all(r[k]==doc[k] for k in ('entity','cardholder','merchant_case_ref','merchant')) and doc['valid_from_day']<=r['service_day']<=doc['valid_through_day'] and r['settlement_trace'] in doc['settlement_trace_refs']]
        if sum(r['amount_minor'] for r in matched)<=doc['consent_limit_minor']:
            supported.update(r['id'] for r in matched)
    for charge in presentments:
        if charge['id'] not in supported:
            compensated = sum(r['amount_minor'] for r in rows if r['kind']=='merchant_card_credit' and r['status']=='POSTED' and r['merchant_case_ref']==charge['merchant_case_ref'])
            loss = max(0,charge['amount_minor']-compensated)
            if loss:
                service_action(p,'propose_card_reconciliation',card,'file_dispute',presentment_id=charge['id'],amount_minor=loss)
    for order in service_rows(p,auth):
        if order['kind']=='checkout_order':
            assert order['final_minor'] is not None
            authentication_pay(p,auth,order)
    p.wait()
    rows = service_rows(p,card)
    terms = next(r for r in rows if r['kind']=='card_reconciliation_terms')
    operating = next(r for r in rows if r['kind']=='company_cash_account' and r['reference']==terms['payment_account_ref'])
    for statement in (r for r in rows if r['kind']=='corporate_card_account'):
        service_action(p,'propose_card_reconciliation',card,'pay_card',card_account_id=statement['id'],cash_account_id=operating['id'],amount_minor=statement['current_due_minor'])
    p.finish('Reconciled physical presentments to genuine final purchase evidence, subtracted actual merchant credits across cards before filing exact residual claims, paid both statements from authorized operating cash and completed both amended purchases with timely private authentication and the actual final bank event.')


def case_021(p):
    p.customer_facts('Please confirm the expense and shipment settlement requirements and protected cash.',
        'Reconcile each employee’s actual eligible personal expenditure, refunds, advances and earlier reimbursements by their deadlines and retain USD 100 for operations. Pay the courier and only the actually dispatched goods on time, release unused card holds, and keep USD 50 in the shipment cash wallet.')
    cases = service_context(p,'DIVERSE-reconciled_expenses','PAYMENT-common','PAYMENT-payment_split_capture')
    expense = cases['reconciled_expenses']['id']
    shipment = cases['payment_split_capture']['id']
    source = next(r for r in service_rows(p,expense) if r['kind']=='external_correspondence')
    p.write('propose_service_inquiry',case_id=expense,record_id=source['id'])
    shipment_start(p,shipment)
    p.wait()
    terms = p.read('service_records',source['id'])['receipt']
    settle_expenses(p,expense,terms,early=True)
    while not all(r['fulfilled'] for r in service_rows(p,shipment) if r['kind']=='fulfillment_line'):
        p.wait()
    shipment_complete_capture(p,shipment)
    while p.call('assistant','get_clock')['minute']<terms['final_review_minute']:
        p.wait()
    settle_expenses(p,expense,terms,early=False)
    assert all(value==0 for value in expense_balances(service_rows(p,expense),terms['meal_cap_minor']).values())
    assert all(r['cleared_minor']==r['final_minor'] for r in service_rows(p,shipment) if r['kind']=='fulfillment_line')
    p.finish('Started the expense inquiry before the linked shipment instructions, reconciled each employee’s eligible personal expenditure and actual refunds, paid both dispatched shipments and courier, released unused card commitments, and preserved the operating reserves and dates.')


def corporate_assignments(rows, invoices, minute):
    from itertools import combinations
    people = {r['reference']:r for r in rows if r['kind']=='authority_person'}
    policy = next(r for r in rows if r['kind']=='corporate_control')
    options = []
    for invoice in invoices:
        gross = invoice['face_minor']-invoice['prior_paid_minor']+invoice['fee_minor']
        quorum = policy['upper_tier_people'] if gross>policy['threshold_minor'][invoice['currency']] else policy['ordinary_people']
        eligible = []
        for signature in (r for r in rows if r['kind']=='signed_instrument' and r['status']=='AVAILABLE' and r['verified_genuine']):
            body = signature['body']
            person = people[body['person']]
            if body['payment']!=invoice['reference'] or body['currency']!=invoice['currency'] or body['bank_version']!=invoice['bank_version'] or body['ceiling_minor']<gross:
                continue
            if invoice['currency'] not in person['currencies'] or body['capacity'] not in person['capacities'] or gross>person['ceiling_minor']:
                continue
            if not (person['effective_from']<=body['signed_minute']<person['effective_until'] and person['effective_from']<=minute<person['effective_until']):
                continue
            eligible.append(signature)
        choices = []
        for count in range(quorum,quorum+2):
            for signatures in combinations(eligible,count):
                persons = {s['body']['person'] for s in signatures}
                capacities = {s['body']['capacity'] for s in signatures}
                if len(persons)>=quorum and set(policy['required_capacities'])<=capacities:
                    choices.append((signatures,persons,gross,invoice['currency']))
        options.append(choices)
    def assign(index,used):
        if index==len(invoices):
            return []
        for signatures,persons,gross,currency in options[index]:
            if any(used[(person,currency)]+gross>people[person]['daily_limit_minor'][currency] for person in persons):
                continue
            after = dict(used)
            for person in persons:
                after[(person,currency)]+=gross
            suffix = assign(index+1,after)
            if suffix is not None:
                return [signatures]+suffix
        return None
    used = {(key,currency):p['committed_minor'][currency] for key,p in people.items() for currency in ('USD','EUR')}
    result = assign(0,used)
    assert result is not None, 'No feasible current corporate signature allocation'
    return result


def corporate_pay(p, case_id, invoices, assignments):
    for invoice,signatures in zip(invoices,assignments):
        service_action(p,'propose_corporate_payment',case_id,'attach_signatures',record_id=invoice['id'],signature_ids=[s['id'] for s in signatures])
        service_action(p,'propose_corporate_payment',case_id,'pay_invoice',record_id=invoice['id'],amount_minor=invoice['face_minor']-invoice['paid_minor'],bank_version=invoice['bank_version'])


def case_022(p):
    p.customer_facts('Please confirm corporate authority requirements and the conditional cheque stop preference.',
        'Pay all six supplier invoices by their dates using current confirmed bank details and genuine signed authorities, respecting independent-person, capacity and cumulative company controls. Count earlier payments and preserve them. I can approve as owner only in my own capacity. For the related invoices, request a stop if still possible, otherwise count actual cheque presentment, pay the lawful holders and inspection fee without duplication, and retain USD 50 at completion.')
    cases = service_context(p,'DIVERSE-versioned_authority','PAYMENT-common','PAYMENT-payment_cheque_stop_and_replacement')
    corporate = cases['versioned_authority']['id']
    cheque = cases['payment_cheque_stop_and_replacement']['id']
    rows = service_rows(p,corporate)
    early = [r for r in rows if r['kind']=='controlled_invoice' and r['due_minute']<=2]
    corporate_pay(p,corporate,early,corporate_assignments(rows,early,0))
    cheque_start(p,cheque)
    while any(r.get('held_minor',0)>0 for r in service_rows(p,cheque) if r['kind']=='electronic_cheque'):
        p.wait()
    cheque_finish(p,cheque)
    latest_copy = max(r['available_minute'] for r in rows if r['kind']=='signed_instrument')
    while p.call('assistant','get_clock')['minute']<latest_copy:
        p.wait()
    rows = service_rows(p,corporate)
    invoices = sorted((r for r in rows if r['kind']=='controlled_invoice' and r['paid_minor']<r['face_minor']),key=lambda r:(r['due_minute'],r['reference']))
    assert all(r['amendment_status']!='PENDING' for r in invoices)
    corporate_pay(p,corporate,invoices,corporate_assignments(rows,invoices,p.call('assistant','get_clock')['minute']))
    service_rows(p,corporate)
    p.finish('Settled every remaining supplier invoice with current bank details and a globally feasible set of genuine independent signatures under appointment and daily allowance limits, preserved prior payments, and reconciled and settled the linked cheques and inspection bill from actual bank outcomes.')


def case_023(p):
    from itertools import combinations
    p.customer_facts('Please confirm fee limits and the scope of your retained-cash requirement.',
        'Pay all three corporate invoices on time with existing authorities and at most USD 55 in total service fees. There is no extra funding. The USD 50 cash floor applies only to the related shipment purchase: pay only dispatched goods and courier, and release unused authorizations.')
    cases = service_context(p,'DIVERSE-revised_tolerances','PAYMENT-common','PAYMENT-payment_split_capture')
    corporate = cases['revised_tolerances']['id']
    shipment = cases['payment_split_capture']['id']
    rows = service_rows(p,corporate)
    invoices = sorted((r for r in rows if r['kind']=='authorized_invoice'),key=lambda r:r['due_minute'])
    authorities = [r for r in rows if r['kind']=='corporate_authority' and r['status']=='SIGNED']
    first = invoices[0]
    dedicated = next(r for r in authorities if r['invoice_refs']==[first['reference']])
    general = max((r for r in authorities if first['reference'] in r['invoice_refs'] and r['id']!=dedicated['id']),key=lambda r:r['total_gross_limit_minor'])
    service_action(p,'propose_tolerance_payment',corporate,'pay',invoice_id=first['id'],quote_version=first['quote_version'],authority_ids=[dedicated['id'],general['id']])
    shipment_start(p,shipment)
    revision = max(r['quote_revision_minute'] or 0 for r in invoices)
    while p.call('assistant','get_clock')['minute']<revision:
        p.wait()
    shipment_complete_capture(p,shipment)
    rows = service_rows(p,corporate)
    invoices = [r for r in rows if r['kind']=='authorized_invoice' and not r['paid_minor']]
    authorities = [r for r in rows if r['kind']=='corporate_authority' and r['status']=='SIGNED']
    minute = p.call('assistant','get_clock')['minute']
    def assign(index, used):
        if index==len(invoices):
            return []
        invoice = invoices[index]
        gross = invoice['principal_minor']+invoice['fee_minor']
        eligible = [a for a in authorities if invoice['reference'] in a['invoice_refs'] and invoice['beneficiary_version'] in a['beneficiary_versions'] and a['effective_from']<=minute<=a['effective_through'] and invoice['fee_minor']<=a['fee_ceiling_minor'] and used[a['id']]+gross<=a['total_gross_limit_minor']]
        for pair in combinations(eligible,2):
            if pair[0]['natural_person']==pair[1]['natural_person']:
                continue
            next_used = dict(used)
            for a in pair:
                next_used[a['id']]+=gross
            suffix = assign(index+1,next_used)
            if suffix is not None:
                return [pair]+suffix
        return None
    assignments = assign(0,{a['id']:a['used_gross_minor'] for a in authorities})
    assert assignments is not None
    for invoice,pair in zip(invoices,assignments):
        service_action(p,'propose_tolerance_payment',corporate,'pay',invoice_id=invoice['id'],quote_version=invoice['quote_version'],authority_ids=[a['id'] for a in pair])
    p.wait()
    service_rows(p,shipment)
    p.finish('Paid all corporate invoices using current quote versions and distinct signed natural-person authorities within their cumulative limits and total fee cap, interleaved the linked shipment correctly, paid only dispatched goods and courier, and released unused card authority.')


def installment_start(p, case_id):
    rows = service_rows(p,case_id)
    bill = next(r for r in rows if r['kind']=='bill')
    service_action(p,'propose_payment_installment_return',case_id,'pay_bill',record_id=bill['id'],amount_minor=bill['amount_minor'])
    service_action(p,'propose_payment_installment_return',case_id,'cancel_future')


def installment_finish(p, case_id):
    plan = next(r for r in service_rows(p,case_id) if r['kind']=='installment_plan')
    assert plan['return_minor'] is not None
    operation = 'propose_payment_installment_return'
    principal = plan['principal_minor']-plan['return_minor']
    fee = plan['earned_periods']*plan['period_fee_minor']
    service_action(p,operation,case_id,'apply_return',remaining_principal_minor=principal,earned_fee_minor=fee)
    balance = principal+fee-plan['collected_minor']-plan['paid_minor']+plan['refunded_minor']
    if balance:
        service_action(p,operation,case_id,'pay_balance' if balance>0 else 'refund',amount_minor=abs(balance))
    service_action(p,operation,case_id,'close_plan')


def case_024(p):
    p.customer_facts('Please confirm exact supplier balances, total charges and installment requirements.',
        'Both suppliers must receive exactly what remains owed using current signed bank directions. Including the earlier return charge, total bank charges may be USD 75, with USD 50 retained throughout and no new funding. Pay the related new purchase on time, retain two earned installment-period fees, refund only actual overcollection after accepted returns, cancel future collection and unearned fees, and retain USD 150 in that separate wallet.')
    cases = service_context(p,'DIVERSE-contingent_net','PAYMENT-common','PAYMENT-payment_installment_return')
    delivery = cases['contingent_net']['id']
    installment = cases['payment_installment_return']['id']
    installment_start(p,installment)
    rows = service_rows(p,delivery)
    old = next(r for r in rows if r['kind']=='pending_remittance')
    certificate_invoice = next(r for r in rows if r['kind']=='net_invoice' and r['reference']!=old['invoice_ref'])
    beneficiary = next(r for r in rows if r['kind']=='net_beneficiary' and r['reference']==certificate_invoice['current_beneficiary_ref'])
    service_action(p,'propose_net_delivery',delivery,'send',invoice_id=certificate_invoice['id'],beneficiary_id=beneficiary['id'],route='protected',amount_minor=certificate_invoice['net_due_minor']-certificate_invoice['received_minor'])
    p.wait()
    rows = service_rows(p,delivery)
    old = next(r for r in rows if r['kind']=='pending_remittance')
    assert old['actual_credited_minor'] is not None
    invoice = next(r for r in rows if r['kind']=='net_invoice' and r['reference']==old['invoice_ref'])
    direction = next(r for r in rows if r['kind']=='payment_direction' and r['invoice_ref']==invoice['reference'])
    beneficiary = next(r for r in rows if r['kind']=='net_beneficiary' and r['reference']==direction['beneficiary_ref'])
    gross = invoice['net_due_minor']-invoice['received_minor']+min(invoice['possible_standard_fees_minor'])
    service_action(p,'propose_net_delivery',delivery,'send',invoice_id=invoice['id'],beneficiary_id=beneficiary['id'],route='standard',amount_minor=gross)
    installment_finish(p,installment)
    p.wait()
    invoice = p.read('service_records',invoice['id'])
    remaining = invoice['net_due_minor']-invoice['received_minor']
    if remaining:
        service_action(p,'propose_net_delivery',delivery,'topup',invoice_id=invoice['id'],beneficiary_id=beneficiary['id'],net_minor=remaining)
    service_rows(p,delivery)
    service_rows(p,installment)
    p.finish('Used actual traced credits and returned principal, current beneficiary directions and one protected delivery to discharge both exact net invoices within the total charge cap, while paying the new purchase and reconciling the accepted installment return, earned fees, real collections and future cancellation.')


def case_025(p):
    p.customer_facts('What future volumes, discounts, retained balances and service requirements should I use for this comparison?',
        'October has 50 domestic payments, 10 overseas and no conversions across our two operating accounts. November has 10 domestic, 50 overseas and 20 conversions. These are complete committed volumes. I own unused voucher LAUREL-AUTUMN-150. Compare both upcoming periods, keep both operating accounts, retire the former account by its recorded date, and retain USD 100. For the related bill, use the actual upgrade and usage, refund true overcollection, keep renewal active and USD 100 in that wallet, and avoid recall fees.')
    cases = service_context(p, 'DIVERSE-prospective_billing', 'PAYMENT-payment_subscription_proration')
    billing = cases['prospective_billing']['id']
    subscription = cases['payment_subscription_proration']['id']
    rows = service_rows(p, billing)
    source = next(r for r in rows if r['kind']=='external_correspondence')
    p.write('propose_service_inquiry', case_id=billing, record_id=source['id'])
    p.wait()
    arrangement = p.read('service_records', source['id'])['receipt']
    periods = sorted((r for r in rows if r['kind']=='billing_period'), key=lambda r:r['billing_minute'])
    plans = [r for r in rows if r['kind']=='subscription_plan']
    voucher = next(r for r in rows if r['kind']=='partner_voucher')
    forecast = [dict(domestic=50, overseas=10, fx=0), dict(domestic=10, overseas=50, fx=20)]
    alternatives = []
    for first in plans:
        for second in plans:
            for redemption in range(2):
                total = 0
                for i, plan in enumerate([first, second]):
                    variable = sum(forecast[i][k]*plan['rates_minor'][k] for k in forecast[i])
                    if periods[i]['billing_minute'] <= arrangement['close_by_minute'] and sum(forecast[i].values())>=plan['credit_minimum_transactions']:
                        variable = max(0, variable-plan['usage_credit_minor'])
                    fixed = plan['fixed_minor']
                    if i==redemption and periods[i]['billing_minute']<=arrangement['close_by_minute']:
                        fixed -= min(fixed,voucher['cap_minor'])
                    total += fixed+variable
                alternatives.append((total, first, second, redemption))
    _, first, second, redemption = min(alternatives, key=lambda x:x[0])
    for period, plan in zip(periods,[first,second]):
        service_action(p,'propose_subscription_election',billing,'select_plan',record_id=period['id'],plan_id=plan['id'])
    service_action(p,'propose_subscription_election',billing,'reserve_voucher',record_id=periods[redemption]['id'],code='LAUREL-AUTUMN-150')
    # The linked first downstream execution waits for a listed billing event.
    while p.call('assistant','get_clock')['minute']<periods[0]['billing_minute']:
        p.wait()
    subrows = service_rows(p, subscription)
    invoice = next(r for r in subrows if r['kind']=='subscription_invoice')
    assert invoice['usage_units'] is not None
    due = (invoice['old_monthly_minor']*invoice['old_days']+invoice['new_monthly_minor']*(invoice['days']-invoice['old_days']))//invoice['days'] + invoice['usage_units']*invoice['usage_unit_minor']
    service_action(p,'propose_payment_subscription_proration',subscription,'amend_invoice',amount_minor=due)
    if invoice['collected_minor']>due:
        service_action(p,'propose_payment_subscription_proration',subscription,'refund',amount_minor=invoice['collected_minor']-due)
    elif invoice['collected_minor']<due:
        service_action(p,'propose_payment_subscription_proration',subscription,'pay_balance',amount_minor=due-invoice['collected_minor'])
    while p.call('assistant','get_clock')['minute']<periods[-1]['billing_minute']:
        p.wait()
    legacy = next(r for r in rows if r.get('reference')==arrangement['retired_account'])
    service_action(p,'propose_subscription_election',billing,'close_account',record_id=legacy['id'])
    service_rows(p,billing)
    service_rows(p,subscription)
    p.finish('Applied the lowest combined upcoming subscription charges using the disclosed forecast and owned voucher, retained the operating services and reserves, retired the former partner account on time, corrected the actual upgraded invoice and refunded overcollection while keeping renewal active.')


def marketplace_settle(p, case_id, final=False):
    rows = service_rows(p,case_id)
    operation = 'propose_payment_marketplace_split_refund'
    for seller in (r for r in rows if r['kind']=='seller_allocation' and r['accepted_return_minor'] is not None):
        entitlement = (seller['gross_minor']-seller['accepted_return_minor'])*(10000-seller['commission_bp'])//10000
        paid = seller['transferred_minor']+seller['additional_paid_minor']-seller['reversed_minor']
        if paid>entitlement:
            service_action(p,operation,case_id,'reverse_seller',seller_id=seller['id'],amount_minor=paid-entitlement)
        elif paid<entitlement:
            service_action(p,operation,case_id,'pay_seller',seller_id=seller['id'],amount_minor=entitlement-paid)
    if final:
        refund = next(r for r in rows if r['kind']=='buyer_refund')
        assert refund['status'] in ('SETTLED','FAILED')
        total = sum(r['accepted_return_minor'] for r in rows if r['kind']=='seller_allocation')
        amount = total-refund['paid_minor']-refund['manual_paid_minor']
        if amount:
            service_action(p,operation,case_id,'refund_buyer',amount_minor=amount)


def case_026(p):
    from itertools import combinations
    p.customer_facts('Please confirm the store, conversion amount, invoice, financing permissions and refund requirements.',
        'Use Juniper Home international on Market Bridge, not the UK outlet. Convert USD 800 to our usual CNY account and finish the packaging invoice by its deadline. Finance receivables if needed but keep Orion free throughout and USD 100 in this wallet. There is no extra money. For the combined order refund exactly accepted returns without duplicating the pending refund, and settle each seller on time; only the returned-item seller bears a reversal.')
    cases = service_context(p,'DIVERSE-reconciled_sync','PAYMENT-payment_marketplace_split_refund')
    sync = cases['reconciled_sync']['id']
    marketplace = cases['payment_marketplace_split_refund']['id']
    marketplace_settle(p,marketplace)
    rows = service_rows(p,sync)
    source = next(r for r in rows if r['kind']=='external_correspondence')
    p.write('propose_service_inquiry',case_id=sync,record_id=source['id'])
    for stream in (r for r in rows if r['kind']=='sync_stream' and r['shop']=='MAIN'):
        if not stream['granted']:
            service_action(p,'propose_sales_recovery',sync,'grant_stream',record_id=stream['id'])
        last = max(r['sequence'] for r in rows if r['kind']=='source_event' and r['shop']==stream['shop'] and r['stream']==stream['stream'])
        service_action(p,'propose_sales_recovery',sync,'import_window',record_id=stream['id'],after_cursor=0,through_cursor=last)
    pending = next(r for r in rows if r['kind']=='supplier_transfer')
    for _ in range(8):
        p.wait()
        marketplace_settle(p,marketplace)
        pending = p.read('service_records',pending['id'])
        if pending['status']!='PROCESSING':
            break
    terms = p.read('service_records',source['id'])['receipt']
    rows = service_rows(p,sync)
    current = p.read('service_cases',sync)
    invoice = next(r for r in rows if r['kind']=='sync_invoice')
    due = invoice['amount_minor']-invoice['paid_minor']
    receivables = [r for r in rows if r['kind']=='sales_receivable' and r['shop']==terms['target_shop'] and r['reference']!=terms['protected_receivable'] and not r['existing_encumbrance_minor'] and r['advance_bp']>0]
    possibilities = []
    for count in range(len(receivables)+1):
        for selected in combinations(receivables,count):
            advance = sum(r['face_minor']*r['advance_bp']//10000 for r in selected)
            allowance = current['state']['available_quota_minor']-sum(r['face_minor'] for r in selected)
            if allowance>=terms['withdrawal_minor'] and current['cash_minor']+advance>=due+terms['withdrawal_minor']+terms['minimum_cash_reserve_minor']:
                possibilities.append((advance,selected))
    _, selected = min(possibilities,key=lambda x:x[0])
    for receivable in selected:
        service_action(p,'propose_sales_recovery',sync,'finance',record_id=receivable['id'])
    recipient = next(r for r in rows if r['kind']=='sync_recipient' and r['reference']==terms['withdrawal_recipient'])
    service_action(p,'propose_sales_recovery',sync,'withdraw',record_id=recipient['id'],amount_minor=terms['withdrawal_minor'])
    service_action(p,'propose_sales_recovery',sync,'pay_supplier',record_id=invoice['id'],amount_minor=due)
    marketplace_settle(p,marketplace,final=True)
    p.read('service_cases',sync)
    service_rows(p,marketplace)
    p.finish('Replayed complete signed source events with canonical deduplication for the intended store, kept Orion unassigned, financed only the feasible whole invoice, converted the exact mandate, reconciled the actual prior transfer and paid the supplier, and completed buyer/seller adjustments without duplicate refund or cross-seller reversal.')


def payroll_period(p, case_id, period, terms):
    rows = service_rows(p,case_id)
    for wage in (r for r in rows if r['kind']=='payroll_obligation' and r['period']==period):
        current = service_rows(p,case_id)
        employee = next(r for r in current if r['kind']=='payroll_employee' and r['reference']==wage['employee'])
        orders = [r for r in current if r['kind']=='attachment_order' and r['employee']==wage['employee']]
        notices = [r for r in current if r['kind']=='court_notice']
        disposable = wage['gross_minor']-wage['tax_minor']
        capacity = max(0,disposable-wage['protected_disposable_minor'])
        allocations = []
        for category, cap in [('SUPPORT',terms['support_cap_bp']),('ORDINARY',terms['ordinary_aggregate_cap_bp'])]:
            remaining_cap = disposable*cap//10000
            for order in sorted((r for r in orders if r['category']==category),key=lambda r:(r['priority_day'],r['reference'])):
                if any(n.get('decision')=='STAY' and n['order']==order['reference'] and period>=n['effective_from_period'] for n in notices):
                    continue
                amount = min(capacity,remaining_cap,order['principal_minor']-order['historical_paid_minor']-order['paid_minor'])
                if amount>0:
                    allocations.append((order,amount))
                    capacity -= amount
                    remaining_cap -= amount
        operation = 'propose_payroll_remittance'
        for order, amount in allocations:
            service_action(p,operation,case_id,'pay_attachment',record_id=wage['id'],order_id=order['id'],amount_minor=amount)
        service_action(p,operation,case_id,'pay_tax',record_id=wage['id'],amount_minor=wage['tax_minor'])
        service_action(p,operation,case_id,'pay_employee',record_id=wage['id'],amount_minor=disposable+wage['expense_repayment_minor']-sum(a for _,a in allocations),bank_version=employee['bank_version'])


def case_027(p):
    p.customer_facts('Please confirm shipment, payroll and retained-funds requirements.',
        'Pay only dispatched goods in both shipments and the courier on time, release unused authorizations, and retain USD 50 throughout. Pay both payroll runs, taxes, proper court creditors and expense repayments on time, retain USD 100 for operations, and follow the actual court decision rather than treating an application as a stay.')
    cases = service_context(p,'DIVERSE-dated_payroll','PAYMENT-common','PAYMENT-payment_split_capture')
    shipment = cases['payment_split_capture']['id']
    payroll = cases['dated_payroll']['id']
    operation = 'propose_payment_split_capture'
    rows = service_rows(p,shipment)
    bill = next(r for r in rows if r['kind']=='bill')
    service_action(p,operation,shipment,'pay_bill',record_id=bill['id'],amount_minor=bill['amount_minor'])
    authorization = next(r for r in rows if r['kind']=='capture_authorization')
    first = next(r for r in rows if r['kind']=='fulfillment_line' and r['fulfilled'])
    service_action(p,operation,shipment,'capture',authorization_id=authorization['id'],line_id=first['id'],amount_minor=first['final_minor'])
    source = next(r for r in service_rows(p,payroll) if r['kind']=='external_correspondence')
    p.write('propose_service_inquiry',case_id=payroll,record_id=source['id'])
    second = next(r for r in rows if r['kind']=='fulfillment_line' and not r['fulfilled'])
    for _ in range(5):
        p.wait()
        second = p.read('service_records',second['id'])
        if second['fulfilled']:
            break
    service_action(p,operation,shipment,'capture',authorization_id=authorization['id'],line_id=second['id'],amount_minor=second['final_minor'])
    authorization = p.read('service_records',authorization['id'])
    if authorization['remaining_minor']:
        service_action(p,operation,shipment,'release',authorization_id=authorization['id'],amount_minor=authorization['remaining_minor'])
    terms = p.read('service_records',source['id'])['receipt']
    payroll_period(p,payroll,1,terms)
    future = [r for r in service_rows(p,payroll) if r['kind']=='payroll_obligation' and r['period']==2]
    required = sum(r['gross_minor']+r['expense_repayment_minor'] for r in future)+terms['minimum_cash_reserve_minor']
    for _ in range(10):
        current = p.read('service_cases',payroll)
        notices = [r for r in service_rows(p,payroll) if r['kind']=='court_notice']
        if current['cash_minor']>=required and all(n['decision'] is not None for n in notices):
            break
        p.wait()
    payroll_period(p,payroll,2,terms)
    while any(r['cleared_minor']+r['cash_paid_minor']!=r['final_minor'] for r in service_rows(p,shipment) if r['kind']=='fulfillment_line'):
        p.wait()
    p.finish('Paid courier and both actually dispatched shipments using the valid card commitment, released unused authorization, and paid both complete payroll runs with current employee details, actual court decisions and correct attachment priorities while retaining both cash reserves.')


def proportional(total, weights):
    denominator = sum(weights.values())
    result = {key:total*value//denominator for key,value in weights.items()}
    order = sorted(weights, key=lambda key:(-(total*weights[key]%denominator), key))
    for key in order[:total-sum(result.values())]:
        result[key] += 1
    return result


def settle_acquirer(p, case_id):
    rows = service_rows(p,case_id)
    operation = 'propose_payment_acquirer_batch_close'
    for batch in (r for r in rows if r['kind']=='acquirer_batch' and not r['posted'] and r['status']=='FINAL'):
        receipts = [r for r in rows if r['kind']=='acquirer_receipt' and r['bank_ref']==batch['batch_ref'] and r['status']=='SETTLED' and not r['used']]
        if not receipts:
            continue
        receipt = receipts[0]
        fields = {key:batch[key] for key in ('gross_minor','refund_minor','fee_minor','carry_minor','reserve_delta_minor')}
        assert fields['gross_minor']-fields['refund_minor']-fields['fee_minor']+fields['carry_minor']+fields['reserve_delta_minor']==receipt['amount_minor']
        service_action(p,operation,case_id,'post_batch',batch_id=batch['id'],bank_id=receipt['id'],**fields)
        for invoice in (r for r in rows if r['kind']=='merchant_invoice' and r['batch_ref']==batch['batch_ref']):
            due = invoice['sales_minor']-invoice['refund_minor']-invoice['commission_minor']-invoice['paid_minor']
            service_action(p,operation,case_id,'pay_merchant',invoice_id=invoice['id'],amount_minor=due)


def case_028(p):
    p.customer_facts('Please confirm your merchant settlement and payroll requirements and retained funds.',
        'Reconcile real card deposits once and pay each merchant its actual proceeds by the agreed deadline. Pay both payroll runs, tax, proper court deductions and expenses on time using the actual court decision and current bank details. Retain USD 100 in the payroll wallet and do not pay anyone twice.')
    cases = service_context(p,'DIVERSE-dated_payroll','PAYMENT-payment_acquirer_batch_close')
    acquirer = cases['payment_acquirer_batch_close']['id']
    payroll = cases['dated_payroll']['id']
    settle_acquirer(p,acquirer)
    source = next(r for r in service_rows(p,payroll) if r['kind']=='external_correspondence')
    p.write('propose_service_inquiry',case_id=payroll,record_id=source['id'])
    p.wait()
    terms = p.read('service_records',source['id'])['receipt']
    payroll_period(p,payroll,1,terms)
    future = [r for r in service_rows(p,payroll) if r['kind']=='payroll_obligation' and r['period']==2]
    required = sum(r['gross_minor']+r['expense_repayment_minor'] for r in future)+terms['minimum_cash_reserve_minor']
    for _ in range(10):
        settle_acquirer(p,acquirer)
        current = p.read('service_cases',payroll)
        notices = [r for r in service_rows(p,payroll) if r['kind']=='court_notice']
        if current['cash_minor']>=required and all(n['decision'] is not None for n in notices):
            break
        p.wait()
    payroll_period(p,payroll,2,terms)
    assert all(r['posted'] for r in service_rows(p,acquirer) if r['kind']=='acquirer_batch')
    p.finish('Reconciled both actual bank batch credits once with final fees and signed carry/reserve values, paid all merchant proceeds on time, and paid both payroll runs with correct court priorities, current employee details and continuous operating reserves.')


def case_029(p):
    p.customer_facts('Please confirm group ownership and refund goals, including protected currency balances.',
        'Complete both group purchases at their group prices, return withdrawing participants their contributions, and divide remaining savings proportionally among continuing contributors. Keep the groups separate and ask for no extra money. Finish current cancelled-order refunds in the currencies buyers originally paid; keep USD 20 and EUR 10 throughout, without extra funding or collecting refunds back from buyers.')
    cases = service_context(p,'DIVERSE-origin_currency_refunds','PAYMENT-payment_group_purchase_commitment')
    group_case = cases['payment_group_purchase_commitment']['id']
    refund_case = cases['origin_currency_refunds']['id']
    operation = 'propose_payment_group_purchase_commitment'
    rows = service_rows(p,group_case)
    groups = [r for r in rows if r['kind']=='purchase_group']
    for group in groups:
        people = [r for r in rows if r['kind']=='group_contribution' and r['group']==group['reference'] and r['received_minor'] and not r['withdrawn']]
        if len(people)>=group['minimum_people'] and sum(r['received_minor'] for r in people)>=group['minimum_contribution_minor']:
            service_action(p,operation,group_case,'commit_group',group_id=group['id'],offer='GROUP')
    # Fresh downstream proposals are created only after the first group execution.
    rows = service_rows(p,refund_case)
    for purchase in (r for r in rows if r['kind']=='refund_purchase' and r['due_minute']==0):
        credited = sum(r['credited_minor'] for r in rows if r['kind']=='physical_refund' and r['purchase_ref']==purchase['reference'] and r['status']=='POSTED')
        wallet = next(r for r in rows if r['kind']=='refund_wallet' and r['currency']==purchase['charge_currency'])
        service_action(p,'propose_origin_refund',refund_case,'refund',purchase_id=purchase['id'],account_id=wallet['id'],currency=purchase['charge_currency'],amount_minor=purchase['charge_minor']-credited)
    while True:
        p.wait()
        rows = service_rows(p,refund_case)
        if all(r['status']!='IN_FLIGHT' for r in rows if r['kind']=='physical_refund'):
            break
    wallets = {r['reference']:r for r in rows if r['kind']=='refund_wallet'}
    for purchase in (r for r in rows if r['kind']=='refund_purchase' and r['due_minute']>0):
        remaining = purchase['charge_minor']-sum(r['credited_minor'] for r in rows if r['kind']=='physical_refund' and r['purchase_ref']==purchase['reference'] and r['status'] in ('POSTED','FINAL'))
        routes = sorted((r for r in purchase['refund_routes'] if r['currency']==purchase['charge_currency']),key=lambda r:wallets[r['account']]['currency']!=purchase['charge_currency'])
        for route in routes:
            wallet = p.read('service_records', wallets[route['account']]['id'])
            floor = 1000 if wallet['currency']=='EUR' else 2000
            capacity = max(0,wallet['cash_minor']-floor)*route['denominator']//route['numerator']
            amount = min(remaining,capacity)
            if amount:
                service_action(p,'propose_origin_refund',refund_case,'refund',purchase_id=purchase['id'],account_id=wallet['id'],currency=purchase['charge_currency'],amount_minor=amount)
                remaining -= amount
        assert remaining == 0
    for _ in range(5):
        rows = service_rows(p,group_case)
        ready = True
        for group in (r for r in rows if r['kind']=='purchase_group' and not r['committed']):
            people = [r for r in rows if r['kind']=='group_contribution' and r['group']==group['reference'] and r['received_minor'] and not r['withdrawn']]
            if len(people)>=group['minimum_people'] and sum(r['received_minor'] for r in people)>=group['minimum_contribution_minor']:
                service_action(p,operation,group_case,'commit_group',group_id=group['id'],offer='GROUP')
            else:
                ready = False
        if ready:
            break
        p.wait()
    rows = service_rows(p,group_case)
    for group in (r for r in rows if r['kind']=='purchase_group'):
        service_action(p,operation,group_case,'pay_merchant',group_id=group['id'],amount_minor=group['price_minor']-group['merchant_paid_minor'])
        contributors = [r for r in rows if r['kind']=='group_contribution' and r['group']==group['reference']]
        continuing = {r['reference']:r['received_minor'] for r in contributors if not r['withdrawn']}
        savings = sum(continuing.values())-group['price_minor']
        refunds = proportional(savings,continuing)
        for person in contributors:
            amount = person['received_minor'] if person['withdrawn'] else refunds[person['reference']]
            if amount:
                service_action(p,operation,group_case,'refund_participant',participant_id=person['id'],amount_minor=amount)
    service_rows(p,group_case)
    service_rows(p,refund_case)
    p.finish('Preserved both group-price commitments, settled each group from its own contributions and refunded withdrawal and proportional savings, and completed only the remaining original-currency refunds after real pending outcomes while preserving both currency reserves.')


def expense_balances(rows, meal_cap):
    profiles = {r['reference']:r['person'] for r in rows if r['kind']=='employee_profile'}
    accounts = {r['reference']:r for r in rows if r['kind']=='funding_account'}
    contexts = {r['booking_reference']:r for r in rows if r['kind']=='travel_context'}
    amounts = {r['reference']:0 for r in rows if r['kind']=='employee'}
    groups = {}
    owners = {}
    for receipt in (r for r in rows if r['kind']=='expense_receipt' and r['receipt_status']=='FINAL'):
        context = contexts[receipt['booking_reference']]
        if not context['registered_business_purpose'] or receipt['item_kind'] not in ('lodging','meals','taxi','meeting'):
            continue
        if receipt['item_kind']=='meeting' and not context['external_attendees']:
            continue
        key = (profiles[receipt['profile']],receipt['expense_day'],receipt['item_kind'])
        group = groups.setdefault(key,{})
        for leg in (r for r in rows if r['kind']=='funding_leg' and r['receipt']==receipt['reference'] and r['posting_status']=='SETTLED'):
            refunded = sum(r['posted_minor'] for r in rows if r['kind']=='merchant_refund' and r['payment_reference']==leg['reference'] and r['status']=='SETTLED')
            group[leg['reference']] = leg['amount_minor']-refunded
            account = accounts[leg['account']]
            owners[leg['reference']] = account['owner'] if account['funding_type']=='PERSONAL' else None
    for key, legs in groups.items():
        counted = min(sum(legs.values()),meal_cap) if key[2]=='meals' else sum(legs.values())
        shares = proportional(counted,legs)
        for ref, share in shares.items():
            if owners[ref]:
                amounts[owners[ref]] += share
    return {r['id']:amounts[r['reference']]-r['advance_minor']-r['prior_reimbursement_minor']-r['reimbursed_minor']+r['recovered_minor'] for r in rows if r['kind']=='employee'}


def settle_expenses(p, case_id, terms, early):
    rows = service_rows(p,case_id)
    balances = expense_balances(rows,terms['meal_cap_minor'])
    for employee in (r for r in rows if r['kind']=='employee' and (r['due_minute']<terms['final_review_minute'])==early):
        value = balances[employee['id']]
        if value:
            service_action(p,'propose_expense_reconciliation',case_id,'reimburse' if value>0 else 'recover_advance',employee_id=employee['id'],amount_minor=abs(value),bank_version=employee['bank_version'])


def case_030(p):
    p.customer_facts('Please confirm settlement goals, spending reserves and use of current records for both matters.',
        'Pay the right cheque holders without paying either invoice twice, and pay the inspection bill on time. Retain USD 50 in that wallet. Reconcile actual business expenses, personal funding, refunds, prior reimbursements and travel advances for each employee separately by their deadlines, retaining USD 100 for operations.')
    cases = service_context(p,'DIVERSE-reconciled_expenses','PAYMENT-common','PAYMENT-payment_cheque_stop_and_replacement')
    cheque = cases['payment_cheque_stop_and_replacement']['id']
    expense = cases['reconciled_expenses']['id']
    operation = 'propose_payment_cheque_stop_and_replacement'
    rows = service_rows(p,cheque)
    bill = next(r for r in rows if r['kind']=='bill')
    service_action(p,operation,cheque,'pay_bill',record_id=bill['id'],amount_minor=bill['amount_minor'])
    issued = next(r for r in rows if r['kind']=='electronic_cheque' and r['status']=='ISSUED')
    service_action(p,operation,cheque,'request_stop',cheque_id=issued['id'])
    source = next(r for r in service_rows(p,expense) if r['kind']=='external_correspondence')
    p.write('propose_service_inquiry',case_id=expense,record_id=source['id'])
    p.wait()
    terms = p.read('service_records',source['id'])['receipt']
    settle_expenses(p,expense,terms,early=True)
    for _ in range(5):
        rows = service_rows(p,cheque)
        if all(r.get('held_minor',0)==0 for r in rows if r['kind']=='electronic_cheque'):
            break
        p.wait()
    for invoice in (r for r in rows if r['kind']=='cheque_invoice'):
        due = invoice['face_minor']-invoice['paid_minor']
        if due:
            service_action(p,operation,cheque,'replacement_payment',invoice_id=invoice['id'],payee=invoice['current_holder'],amount_minor=due)
    while p.call('assistant','get_clock')['minute']<terms['final_review_minute']:
        p.wait()
    settle_expenses(p,expense,terms,early=False)
    assert all(value==0 for value in expense_balances(service_rows(p,expense),terms['meal_cap_minor']).values())
    p.finish('Paid the inspection fee, reconciled actual stopped/presented cheques and returned holds before paying only each lawful holder’s remaining invoice, and settled every employee’s actual personally funded eligible expenses, refunds and advances within the dates and cash reserves.')


def case_031(p):
    inspect(p, ['PX-A-OWNER', 'PX-A-D31', 'PX-A-R-CUSTODY-ONBOARDING', 'PX-A-R-CUSTODY-CASH', 'PX-A-R-RETURN-WORKING-CASH'],
            ['xp_a_incoming', 'xp_a_quarantine_disputes', 'xp_a_reasoning_contracts', 'xp_a_custody_services', 'xp_a_invoices', 'xp_accounts'])
    for f in p.call('user', 'list_my_files'):
        if f['purpose'] in ('origin_proof', 'escrow_direction'):
            p.call('user', 'upload_file', file_id=f['id'], target_id=f['target_id'], purpose=f['purpose'])
    incoming = p.one('xp_a_incoming')
    contract = p.one('xp_a_reasoning_contracts')
    p.write('a_investigate_incoming_owner', incoming_id=incoming['id'])
    p.write('a_submit_quarantine_escrow_direction', incoming_id=incoming['id'])
    services = p.rows('xp_a_custody_services')
    review = min((s for s in services if s['stage'] == 'REVIEW'), key=lambda s:s['delay_minutes'])
    p.write('a_order_trustee_review', contract_id=contract['id'], service_id=review['id'])
    invoice = p.read('xp_a_invoices', contract['normal_invoice_id'])
    p.write('a_pay_business_invoice', invoice_id=invoice['id'], recipient_id=invoice['recipient_id'], amount_minor=invoice['amount_minor'], payment_key=invoice['id']+'-original')
    while p.call('assistant', 'get_clock')['minute'] < review['delay_minutes']:
        p.wait()
    activation = min((s for s in p.rows('xp_a_custody_services') if s['stage'] == 'ACTIVATION'), key=lambda s:s['fee_minor'])
    p.write('a_activate_dispute_custody', contract_id=contract['id'], service_id=activation['id'])
    ready = p.call('assistant', 'get_clock')['minute'] + activation['delay_minutes']
    while p.call('assistant', 'get_clock')['minute'] < ready:
        p.wait()
    dispute = p.one('xp_a_quarantine_disputes')
    print('FINAL DISPUTE', dispute, flush=True)
    p.write('a_partition_quarantined_funds', incoming_id=incoming['id'], return_minor=incoming['amount_minor']-dispute['disputed_minor'], escrow_minor=dispute['disputed_minor'], claim_minor=0, trustee_id=dispute['authorized_trustee_id'])
    p.finish('Returned undisputed principal to its original sender, deposited the signed disputed security with the authorized active trustee, and paid the ordinary supplier from operating cash within both deadlines.')


def case_032(p):
    inspect(p, ['PX-A-OWNER', 'PX-A-RECALL-SALE', 'PX-A-BUYER-COLLECTION-CALENDAR', 'PX-A-RETURN-VALUATION'],
            ['xp_a_incoming', 'xp_a_recall_sales', 'xp_a_settlement_terms', 'xp_a_buyer_collection_services'])
    for f in p.call('user', 'list_my_files'):
        if f['purpose'] in ('contract_proof', 'returned_goods'):
            p.call('user', 'upload_file', file_id=f['id'], target_id=f['target_id'], purpose=f['purpose'])
    incoming = p.one('xp_a_incoming')
    sale = p.one('xp_a_recall_sales')
    terms = p.one('xp_a_settlement_terms')
    p.write('a_submit_receipt_claim', incoming_id=incoming['id'], position='RETAIN')
    p.write('a_review_sale_return', sale_id=sale['id'])
    services = p.rows('xp_a_buyer_collection_services')
    fast = min(services, key=lambda s:s['delay_minutes'])
    booking = p.write('a_book_buyer_collection', service_id=fast['id'], capacity_minor=terms['first_amount_minor'])
    for _ in range(20):
        incoming = p.read('xp_a_incoming', incoming['id'])
        sale = p.read('xp_a_recall_sales', sale['id'])
        if incoming.get('decision_final') and 'authorized_credit_minor' in sale:
            break
        p.wait()
    p.write('a_dispose_incoming_balance', incoming_id=incoming['id'], disposition=incoming['allowed_dispositions'][0], decision_version=incoming['decision_version'])
    p.write('a_issue_sale_credit', sale_id=sale['id'], amount_minor=sale['authorized_credit_minor'])
    remaining = sale['face_minor']-sale['authorized_credit_minor']
    first = min(remaining, terms['first_amount_minor'])
    p.write('a_collect_remaining_sale', sale_id=sale['id'], booking_id=booking['id'], amount_minor=first)
    if remaining > first:
        regular = min(services, key=lambda s:s['booking_fee_minor'])
        other = p.write('a_book_buyer_collection', service_id=regular['id'], capacity_minor=remaining-first)
        p.write('a_collect_remaining_sale', sale_id=sale['id'], booking_id=other['id'], amount_minor=remaining-first)
    for _ in range(10):
        receipts = p.rows('xp_a_replacement_receipts')
        for receipt in receipts:
            if not receipt.get('applied'):
                print('RECEIPT', receipt, flush=True)
                p.write('a_apply_replacement_receipt', receipt_id=receipt['id'], sale_id=sale['id'])
        current = p.read('xp_a_recall_sales', sale['id'])
        if current['paid_minor'] == remaining:
            break
        p.wait()
    assert current['paid_minor'] == remaining
    p.finish('Respected the final bank recall, credited only reviewed returned goods, and received and applied the retained-goods balance within both collection milestones and the fee limit.')


def case_033(p):
    inspect(p, ['PX-A-RECEIPTS', 'PX-A-D33', 'PX-A-R-CREDIT-NETTING', 'PX-A-R-CREDIT-CASH', 'PX-A-R-RETURN-WORKING-CASH'],
            ['xp_a_bank_receipts', 'xp_a_supplier_payables', 'xp_a_reasoning_contracts', 'xp_a_supplier_credit_notes', 'xp_a_invoices', 'xp_accounts'])
    p.call('user', 'list_my_files')
    contract = p.one('xp_a_reasoning_contracts')
    p.write('a_request_supplier_credit_confirmation', contract_id=contract['id'])
    while p.call('assistant', 'get_clock')['minute'] < contract['credit_confirmation_minute']:
        p.wait()
    receipts = p.rows('xp_a_bank_receipts')
    for invoice in p.rows('xp_a_invoices'):
        latest = max((r for r in receipts if r['invoice_id']==invoice['id']), key=lambda r:r['bank_sequence'])
        p.write('a_project_bank_receipts', invoice_id=invoice['id'], projection='CAUSAL')
        p.write('a_post_bank_receipt_to_payables', invoice_id=invoice['id'], receipt_id=latest['id'])
    returned = next(x for x in p.rows('xp_a_supplier_payables') if x['open_minor']>0)
    notes = p.rows('xp_a_supplier_credit_notes')
    print('CONFIRMED NOTES', notes, flush=True)
    refund = min(notes, key=lambda n:n['refund_services']['EXPRESS']['fee_minor'])
    applied = next(n for n in notes if n['id'] != refund['id'])
    p.write('a_apply_supplier_credit_note', credit_note_id=applied['id'], invoice_id=returned['source_id'])
    p.write('a_redeem_supplier_credit_note', credit_note_id=refund['id'], service='EXPRESS')
    invoice = p.read('xp_a_invoices', returned['source_id'])
    p.write('a_pay_business_invoice', invoice_id=invoice['id'], recipient_id=invoice['recipient_id'], amount_minor=invoice['amount_minor'], payment_key=invoice['id']+'-replacement')
    ready = p.call('assistant','get_clock')['minute'] + refund['refund_services']['EXPRESS']['delay_minutes']
    while p.call('assistant','get_clock')['minute'] < ready:
        p.wait()
    p.rows('xp_a_supplier_credit_notes')
    p.write('a_deliver_supplier_payable_statement', payable_ids=[x['id'] for x in p.rows('xp_a_supplier_payables')])
    p.finish('Applied causal bank corrections, preserved the settled original payment, realized both nonstacking credits by the deadline, paid only the reopened net invoice, and delivered the final payable statement.')


def case_040(p):
    p.docs('PX-B-40', 'PX-BR-PROOF-VERSIONS', 'PX-BR-PROOF-LINEAGE')
    request = p.one('xp_b_evidence_requests')
    access = p.one('xp_b_proof_access')
    schedule = p.one('xp_b_reasoning_proof_versions')
    seal = p.write('purchase_payment_proof_seal', schedule_id=schedule['id'], product_id='flexible')
    p.write('select_payment_proof_rendering', schedule_id=schedule['id'], seal_id=seal['id'], rendering_id='transfer_advice')
    first = p.write('create_bank_evidence', evidence_request_id=request['id'], kind='receipt', field_names=request['required_fields'], format='pdf')
    p.write('deliver_bank_evidence', evidence_id=first['id'])
    p.write('verify_bank_proof_recipient', record_id=access['id'], choice='registered_email')
    p.wait()
    request = p.read('xp_b_evidence_requests', request['id'])
    final = p.write('create_bank_evidence', evidence_request_id=request['id'], kind='receipt', field_names=request['required_fields'], format='pdf')
    p.write('deliver_bank_evidence', evidence_id=final['id'])
    p.write('set_bank_proof_access_scope', record_id=access['id'], choice='B-040-NAMED')
    p.write('issue_scoped_bank_proof_link', record_id=access['id'], choice=final['id'])
    p.wait()
    p.read('xp_b_proof_access', access['id'])
    p.write('revoke_delivered_bank_proof_link', record_id=access['id'])
    p.finish('Delivered preliminary and final sealed single-payment proofs, confirmed Buyer One read the final proof, and revoked the named-only link without disclosing unrelated banking information.')


def case_041(p):
    inspect(p, ['PX-B-41', 'PX-BR-RECOVERY-ADVANCE', 'PX-BR-RECOVERY-INSTRUCTIONS', 'PX-BR-RECOVERY-MANDATES', 'IFACE-RECOVERY-SUPPLIER-ADVANCE'],
            ['xp_b_access_profiles', 'xp_b_reasoning_accepted_advances', 'xp_b_reasoning_recovery', 'xp_b_recovery_handoffs', 'xp_b_recovery_instructions', 'xp_b_secure_obligations'])
    files = p.call('user', 'list_my_files')
    handoff = p.one('xp_b_recovery_handoffs')
    profile = p.one('xp_b_access_profiles')
    schedule = p.one('xp_b_reasoning_recovery')
    advance = max(p.rows('xp_b_reasoning_accepted_advances'), key=lambda x: x['nominal_minor'])
    p.write('release_accepted_supplier_advance', advance_id=advance['id'])
    identity = next(x for x in files if x['purpose'] == 'identity_recovery' and x['content']['identity_revision'] == handoff['required_identity_revision'])
    p.call('user', 'upload_file', file_id=identity['id'], target_id=profile['id'], purpose='identity_recovery')
    p.write('recover_access_channel', profile_id=profile['id'], channel='payment')
    for _ in range(10):
        actual = p.read('xp_b_reasoning_accepted_advances', advance['id'])
        if actual['status'] == 'settled':
            break
        p.wait()
    p.write('apply_supplier_advance_receipt', advance_id=advance['id'])
    instruction = next(x for x in p.rows('xp_b_recovery_instructions') if x['obligation_id'] == schedule['obligation_id'])
    p.write('amend_held_supplier_balance', instruction_id=instruction['id'])
    for _ in range(10):
        profile = p.read('xp_b_access_profiles', profile['id'])
        if profile['payment_status'] == 'active':
            break
        p.wait()
    handoff = p.read('xp_b_recovery_handoffs', handoff['id'])
    obligation = p.read('xp_b_secure_obligations', schedule['obligation_id'])
    minute = p.call('assistant', 'get_clock')['minute']
    candidates = [(desk['fee_minor'], name, desk) for name, desk in handoff['desks'].items()
                  if desk['permission'] == 'execute' and desk['maximum_invoice_balance_minor'] >= obligation['amount_minor']
                  and max(minute + desk['delay'], desk['start']) <= min(desk['end'], schedule['final_deadline'])]
    _, desk_id, desk = min(candidates)
    p.write('select_recovered_payment_executor', handoff_id=handoff['id'], desk_id=desk_id)
    p.write('migrate_recovery_payment_instruction', handoff_id=handoff['id'], instruction_id=instruction['id'])
    p.write('bind_recovered_payment_instruction', handoff_id=handoff['id'], instruction_id=instruction['id'])
    for _ in range(10):
        current = p.read('xp_b_recovery_handoffs', handoff['id'])
        if current.get('executor_ready') and p.call('assistant', 'get_clock')['minute'] >= desk['start']:
            break
        p.wait()
    challenge = p.write('create_payment_challenge', profile_id=profile['id'], obligation_id=obligation['id'], method='registered_email')
    p.write('execute_authenticated_payment', obligation_id=obligation['id'], profile_id=profile['id'], credential_version=profile['payment_version'], challenge_id=challenge['id'])
    p.write('complete_recovery_execution_handover', handoff_id=handoff['id'])
    p.finish('Delivered the actual accepted advance by its deadline, restored only the payment channel using current signed identity evidence, reconciled the received principal and amended the held invoice balance, used an authorized in-limit ready desk and a current bound challenge, paid the exact balance on time, and closed temporary access while preserving the owner channel and unrelated quotation.')


def case_042(p):
    inspect(p, ['PX-B-42', 'PX-BR-INCIDENT-FINALITY', 'PX-BR-INCIDENT-CONTINUITY', 'IFACE-INCIDENT-SUPPLIER-REPLACEMENT'],
            ['xp_b_credentials', 'xp_b_credential_continuity', 'xp_b_reasoning_incidents', 'xp_b_security_transfers'])
    files = p.call('user', 'list_my_files')
    preferences = next(x['content'] for x in files if x['purpose'] == 'customer_preferences')
    incident = p.one('xp_b_reasoning_incidents')
    continuity = p.one('xp_b_credential_continuity')
    credentials = p.rows('xp_b_credentials')
    exposed = next(x for x in credentials if x['family'] == preferences['compromised_family'])
    safe = next(x for x in credentials if x['family'] != preferences['compromised_family'])
    p.write('freeze_independent_standing_payment', record_id=continuity['id'])
    p.write('revoke_access_credential', credential_id=exposed['id'], scope='family')
    for transfer_id in incident['suspect_transfer_ids'] + [incident['legitimate_transfer_id']]:
        p.write('resolve_queued_transfer', transfer_id=transfer_id, action='cancel')
    p.write('send_incident_supplier_replacement', incident_id=incident['id'], credential_id=safe['id'], service='regular')
    p.write('cancel_independent_standing_payment', record_id=continuity['id'])
    p.write('audit_payment_callback_destination', record_id=continuity['id'])
    for _ in range(10):
        continuity = p.read('xp_b_credential_continuity', continuity['id'])
        if continuity.get('callback_audited'):
            break
        p.wait()
    supplier_endpoint = next(key for key, entity in continuity['callback_endpoints'].items() if entity == preferences['legitimate_purpose'])
    p.write('rotate_supplier_payment_callback', record_id=continuity['id'], choice=supplier_endpoint)
    for _ in range(10):
        deliveries = p.rows('xp_b_incident_supplier_deliveries')
        if deliveries:
            break
        p.wait()
    p.write('deliver_supplier_payment_callback', record_id=continuity['id'])
    p.finish('Revoked the entire exposed integration family and explicitly cancelled both unauthorized instructions and the original pending supplier instruction. Cancelled the independent standing authority, retained the safe finance credential, delivered one regular replacement before the supplier deadline, and sent its genuine receipt through the audited rotated supplier callback within the cash budget.')


def case_036(p):
    inspect(p, ['PX-B-36', 'PX-BR-FX-INSTALLMENTS', 'PX-BR-FX-CREDIT-PORTIONS', 'PX-BR-FX-EXPOSURE'],
            ['xp_b_fx_orders', 'xp_b_fx_requirements', 'xp_b_supplier_fx_credits'])
    schedule = p.one('xp_b_reasoning_supplier_schedule')
    credit = p.one('xp_b_supplier_fx_credits')
    requirement = p.one('xp_b_fx_requirements')
    order = next(x for x in p.rows('xp_b_fx_orders') if x['requirement_id'] == requirement['id'])
    p.write('request_fx_order_cancellation', order_id=order['id'])
    p.write('request_supplier_credit_advice', record_id=credit['id'])
    p.wait()
    requirement = p.read('xp_b_fx_requirements', requirement['id'])
    assert requirement['acquired_minor'] >= schedule['advance_minimum_minor']
    p.write('pay_supplier_foreign_installment', requirement_id=requirement['id'], amount_minor=schedule['advance_minimum_minor'])
    for _ in range(10):
        credit = p.read('xp_b_supplier_fx_credits', credit['id'])
        if credit.get('advice_received'):
            break
        p.wait()
    requirement = p.read('xp_b_fx_requirements', requirement['id'])
    offset = min(credit['credit_minor'], requirement['need_minor'])
    p.write('allocate_supplier_credit_portions', credit_record_id=credit['id'], offset_minor=offset, refund_minor=credit['credit_minor'] - offset)
    for _ in range(10):
        order = p.read('xp_b_fx_orders', order['id'])
        if order['status'] == 'cancelled':
            break
        p.wait()
    requirement = p.read('xp_b_fx_requirements', requirement['id'])
    surplus = requirement['acquired_minor'] - requirement['need_minor']
    if surplus > 0:
        p.write('sell_surplus_supplier_currency', record_id=credit['id'], choice='standard_treasury', amount_minor=surplus)
    elif surplus < 0:
        p.write('buy_foreign_currency', requirement_id=requirement['id'], amount_minor=-surplus)
    if requirement['need_minor']:
        p.write('pay_foreign_obligation', requirement_id=requirement['id'])
    for _ in range(10):
        current = p.read('xp_b_supplier_fx_credits', credit['id'])
        if current.get('refund_received') or credit['credit_minor'] == offset:
            break
        p.wait()
    p.write('confirm_supplier_fx_settlement', record_id=credit['id'])
    p.finish('Paid the early installment from the actual fill, confirmed cancellation, allocated the supplier credit only against remaining principal and refunded its excess, sold surplus currency and confirmed the exact settled invoice with no foreign exposure or changes to the unrelated order.')


def case_037(p):
    p.docs('PX-B-37', 'PX-BR-ROYALTY-CAPACITY', 'PX-BR-ROYALTY-RECEIPTS', 'PX-BR-ROYALTY-REVIEW', 'IFACE-ROYALTY-CAPACITY')
    pool = p.one('xp_b_pools')
    allocations = p.rows('xp_b_allocations')
    tax = p.one('xp_b_royalty_tax')
    delivery = p.one('xp_b_reasoning_royalty_delivery')
    channels = p.rows('xp_b_reasoning_royalty_channels')
    p.write('convert_shared_proceeds', pool_id=pool['id'])
    total = pool['source_minor'] * pool['rate_num'] // pool['rate_den']
    weights = sum(x['weight'] for x in allocations)
    gross = {x['id']: total * x['weight'] // weights for x in allocations}
    for allocation in sorted(allocations, key=lambda x: (-(total * x['weight'] % weights), x['residual_rank']))[:total-sum(gross.values())]:
        gross[allocation['id']] += 1
    p.write('review_royalty_beneficiary_residency', record_id=tax['id'])
    first = next(x for x in allocations if delivery['beneficiary_conditions'][x['id']]['status'] == 'final' and gross[x['id']])
    instant = next(x for x in channels if x['capacity_group'] == 'immediate')
    booking = p.write('reserve_royalty_payout_capacity', allocation_id=first['id'], channel_id=instant['id'])
    p.write('select_royalty_payout_booking', booking_id=booking['id'])
    p.write('disburse_allocation', allocation_id=first['id'], amount_minor=gross[first['id']])
    for _ in range(10):
        current = p.read('xp_b_reasoning_royalty_delivery', delivery['id'])
        if current['conditions_final']:
            break
        p.wait()
    tax = p.read('xp_b_royalty_tax', tax['id'])
    withholding = gross[tax['beneficiary_id']] * tax['withholding_bps'] // 10000
    p.write('elect_royalty_withholding', record_id=tax['id'], choice=tax['beneficiary_id'], amount_minor=withholding)
    p.write('remit_royalty_withholding', record_id=tax['id'])
    remaining = [x for x in allocations if gross[x['id']] and x['id'] != first['id']]
    from itertools import product
    options = []
    minute = p.call('assistant', 'get_clock')['minute']
    for selected in product(channels, repeat=len(remaining)):
        counts = {'immediate': 1}
        valid = True
        for allocation, channel in zip(remaining, selected, strict=True):
            conditions = current['beneficiary_conditions'][allocation['id']]
            counts[channel['capacity_group']] = counts.get(channel['capacity_group'], 0) + 1
            arrival = channel.get('arrival_minute', minute + channel['delay_minutes'])
            valid &= channel['id'] in conditions['allowed_channels'] and arrival <= conditions['deadline'] and minute <= channel['cutoff_minute']
        valid &= all(count <= current['capacity_limits'][group] for group, count in counts.items())
        if valid:
            options.append((sum(x['fee_minor'] for x in selected), selected))
    _, selected = min(options, key=lambda x: x[0])
    final_arrival = minute
    for allocation, channel in zip(remaining, selected, strict=True):
        booking = p.write('reserve_royalty_payout_capacity', allocation_id=allocation['id'], channel_id=channel['id'])
        p.write('select_royalty_payout_booking', booking_id=booking['id'])
        net = gross[allocation['id']] - (withholding if allocation['id'] == tax['beneficiary_id'] else 0)
        p.write('disburse_allocation', allocation_id=allocation['id'], amount_minor=net)
        final_arrival = max(final_arrival, channel.get('arrival_minute', minute + channel['delay_minutes']))
    for _ in range(10):
        p.wait()
        if p.call('assistant', 'get_clock')['minute'] >= final_arrival:
            break
    p.rows('xp_b_reasoning_royalty_bookings')
    p.write('deliver_royalty_tax_certificate', record_id=tax['id'])
    p.finish('Distributed every beneficiary entitlement by largest remainder, paid the unaffected early beneficiary on time, waited for final residency and route conditions, used the limited delivery slots to meet both remaining receipt deadlines, and remitted and certified withholding against its actual owner without allocating anything to the zero-weight reserve.')


def case_038(p):
    inspect(p, ['PX-B-38', 'PX-BR-TAX-CAPACITY', 'PX-BR-TAX-ROUTES', 'PX-BR-TAX-CENSUS', 'IFACE-TAX-AGENCY-CAPACITY'],
            ['xp_b_tax_agents', 'xp_b_tax_obligations', 'xp_b_tax_handovers', 'xp_b_retiring_tax_instructions', 'xp_b_reasoning_tax_capacity'])
    files = p.call('user', 'list_my_files')
    handover = p.one('xp_b_tax_handovers')
    capacity = p.one('xp_b_reasoning_tax_capacity')
    p.call('user', 'upload_file', file_id=next(x['id'] for x in files if x['purpose'] == 'tax_agent_appointment'), target_id=handover['new_agent_id'], purpose='tax_agent_appointment')
    p.write('submit_tax_agent_application', agent_id=handover['new_agent_id'])
    p.write('reserve_tax_agency_processing', capacity_contract_id=capacity['id'], jurisdiction='Northhaven', amount_minor=500)
    p.write('request_retiring_tax_agent_census', handover_id=handover['id'])
    p.write('end_retiring_tax_agent_mandate', handover_id=handover['id'], jurisdiction='ALL')
    p.wait()
    p.rows('xp_b_retiring_tax_instructions')
    for _ in range(10):
        instructions = p.rows('xp_b_retiring_tax_instructions')
        agent = p.read('xp_b_tax_agents', handover['new_agent_id'])
        if all(x['status'] == 'settled' for x in instructions) and agent['status'] == 'approved':
            break
        p.wait()
    obligations = p.rows('xp_b_tax_obligations')
    for receipt in p.rows('xp_b_tax_settlement_receipts'):
        obligation = next(x for x in obligations if x['jurisdiction'] == receipt['jurisdiction'])
        p.write('allocate_settled_tax_receipt', handover_id=handover['id'], receipt_id=receipt['id'],
                obligation_id=obligation['id'], amount_minor=receipt['amount_minor'])
    p.write('configure_tax_agent_route', agent_id=handover['new_agent_id'])
    for obligation in p.rows('xp_b_tax_obligations'):
        if not obligation['discharged']:
            p.write('pay_tax_obligation', obligation_id=obligation['id'], recipient_id=handover['new_agent_id'])
    p.wait()
    p.rows('xp_b_reasoning_tax_payments')
    p.write('publish_tax_handover_clearance', handover_id=handover['id'])
    p.finish('Ended all retiring-agent scopes, allowed its existing instructions to settle, allocated each actual authority receipt once to the matching jurisdiction, and used the approved successor route and reserved capacity only for the unpaid balance. Both taxes reached their authority by deadline without duplicate tax; published the handover clearance.')


def case_039(p):
    inspect(p, ['PX-B-39', 'PX-BR-CUSTOMS-CORRECTION', 'PX-BR-CUSTOMS-RECEIVING'],
            ['xp_b_importers', 'xp_b_destinations', 'xp_b_customs_entries', 'xp_b_customs_liens', 'xp_b_reasoning_customs_disbursements'])
    files = p.call('user', 'list_my_files')
    importer = p.one('xp_b_importers')
    schedule = p.one('xp_b_reasoning_customs_disbursements')
    lien = p.one('xp_b_customs_liens')
    p.call('user', 'upload_file', file_id=next(x['id'] for x in files if x['purpose'] == 'customs_schedule'), target_id=importer['id'], purpose='customs_schedule')
    destination = schedule['receiving_channels']['main_cycle']['destination_id']
    p.write('register_customs_refund_account', importer_id=importer['id'], destination_id=destination)
    p.write('submit_customs_refund_claim', importer_id=importer['id'], entry_ids=[x['id'] for x in p.rows('xp_b_customs_entries')])
    p.write('inspect_importer_customs_lien', record_id=lien['id'])
    p.wait()
    lien = p.read('xp_b_customs_liens', lien['id'])
    candidates = [(value['fee_minor'], key) for key, value in lien['release_certificates'].items()
                  if value['entry_id'] == lien['lien_entry_id'] and value['amount_minor'] >= lien['lien_minor']]
    certificate = min(candidates)[1]
    p.write('file_customs_lien_discharge', record_id=lien['id'], choice=certificate)
    for _ in range(10):
        current = p.read('xp_b_customs_liens', lien['id'])
        importer = p.read('xp_b_importers', importer['id'])
        if current.get('discharge_received') and importer.get('award_status') == 'reviewed':
            break
        p.wait()
    p.write('select_customs_disbursement_channel', schedule_id=schedule['id'], channel='main_cycle')
    p.write('accept_customs_award', importer_id=importer['id'], decision='accept', amount_minor=importer['award_minor'])
    p.wait()
    p.write('apply_customs_encumbrance_release', record_id=lien['id'])
    p.call('user', 'upload_file', file_id=next(x['id'] for x in files if x['purpose'] == 'classification_amendment'), target_id=schedule['amendment_entry_id'], purpose='classification_amendment')
    p.write('submit_customs_classification_review', schedule_id=schedule['id'], entry_id=schedule['amendment_entry_id'], channel='standard')
    for _ in range(10):
        actual = p.read('xp_b_reasoning_customs_disbursements', schedule['id'])
        if actual.get('classification_final'):
            break
        p.wait()
    remaining = actual['approved_minor'] - actual['committed_minor']
    if remaining:
        p.write('select_customs_disbursement_channel', schedule_id=schedule['id'], channel='registered_ach')
        p.write('accept_customs_award', importer_id=importer['id'], decision='accept', amount_minor=remaining)
        p.wait()
    p.rows('xp_b_reasoning_customs_payouts')
    p.rows('xp_b_destinations')
    p.write('deliver_customs_availability_statement', record_id=lien['id'])
    p.finish('Claimed the reviewed importer-owned duty, received the initial award before the early cash deadline, released the exact entry lien with its genuine certificate, submitted the component correction and received its approved supplement by the final deadline, then delivered the full availability statement within the fee budget.')


def case_043(p):
    p.docs('PX-C-43', 'PX-C-R43', 'IFACE-NETWORK-CAPTURE')
    card = p.one('xp_c_network_cards')
    tokens = p.rows('xp_c_network_tokens')
    consent = p.one('xp_c_subscription_consents')
    captures = p.rows('xp_c_essential_captures')
    manage = manager(p, 'manage_subscription_consent', consent['id'])
    pending = manage('retrieve_capture_orders')
    manage('dispose_capture', pending['capture_merchant'], 0)
    for capture in captures:
        p.write('present_essential_capture', capture_id=capture['id'], disposition='void')
    p.write('replace_network_card', network_card_id=card['id'], action='replace')
    card = p.read('xp_c_network_cards', card['id'])
    for token in tokens:
        if token['merchant'] not in consent['essential_merchants']:
            p.write('manage_merchant_token', token_id=token['id'], action='cancel_agreement')
        else:
            if not token['updater_supported']:
                p.write('manage_merchant_token', token_id=token['id'], action='refresh')
            manage('record_service_consent', token['merchant'], consent['service_limits'][token['merchant']])
    manage('bind_card_generation', card['id'], card['generation'])
    p.write('run_merchant_billing', network_card_id=card['id'])
    p.rows('xp_c_network_tokens')
    p.finish('Replaced the card, restored essential merchant credentials and exact consent ceilings on its current generation, cancelled the unwanted agreement and old capture, voided the unpresented essential capture, and billed the two genuine invoices once.')


def case_044(p):
    p.docs('PX-C-44', 'PX-C-R44', 'IFACE-CARRIER-COD-RETURN')
    batch = p.one('xp_c_cod_batches')
    orders = p.rows('xp_c_cod_orders')
    claim = p.one('xp_c_carrier_fee_claims')
    returned = p.one('xp_c_cod_returns')
    manage = manager(p, 'manage_carrier_fee_claim', claim['id'])
    fee = manage('retrieve_carrier_fees')
    manage('settle_return_fee', fee['fee_parcel'], 0)
    commission = sum(x['commission_minor'] for x in orders if x['delivery_status'] == 'DELIVERED')
    p.write('request_cod_return_notice', return_id=returned['id'])
    p.write('reconcile_carrier_cash', batch_id=batch['id'], service='standard')
    manage('offset_commission', claim['invoice_batch_reference'], commission)
    p.wait()
    returned = p.read('xp_c_cod_returns', returned['id'])
    channel = 'net_remittance' if returned['refund_minor'] >= returned['net_offset_minimum_minor'] else 'cash_refund'
    p.write('select_cod_return_channel', return_id=returned['id'], channel=channel)
    p.write('settle_carrier_collection', batch_id=batch['id'], action='remit_cash')
    p.write('settle_carrier_collection', batch_id=batch['id'], action='carrier_shortfall')
    if channel == 'cash_refund':
        p.write('send_cod_buyer_refund', return_id=returned['id'], order_id=returned['order_id'], amount_minor=returned['refund_minor'])
    batch = p.read('xp_c_cod_batches', batch['id'])
    print('BATCH', batch, flush=True)
    print('CASH', p.read('xp_accounts', returned['account_id']), flush=True)
    manage('allocate_remittance', claim['invoice_batch_reference'], batch['remitted_minor'] + batch['recovered_minor'])
    p.write('pay_cod_replenishment', return_id=returned['id'], amount_minor=returned['replenishment_minor'])
    p.finish('Reconciled parcel-level custody cash, disputed the unpaid return fee, offset only delivered-parcel commissions, recovered the carrier shortfall, allocated proceeds to buyer invoices, refunded the named returned order once and paid replenishment from posted cash.')


def case_045(p):
    p.docs('PX-C-45', 'PX-C-R45', 'IFACE-TAX-REFUND-CREDIT')
    batch = p.one('xp_c_tax_batches')
    registration = p.one('xp_c_tax_registrations')
    p.write('synchronize_sales_tax_events', tax_batch_id=batch['id'])
    manage = manager(p, 'manage_tax_registration', registration['id'])
    registry = manage('retrieve_jurisdiction_status')
    refund = p.one('xp_c_prior_tax_refunds')
    orders = p.rows('xp_c_tax_orders')
    manage('register_jurisdiction', registry['destination'])
    manage('reserve_tax_credit', registry['credit_jurisdiction'], registry['credit_minor'])
    p.write('refund_prior_tax_overcollection', refund_id=refund['id'], recipient=refund['original_recipient'],
            route='bank', amount_minor=refund['refund_minor'])
    p.wait()
    notice = p.read('xp_c_prior_tax_refunds', refund['id'])
    p.write('allocate_generated_tax_credit', refund_id=refund['id'], period='CURRENT', jurisdiction=notice['credit_jurisdiction'])
    p.write('remit_order_sales_tax', tax_batch_id=batch['id'], order_ids=[x['id'] for x in orders if x['collector'] == 'MERCHANT'])
    p.write('publish_sales_tax_close', tax_batch_id=batch['id'])
    manage('publish_credit_schedule', registry['credit_jurisdiction'], registry['credit_minor'])
    p.finish('Synchronized the return and destination changes, refunded the actual prior overcollection to Harbor Buyer, paid only merchant liabilities using matching prepaid and certified refund credits, and published the complete sales and retained credit close.')


def case_046(p):
    p.docs('PX-C-46', 'PX-C-R46', 'IFACE-STATEMENT-DISTRIBUTION')
    match = p.one('xp_c_interaccount_matches')
    distribution = p.one('xp_c_treasury_distributions')
    manage = manager(p, 'manage_interaccount_match', match['id'])
    advice = manage('retrieve_transfer_advice')
    statements = p.rows('xp_c_statements')
    p.write('submit_treasury_redemption', distribution_id=distribution['id'], channel='accelerated')
    for statement in statements:
        if statement['completeness'] == 'GAP':
            p.write('retrieve_statement_segment', statement_id=statement['id'], product='missing_range')
    for entry in p.rows('xp_c_statement_entries'):
        if entry['bank_reference'] == advice['bank_transfer_reference']:
            category = 'internal_transfer'
        elif 'sales' in entry['narrative'].lower():
            category = 'sales'
        elif 'fee' in entry['narrative'].lower():
            category = 'bank_fee'
        elif entry['amount_minor'] > 0:
            category = 'supplier_refund'
        else:
            category = 'supplier_payment'
        p.write('assign_statement_entry', entry_id=entry['id'], category=category)
    manage('match_bank_reference', advice['bank_transfer_reference'], advice['debit_minor'])
    for statement in statements:
        p.write('finalize_statement_day', statement_id=statement['id'], method='complete')
    manage('post_consolidation_entry', 'internal_transfer', advice['debit_minor'])
    consolidated = manage('publish_consolidated_report')
    p.wait()
    distribution = p.read('xp_c_treasury_distributions', distribution['id'])
    owner_due = consolidated['external_income_minor'] * distribution['distribution_numerator'] // distribution['distribution_denominator']
    balances = {x['id']: x['balance_minor'] - distribution['hold_by_account'].get(x['id'], 0) for x in p.rows('xp_accounts')}
    for obligation, amount in [('OWNER', owner_due), ('SUPPLIER', distribution['supplier_face_minor'] - distribution['supplier_discount_minor'])]:
        for account_id, available in balances.items():
            paid = min(available, amount)
            if paid > 0:
                p.write('pay_statement_supported_distribution', distribution_id=distribution['id'], obligation=obligation,
                        account_id=account_id, amount_minor=paid, supplier_terms='early_discount')
                balances[account_id] -= paid
                amount -= paid
        assert amount == 0, (obligation, amount)
    p.finish('Recovered the missing original bank rows, classified every entry and closed both detailed days; matched and eliminated the internal transfer in consolidation, redeemed the deposit on the approved accelerated route and paid the supported owner distribution and discounted supplier invoice before their deadlines from available cash.')


def case_048(p):
    p.docs('PX-C-48', 'PX-C-R48')
    negotiation = p.one('xp_c_negotiations')
    obligations = p.rows('xp_c_negotiation_obligations')
    plans = p.rows('xp_c_negotiation_plans')
    dispute = p.one('xp_c_receivable_disputes')
    manage = manager(p, 'manage_receivable_dispute', dispute['id'])
    debtor = manage('retrieve_debtor_confirmation')
    tranche = p.one('xp_c_debtor_tranches')
    factors = p.rows('xp_c_factor_offers')
    flexible = next(x for x in obligations if x['commercial_role'] == 'FLEXIBLE')
    combinations = [(plan['fee_minor'] + factor['fee_minor'], plan, factor)
                    for plan in plans for factor in factors
                    if plan['obligation_id'] == flexible['id'] and plan['revised_amount_minor'] == flexible['original_amount_minor']
                    and plan['revised_due_minute'] <= min(negotiation['flexible_latest_minute'], factor['latest_invoice_due_minute'])]
    cost, plan, factor = min(combinations, key=lambda x: x[0])
    assert cost <= negotiation['approved_fee_cap_minor']
    manage('set_collection_tranche', debtor['debt_reference'], debtor['undisputed_minor'])
    manage('set_disputed_claim_disposition', 'OPEN', debtor['disputed_minor'])
    p.write('adopt_payment_plan', plan_id=plan['id'])
    p.write('pay_negotiated_obligation', obligation_id=next(x['id'] for x in obligations if x['commercial_role'] == 'CRITICAL'))
    for _ in range(30):
        if p.call('assistant', 'get_clock')['minute'] >= negotiation['receivable_available_minute']:
            break
        p.wait()
    p.write('collect_committed_receivable', negotiation_id=negotiation['id'])
    actual = p.read('xp_c_debtor_tranches', tranche['id'])
    manage('allocate_collection_receipt', debtor['debt_reference'], actual['first_received_minor'])
    p.write('assign_residual_receivable', tranche_id=tranche['id'], factor_id=factor['id'])
    p.write('pay_negotiated_obligation', obligation_id=flexible['id'])
    p.finish('Paid the critical invoice on its original terms and the flexible invoice in full under the approved extension; preserved the disputed claim, allocated the actual first debtor receipt, and assigned only the remaining undisputed tranche without recourse within the shared finance-fee cap.')


def case_049(p):
    inspect(p, ['PX-C-49', 'PX-C-R49', 'IFACE-SUPPLIER-SPLIT-REMITTANCE'],
            ['xp_c_route_offers', 'xp_c_route_portfolios', 'xp_c_beneficiary_delivery_terms'])
    terms = p.one('xp_c_beneficiary_delivery_terms')
    manage = manager(p, 'manage_beneficiary_delivery_terms', terms['id'])
    beneficiary = manage('validate_beneficiary')
    manage('select_beneficiary_account', beneficiary['validated_account'])
    quote = manage('obtain_delivery_quote', 'direct_member')
    manage('set_fee_bearer', 'SENDER')
    offer = p.one('xp_c_route_offers')
    p.write('purchase_route_inquiry', offer_id=offer['id'], service='standard')
    p.write('commit_payment_route', offer_id=offer['id'], route='economical')
    manage('reconcile_delivery', beneficiary['validated_account'], offer['principal_minor'])
    portfolio = p.one('xp_c_route_portfolios')
    remaining = portfolio['second_principal_minor']
    economical = min(remaining, portfolio['remaining_minor'])
    if economical:
        p.write('remit_second_supplier_installment', portfolio_id=portfolio['id'], amount_minor=economical, route='economical', fee_bearer='SENDER')
        remaining -= economical
    while remaining:
        amount = min(remaining, portfolio['ticket_cap_minor'])
        p.write('remit_second_supplier_installment', portfolio_id=portfolio['id'], amount_minor=amount, route='conservative', fee_bearer='SENDER')
        remaining -= amount
    p.rows('xp_c_supplier_installments')
    p.finish('Validated the first supplier account and sender-paid direct-member quote, bought one shared formal certificate, delivered its exact principal, then used the published remaining quota plus capped clearing tickets to deliver Harbor Packaging its full principal without overpayment and within both deadlines and the USD 14 total fee allowance.')


def case_034(p):
    p.docs('PX-B-34', 'PX-B-R34-LINES')
    payments = p.rows('xp_b_gateway_payments')
    p.rows('xp_b_gateway_routes')
    p.rows('xp_b_store_orders')
    fulfillment = p.one('xp_b_order_fulfillments')
    schedule = p.one('xp_b_delivery_schedules')
    lines = sorted(p.rows('xp_b_dispatch_lines'), key=lambda x: x['deadline'])
    bookings = {}
    for line, channel in zip(lines, ('priority', 'ordinary'), strict=True):
        bookings[line['id']] = p.write('reserve_store_dispatch_channel', schedule_id=schedule['id'], channel=channel)
    for route_id in {x['route_id'] for x in payments}:
        intended = {x['merchant_account'] for x in payments if x['route_id'] == route_id}
        assert len(intended) == 1
        p.write('repair_gateway_mapping', route_id=route_id, merchant_account=intended.pop())
    for payment in payments:
        p.write('replay_payment_receipt', payment_id=payment['id'])
    p.write('reserve_store_order_inventory', record_id=fulfillment['id'])
    p.wait()
    fulfillment = p.read('xp_b_order_fulfillments', fulfillment['id'])
    choice = min((key for key, value in fulfillment['substitutes'].items()
                  if value['socket'] == fulfillment['required_socket'] and value['rating'] >= fulfillment['required_rating']),
                 key=lambda key: fulfillment['substitutes'][key]['fee_minor'])
    p.write('commit_store_order_substitute', record_id=fulfillment['id'], choice=choice)
    stock = p.rows('xp_b_dispatch_stock')
    for line in lines:
        eligible = sorted((x for x in stock if x['socket'] == line['required_socket'] and x['rating'] >= line['minimum_rating']), key=lambda x: x['rating'])
        selected = eligible[:line['quantity']]
        assert len(selected) == line['quantity']
        p.write('dispatch_store_delivery_line', schedule_id=schedule['id'], line_id=line['id'],
                stock_ids=[x['id'] for x in selected], booking_id=bookings[line['id']]['id'])
        stock = [x for x in stock if x not in selected]
    for _ in range(10):
        if p.read('xp_b_order_fulfillments', fulfillment['id']).get('delivery_complete'):
            break
        p.wait()
    p.write('close_store_delivery_receipt', record_id=fulfillment['id'])
    p.finish('Replayed all authentic captures and refund to the intended live merchant without recharging; delivered compatible units to both lines before their deadlines and closed the real carrier receipt.')


def case_035(p):
    p.docs('PX-B-35', 'PX-B-R35-EXIT')
    rules = p.rows('xp_b_payout_rules')
    p.rows('xp_b_receiving_accounts')
    reconciliation = p.one('xp_b_platform_reconciliations')
    schedule = p.one('xp_b_delivery_schedules')
    rule = next(x for x in rules if x['receiving_id'] == reconciliation['receiving_id'])
    p.write('register_platform_revenue_reconciliation', record_id=reconciliation['id'])
    p.write('set_platform_payout_rule', rule_id=rule['id'], enabled=False)
    for payout in p.rows('xp_b_platform_payouts'):
        if payout['receiving_id'] == rule['receiving_id'] and payout['status'] == 'accepted':
            p.write('resolve_accepted_payout', payout_id=payout['id'], disposition='settle')
    p.write('request_platform_reserve_breakdown', record_id=reconciliation['id'])
    p.write('settle_manual_platform_receipt', record_id=reconciliation['id'])
    p.write('review_platform_return_liability', schedule_id=schedule['id'])
    p.write('reserve_platform_refund_channel', schedule_id=schedule['id'], channel='prebooked')
    p.write('sweep_platform_receipts', schedule_id=schedule['id'], service='early', amount_minor=schedule['early_amount_minor'])
    p.wait()
    p.read('xp_b_platform_reconciliations', reconciliation['id'])
    p.write('dispose_platform_revenue_reserve', record_id=reconciliation['id'], choice='evidence_appeal')
    for _ in range(12):
        for payout in p.rows('xp_b_platform_payouts'):
            if payout['receiving_id'] == rule['receiving_id'] and payout['status'] == 'accepted':
                p.write('resolve_accepted_payout', payout_id=payout['id'], disposition='settle')
        current = p.read('xp_b_delivery_schedules', schedule['id'])
        if current.get('return_reviewed') and not current.get('refund_order'):
            p.write('pay_platform_customer_return', schedule_id=schedule['id'], channel='prebooked', amount_minor=current['return_amount_minor'])
        if p.call('assistant', 'get_clock')['minute'] >= schedule['manual_delay']:
            break
        p.wait()
    final_rule = p.read('xp_b_payout_rules', rule['id'])
    assert not final_rule['enabled'] and final_rule['pending_enabled'] is None
    p.read('xp_b_platform_reconciliations', reconciliation['id'])
    cash = p.read('xp_accounts', schedule['account_id'])
    p.write('sweep_platform_receipts', schedule_id=schedule['id'], service='regular', amount_minor=cash['balance_minor'])
    p.wait()
    p.rows('xp_b_platform_transfers')
    p.finish('Confirmed the Sales automatic rule stopped, kept receiving and Other rules active, settled all accepted and manual revenue, recovered the reserve by evidence appeal, paid the reviewed customer return on time, and delivered the early and final treasury amounts within deadlines and the fee cap.')


def case_047(p):
    p.docs('PX-C-47', 'PX-C-R47', 'IFACE-SUPPLIER-CALLOFF')
    executions = p.rows('xp_c_executions')
    binding = p.one('xp_c_recovery_period_bindings')
    advance = p.one('xp_c_supplier_advances')
    def manage(action, reference='', amount_minor=0):
        return p.write('manage_recovery_period_binding', record_id=binding['id'], action=action,
                       reference=reference, amount_minor=amount_minor)
    locks = manage('retrieve_period_locks')
    manage('select_posting_period', locks['open_period'])
    p.write('request_supplier_calloff_notice', advance_id=advance['id'])
    for execution in executions:
        p.write('recover_payment_posting', execution_id=execution['id'], mode='replay_all')
    p.wait()
    for _ in range(8):
        returned = p.read('xp_c_executions', advance['return_execution'])
        if returned['bank_status'] == 'RETURNED':
            break
        p.wait()
    assert returned['bank_status'] == 'RETURNED'
    p.write('recover_payment_posting', execution_id=returned['id'], mode='replay_reversal')
    manage('record_returned_payable', returned['return_reference'], returned['amount_minor'])
    applications = p.rows('xp_c_advance_applications')
    advance = p.read('xp_c_supplier_advances', advance['id'])
    required = advance['required_units'] * advance['unit_price_minor']
    for application in applications:
        if application['advance_id'] == advance['id'] and application['status'] == 'APPLIED':
            p.write('reverse_supplier_advance', application_id=application['id'])
    p.write('apply_supplier_advance', advance_id=advance['id'], payable_id=applications[0]['payable_id'],
            amount_minor=advance['original_minor'] - required)
    p.write('release_supplier_calloff', advance_id=advance['id'], units=advance['required_units'])
    manage('publish_rollforward')
    p.finish('Preserved the settled supplier payment, repaired both original projections and the actual bank-return reversal in the current open period, retained the historical lock and receipts, restored the returned payable, released all five call-off units and applied only the remaining advance to debt, without another cash transfer.')


def case_050(p):
    p.docs('PX-C-50', 'PX-C-R50', 'IFACE-WALLET-PAYROLL')
    control = p.one('xp_c_controllers')
    payroll = p.one('xp_c_wallet_payrolls')
    p.rows('xp_accounts')
    order = p.one('xp_c_wallet_purchase_orders')
    def manage(action, reference='', amount_minor=0):
        return p.write('manage_wallet_purchase_order', record_id=order['id'], action=action,
                       reference=reference, amount_minor=amount_minor)
    status = manage('retrieve_merchant_order_status')
    manage('cancel_order', status['cancelled_order_reference'])
    manage('reserve_order_amount', status['required_order_reference'], control['purchase_minor'])
    manage('set_clearing_priority', 'MERCHANT')
    p.write('configure_wallet_automation', controller_id=control['id'], rule='topup',
            threshold_minor=5000, amount_minor=control['max_topup_minor'], enabled=True, cooldown_cycles=0)
    p.write('configure_wallet_automation', controller_id=control['id'], rule='sweep',
            threshold_minor=12000, amount_minor=5000, enabled=True, cooldown_cycles=0)
    p.write('run_wallet_observation', controller_id=control['id'], cycles=2)
    payroll = p.read('xp_c_wallet_payrolls', payroll['id'])
    wallet = p.read('xp_accounts', control['wallet_account_id'])
    shortfall = max(0, payroll['payroll_minor'] - wallet['balance_minor'])
    if shortfall:
        p.write('fund_wallet_payroll', payroll_id=payroll['id'], amount_minor=shortfall + payroll['manual_fee_minor'])
    p.write('settle_wallet_payroll', payroll_id=payroll['id'], amount_minor=payroll['payroll_minor'])
    p.write('run_wallet_observation', controller_id=control['id'], cycles=5)
    manage('reconcile_capture', status['required_order_reference'], control['purchase_minor'])
    p.finish('Reconciled the live merchant purchase once, cancelled its duplicate, paid the published payroll before its due cycle, and observed five stable cycles with both automatic services enabled and total fees within USD 3.')
