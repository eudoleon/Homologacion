from odoo import SUPERUSER_ID, api


def _ensure_tax_group(env, name):
    tax_group = env['account.tax.group'].search([('name', '=', name)], limit=1)
    if not tax_group:
        tax_group = env['account.tax.group'].create({'name': name})
    return tax_group


def _ensure_tax(env, company, spec, type_tax_use):
    target_company = company.root_id if hasattr(company, 'root_id') and company.root_id else company
    tax_obj = env['account.tax'].with_company(target_company).sudo()

    existing = tax_obj.with_context(active_test=False).search([
        ('company_id', 'child_of', target_company.id),
        ('type_tax_use', '=', type_tax_use),
        ('name', '=', spec['name']),
    ], limit=1)
    if existing:
        if not existing.active:
            existing.active = True
        return existing

    group_ref = tax_obj.search([
        ('company_id', 'child_of', target_company.id),
        ('type_tax_use', 'in', ['sale', 'purchase', 'none']),
        ('name', '=', spec['group_ref_name']),
    ], limit=1)

    tax_group = group_ref.tax_group_id if group_ref and group_ref.tax_group_id else _ensure_tax_group(env, spec['group_name'])

    values = {
        'name': spec['name'],
        'description': spec['name'],
        'type_tax_use': type_tax_use,
        'amount_type': 'percent',
        'amount': spec['amount'],
        'tax_group_id': tax_group.id,
        'company_id': target_company.id,
        'active': True,
    }

    # Optional localization fields present in this repo.
    if 'appl_type' in tax_obj._fields:
        values['appl_type'] = spec['appl_type']
    if 'type_tax' in tax_obj._fields:
        values['type_tax'] = 'iva'

    return tax_obj.create(values)


def _assign_company_tax_fields(company, taxes_by_key):
    field_map = {
        'reduced_aliquot_sale': 'iva_8_sale',
        'extend_aliquot_sale': 'iva_31_sale',
        'general_aliquot_sale': 'iva_16_sale',
        'reduced_aliquot_purchase': 'iva_8_purchase',
        'extend_aliquot_purchase': 'iva_31_purchase',
        'general_aliquot_purchase': 'iva_16_purchase',
    }
    for company_field, tax_key in field_map.items():
        if company_field in company._fields and not company[company_field]:
            company[company_field] = taxes_by_key[tax_key].id


def bootstrap_taxes(env):
    companies = env['res.company'].sudo().search([])

    sale_tax_specs = [
        {
            'key': 'exempt_sale',
            'name': 'Exento (ventas)',
            'group_ref_name': 'Exento (ventas)',
            'group_name': 'Exento',
            'amount': 0.0,
            'appl_type': 'exento',
        },
        {
            'key': 'iva_8_sale',
            'name': 'IVA (8.0%) ventas',
            'group_ref_name': 'IVA (8.0%) ventas',
            'group_name': 'IVA 8%',
            'amount': 8.0,
            'appl_type': 'reducido',
        },
        {
            'key': 'iva_16_sale',
            'name': 'IVA (16%) ventas',
            'group_ref_name': '15%',
            'group_name': 'IVA 16%',
            'amount': 16.0,
            'appl_type': 'general',
        },
        {
            'key': 'iva_31_sale',
            'name': 'IVA (16%+15%) ventas',
            'group_ref_name': 'IVA (16%+15%) ventas',
            'group_name': 'IVA 16%+15%',
            'amount': 31.0,
            'appl_type': 'adicional',
        },
    ]

    purchase_tax_specs = [
        {
            'key': 'exempt_purchase',
            'name': 'Exento (compras)',
            'group_ref_name': 'Exento (ventas)',
            'group_name': 'Exento',
            'amount': 0.0,
            'appl_type': 'exento',
        },
        {
            'key': 'iva_8_purchase',
            'name': 'IVA (8.0%) compras',
            'group_ref_name': 'IVA (8.0%) ventas',
            'group_name': 'IVA 8%',
            'amount': 8.0,
            'appl_type': 'reducido',
        },
        {
            'key': 'iva_16_purchase',
            'name': 'IVA (16%) compras',
            'group_ref_name': '15%',
            'group_name': 'IVA 16%',
            'amount': 16.0,
            'appl_type': 'general',
        },
        {
            'key': 'iva_31_purchase',
            'name': 'IVA (16%+15%) compras',
            'group_ref_name': 'IVA (16%+15%) ventas',
            'group_name': 'IVA 16%+15%',
            'amount': 31.0,
            'appl_type': 'adicional',
        },
    ]

    for company in companies:
        taxes = {}
        for spec in sale_tax_specs:
            taxes[spec['key']] = _ensure_tax(env, company, spec, 'sale')
        for spec in purchase_tax_specs:
            taxes[spec['key']] = _ensure_tax(env, company, spec, 'purchase')
        _assign_company_tax_fields(company, taxes)


def post_init_hook(env):
    bootstrap_taxes(env)
