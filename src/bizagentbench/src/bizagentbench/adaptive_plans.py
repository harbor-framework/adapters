"""Five business plans driven by actual public responses; no private customer answers."""

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
    facts = p.customer('facts', fields={'supplier_net_minor': 'Object keyed by currency, amounts in integer minor units', 'retain_minor': 'Wallet minimum balances keyed by currency', 'currency_fee_limit_minor': 'Total USD FX route fee cap in minor units', 'bank_amendment_fee_limit_minor': 'USD correction fee cap in minor units', 'allow_designated_reserve_disbursement': 'Boolean: may use the published designated reserve route for the correction fee?', 'no_new_tax_payment': 'Boolean: correct the existing tax transfers without sending tax again'})
    p.require(isinstance(facts, dict) and all((k in facts for k in ('supplier_net_minor', 'retain_minor', 'currency_fee_limit_minor', 'bank_amendment_fee_limit_minor', 'allow_designated_reserve_disbursement', 'no_new_tax_payment'))), 'Customer requirements are incomplete.')
    p.require(facts['allow_designated_reserve_disbursement'] is True and facts['no_new_tax_payment'] is True, 'The current plan does not cover the changed funding or tax requirements.')
    p.require(isinstance(facts['supplier_net_minor'], dict) and isinstance(facts['retain_minor'], dict) and all((type(v) is int and v >= 0 for v in [*facts['supplier_net_minor'].values(), *facts['retain_minor'].values(), facts['currency_fee_limit_minor'], facts['bank_amendment_fee_limit_minor']])), 'Expected nonnegative integer minor-unit amounts.')
    fx_fees = 0
    fx_ready_minute = 0
    desk_docs(p, 'DESK-fx', 'DESK-tax', 'DESK-collateral', 'DESK-protocol')
    obligations = p.rows('currency_obligations')
    wallet = next((x for x in p.rows('desk_accounts') if 'EUR' in x['wallet']))
    routes = p.rows('fx_routes')
    for obligation in obligations:
        p.require(facts['supplier_net_minor'].get(obligation['currency']) == obligation['amount_minor'], 'Public obligation differs from customer requirements.')
        wallet = p.read('desk_accounts', wallet['id'])
        retained = facts['retain_minor'].get(obligation['currency'], 0)
        needed = obligation['amount_minor'] + obligation['delivery_fee_minor'] + retained - wallet['wallet'].get(obligation['currency'], 0)
        candidates = []
        for route in routes:
            if route['source_currency'] != 'USD' or route['target_currency'] != obligation['currency'] or route['review_status'] != 'FINAL':
                continue
            for amount in range(route['minimum_minor'], wallet['wallet']['USD'] + 1):
                value = amount
                for segment in route['segments']:
                    value = value * segment['numerator'] // segment['denominator']
                if value >= needed:
                    candidates.append((amount + route['fee_minor'], amount, route))
                    break
        candidates = [x for x in candidates if x[0] <= wallet['wallet']['USD'] - facts['retain_minor'].get('USD', 0) and fx_fees + x[2]['fee_minor'] <= facts['currency_fee_limit_minor']]
        p.require(bool(candidates), 'No public route fits the customer balance and fee limits.')
        _, amount, route = min(candidates, key=lambda x: x[0])
        quote = p.write('inspect_multicurrency_quote', account_id=wallet['id'], route_id=route['id'], source_minor=amount)
        p.require(fx_fees + quote['fee_minor'] <= facts['currency_fee_limit_minor'], 'Actual FX quote exceeds the customer fee cap.')
        fx_fees += quote['fee_minor']
        fx_ready_minute = max(fx_ready_minute, p.call('assistant', 'get_clock')['minute'] + quote['settlement_delay'])
        p.write('propose_fx_execution', quote_id=quote['id'])
    files = p.call('user', 'list_my_files')
    certificates = {}
    for f in files:
        if 'current' in f['label']:
            uploaded = p.call('user', 'upload_file', file_id=f['id'], target_id=f['target_id'], purpose=f['purpose'])
            certificates[f['target_id']] = p.write('assess_evidence', submission_id=uploaded['id'])
    while p.call('assistant', 'get_clock')['minute'] < fx_ready_minute:
        p.wait()
    for obligation in obligations:
        p.write('propose_currency_payment', obligation_id=obligation['id'], account_id=wallet['id'], net_minor=obligation['amount_minor'])
    transfers = p.rows('tax_transfers')
    amendable = next((t for t in transfers if t['amend_until_minute'] >= p.call('assistant', 'get_clock')['minute']))
    p.require(amendable['amendment_fee_minor'] <= facts['bank_amendment_fee_limit_minor'], 'Actual correction fee exceeds customer limit.')
    routes = p.rows('reserve_routes')
    p.rows('business_documents')
    route = min((r for r in routes if r['destination_account_id'] == amendable['amendment_fee_account_id'] and r['net_minor'] >= amendable['amendment_fee_minor'] and (r['settlement_delay'] == 0)), key=lambda r: r['fee_minor'])
    p.write('propose_reserve_disbursement', route_id=route['id'])
    cert = certificates[amendable['id']]['contents']
    p.write('propose_bank_message_amendment', transfer_id=amendable['id'], tax_period=cert['declared_bank_period'], tax_reference=cert['tax_reference'])
    initial_posting = p.call('assistant', 'get_clock')['minute'] + amendable['amendment_delay'] + amendable['allocation_delay']
    allocated = set()
    for _ in range(25):
        for f in p.call('user', 'list_my_files'):
            if 'current' in f['label'] and f['target_id'] not in certificates:
                uploaded = p.call('user', 'upload_file', file_id=f['id'], target_id=f['target_id'], purpose=f['purpose'])
                certificates[f['target_id']] = p.write('assess_evidence', submission_id=uploaded['id'])
        for transfer in transfers:
            key = transfer['id']
            if key in certificates and key not in allocated and (key != amendable['id'] or p.call('assistant', 'get_clock')['minute'] >= initial_posting):
                certificate = certificates[key]
                p.write('propose_tax_allocation', transfer_id=key, allocations=certificate['contents']['allocations'], submission_id=certificate['id'])
                allocated.add(key)
        if len(allocated) == len(transfers):
            break
        p.wait()
    p.wait()
    p.rows('tax_allocations')
    periods = p.rows('tax_periods')
    while p.call('assistant', 'get_clock')['minute'] < max((x['filing_cutoff_minute'] for x in periods)):
        p.wait()
    assert all((x.get('filing_status') == 'DISCHARGED' for x in p.rows('tax_periods')))
    p.finish('Delivered both supplier currencies with actual settled funds, funded the timely bank reference amendment from the authorized reserve, and reconciled both existing tax transfers to their current certificate allocations without paying tax twice.')

def case_031(p):
    inspect(p, ['PX-A-OWNER', 'PX-A-D31', 'PX-A-R-CUSTODY-ONBOARDING', 'PX-A-R-CUSTODY-CASH', 'PX-A-R-RETURN-WORKING-CASH'], ['xp_a_incoming', 'xp_a_quarantine_disputes', 'xp_a_reasoning_contracts', 'xp_a_custody_services', 'xp_a_invoices', 'xp_accounts'])
    for f in p.call('user', 'list_my_files'):
        if f['purpose'] in ('origin_proof', 'escrow_direction'):
            p.call('user', 'upload_file', file_id=f['id'], target_id=f['target_id'], purpose=f['purpose'])
    incoming = p.one('xp_a_incoming')
    contract = p.one('xp_a_reasoning_contracts')
    p.write('a_investigate_incoming_owner', incoming_id=incoming['id'])
    p.write('a_submit_quarantine_escrow_direction', incoming_id=incoming['id'])
    services = p.rows('xp_a_custody_services')
    review = min((s for s in services if s['stage'] == 'REVIEW'), key=lambda s: s['delay_minutes'])
    p.write('a_order_trustee_review', contract_id=contract['id'], service_id=review['id'])
    invoice = p.read('xp_a_invoices', contract['normal_invoice_id'])
    p.write('a_pay_business_invoice', invoice_id=invoice['id'], recipient_id=invoice['recipient_id'], amount_minor=invoice['amount_minor'], payment_key=invoice['id'] + '-original')
    while p.call('assistant', 'get_clock')['minute'] < review['delay_minutes']:
        p.wait()
    activation = min((s for s in p.rows('xp_a_custody_services') if s['stage'] == 'ACTIVATION'), key=lambda s: s['fee_minor'])
    p.write('a_activate_dispute_custody', contract_id=contract['id'], service_id=activation['id'])
    ready = p.call('assistant', 'get_clock')['minute'] + activation['delay_minutes']
    while p.call('assistant', 'get_clock')['minute'] < ready:
        p.wait()
    dispute = p.one('xp_a_quarantine_disputes')
    p.write('a_partition_quarantined_funds', incoming_id=incoming['id'], return_minor=incoming['amount_minor'] - dispute['disputed_minor'], escrow_minor=dispute['disputed_minor'], claim_minor=0, trustee_id=dispute['authorized_trustee_id'])
    p.finish('Returned undisputed principal to its original sender, deposited the signed disputed security with the authorized active trustee, and paid the ordinary supplier from operating cash within both deadlines.')

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
    verified = p.read('xp_b_proof_access', access['id'])
    for _ in range(5):
        if verified.get('recipient_verified'):
            break
        p.wait()
        verified = p.read('xp_b_proof_access', access['id'])
    p.require(verified.get('recipient_verified'), 'Recipient verification has not completed; no final proof will be issued.')
    request = p.read('xp_b_evidence_requests', request['id'])
    final = p.write('create_bank_evidence', evidence_request_id=request['id'], kind='receipt', field_names=request['required_fields'], format='pdf')
    p.write('deliver_bank_evidence', evidence_id=final['id'])
    named_policy = next(key for key, readers in access['access_policies'].items() if readers == [access['verified_contact']])
    p.write('set_bank_proof_access_scope', record_id=access['id'], choice=named_policy)
    p.write('issue_scoped_bank_proof_link', record_id=access['id'], choice=final['id'])
    p.wait()
    current = p.read('xp_b_proof_access', access['id'])
    for _ in range(5):
        if current.get('recipient_read') and current.get('reader') == access['verified_contact']:
            break
        p.wait()
        current = p.read('xp_b_proof_access', access['id'])
    p.require(current.get('recipient_read') and current.get('reader') == access['verified_contact'], 'The intended recipient has not read the proof.')
    p.write('revoke_delivered_bank_proof_link', record_id=access['id'])
    p.finish('Delivered preliminary and final sealed single-payment proofs, confirmed Buyer One read the final proof, and revoked the named-only link without disclosing unrelated banking information.')

def case_036(p):
    inspect(p, ['PX-B-36', 'PX-BR-FX-INSTALLMENTS', 'PX-BR-FX-CREDIT-PORTIONS', 'PX-BR-FX-EXPOSURE'], ['xp_b_fx_orders', 'xp_b_fx_requirements', 'xp_b_supplier_fx_credits'])
    schedule = p.one('xp_b_reasoning_supplier_schedule')
    credit = p.one('xp_b_supplier_fx_credits')
    requirement = p.one('xp_b_fx_requirements')
    order = next((x for x in p.rows('xp_b_fx_orders') if x['requirement_id'] == requirement['id']))
    p.write('request_fx_order_cancellation', order_id=order['id'])
    p.write('request_supplier_credit_advice', record_id=credit['id'])
    p.wait()
    requirement = p.read('xp_b_fx_requirements', requirement['id'])
    p.require(requirement['acquired_minor'] >= schedule['advance_minimum_minor'], 'The actual FX fill is not sufficient for the first installment.')
    p.write('pay_supplier_foreign_installment', requirement_id=requirement['id'], amount_minor=schedule['advance_minimum_minor'])
    for _ in range(10):
        credit = p.read('xp_b_supplier_fx_credits', credit['id'])
        if credit.get('advice_received'):
            break
        p.wait()
    p.require(credit.get('advice_received'), 'No actual supplier credit advice has arrived.')
    requirement = p.read('xp_b_fx_requirements', requirement['id'])
    offset = min(credit['credit_minor'], requirement['need_minor'])
    p.write('allocate_supplier_credit_portions', credit_record_id=credit['id'], offset_minor=offset, refund_minor=credit['credit_minor'] - offset)
    for _ in range(10):
        order = p.read('xp_b_fx_orders', order['id'])
        if order['status'] == 'cancelled':
            break
        p.wait()
    requirement = p.read('xp_b_fx_requirements', requirement['id'])
    p.require(order['status'] == 'cancelled', 'FX cancellation is not final.')
    surplus = requirement['acquired_minor'] - requirement['need_minor']
    if surplus > 0:
        p.write('sell_surplus_supplier_currency', record_id=credit['id'], choice='standard_treasury', amount_minor=surplus)
    elif surplus < 0:
        p.write('buy_foreign_currency', requirement_id=requirement['id'], amount_minor=-surplus)
    if requirement['need_minor']:
        p.write('pay_foreign_obligation', requirement_id=requirement['id'])
    for _ in range(10):
        current = p.read('xp_b_supplier_fx_credits', credit['id'])
        if credit['credit_minor'] == offset or current.get('refund_received_minor') == credit['credit_minor'] - offset - current.get('refund_fee_charged_minor', 0):
            break
        p.wait()
    p.require(credit['credit_minor'] == offset or current.get('refund_received_minor') == credit['credit_minor'] - offset - current.get('refund_fee_charged_minor', 0), 'Supplier refund is not yet received.')
    p.write('confirm_supplier_fx_settlement', record_id=credit['id'])
    p.finish('Paid the early installment from the actual fill, confirmed cancellation, allocated the supplier credit only against remaining principal and refunded its excess, sold surplus currency and confirmed the exact settled invoice with no foreign exposure or changes to the unrelated order.')

def case_049(p):
    inspect(p, ['PX-C-49', 'PX-C-R49', 'IFACE-SUPPLIER-SPLIT-REMITTANCE'], ['xp_c_route_offers', 'xp_c_route_portfolios', 'xp_c_beneficiary_delivery_terms'])
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

PLANS = {name: value for name, value in list(globals().items()) if name.startswith("case_")}
