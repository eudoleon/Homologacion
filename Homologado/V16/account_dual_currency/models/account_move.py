# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, Command
from odoo.exceptions import UserError, ValidationError, AccessError, RedirectWarning
from odoo.tools import (
    date_utils,
    email_re,
    email_split,
    float_compare,
    float_is_zero,
    format_amount,
    format_date,
    formatLang,
    frozendict,
    get_lang,
    is_html_empty,
    sql
)
import json
import logging

_logger = logging.getLogger(__name__)

class ResCompany(models.Model):
    _inherit = 'res.company'

    account_id_usd_gain = fields.Many2one(
        'account.account',
        string='Cuenta de Ganancia por Diferencial USD',
        help='Cuenta contable que se usará para registrar ganancias por diferencias en USD.'
    )

    account_id_usd_loss = fields.Many2one(
        'account.account',
        string='Cuenta de Pérdida por Diferencial USD',
        help='Cuenta contable que se usará para registrar pérdidas por diferencias en USD.'
    )

class AccountMove(models.Model):
    _inherit = 'account.move'

    currency_id_dif = fields.Many2one(
        "res.currency",
        string="Moneda Dual Ref.",
        default=lambda self: self.env['res.currency'].search([('name', '=', 'USD')], limit=1)
    )

    verificar_pagos = fields.Boolean(string="Verificar pagos", compute='_verificar_pagos')

    tax_today = fields.Float(
        string="Tasa",
        store=True,
        digits=(16, 4),
    )

    amount_untaxed_usd = fields.Monetary(
        currency_field='currency_id_dif',
        string="Base imponible Ref.",
        store=True,
        compute="_compute_amount_all_usd"
    )
    amount_tax_usd = fields.Monetary(
        currency_field='currency_id_dif',
        string="Impuestos Ref.",
        store=True,
        compute="_compute_amount_all_usd"
    )
    amount_total_usd = fields.Monetary(
        currency_field='currency_id_dif',
        string='Total Ref.',
        store=True,
        compute='_compute_amount_all_usd'
    )
    amount_untaxed_bs = fields.Monetary(
        currency_field='company_currency_id',
        string="Base imponible Bs.",
        store=True,
        compute="_compute_amount_all_usd"
    )
    amount_tax_bs = fields.Monetary(
        currency_field='company_currency_id',
        string="Impuestos Bs.",
        store=True,
        compute="_compute_amount_all_usd"
    )
    amount_total_bs = fields.Monetary(
        currency_field='company_currency_id',
        string='Total Bs.',
        store=True,
        compute='_compute_amount_all_usd'
    )
    amount_residual_usd = fields.Monetary(
        currency_field='currency_id_dif',
        compute='_compute_amount_residual_usd',  # Solo este método, sencillo
        string='Adeudado Ref.',
        store=True, readonly=True, copy=False,
        digits='Dual_Currency'
    )
    is_bs_invoice = fields.Boolean(
        string="¿Factura en Bs?",
        compute="_compute_is_bs_invoice",
        store=False
    )

    name_rate = fields.Char(store=True, readonly=True, compute='_name_ref')

    invoice_payments_widget_usd = fields.Binary(groups="account.group_account_invoice,account.group_account_readonly",
                                              compute='_compute_payments_widget_reconciled_info_USD')

    amount_total_signed_usd = fields.Monetary(
        string='Total Signed Ref.',
        compute='_compute_amount', store=False, readonly=True,
        currency_field='currency_id_dif', copy=False
    )

    acuerdo_moneda = fields.Boolean(string="Acuerdo de Factura Bs.", default=False)
    
    @api.depends(
        # dependencias originales
        'line_ids.matched_debit_ids.debit_move_id.move_id.payment_id.is_matched',
        'line_ids.matched_debit_ids.debit_move_id.move_id.line_ids.amount_residual',
        'line_ids.matched_debit_ids.debit_move_id.move_id.line_ids.amount_residual_currency',
        'line_ids.matched_credit_ids.credit_move_id.move_id.payment_id.is_matched',
        'line_ids.matched_credit_ids.credit_move_id.move_id.line_ids.amount_residual',
        'line_ids.matched_credit_ids.credit_move_id.move_id.line_ids.amount_residual_currency',
        'line_ids.balance',
        'line_ids.currency_id',
        'line_ids.amount_currency',
        'line_ids.amount_residual',
        'line_ids.amount_residual_currency',
        'line_ids.payment_id.state',
        'line_ids.full_reconcile_id',
        'tax_today',
        # nuevas dependencias USD
        'line_ids.balance_usd',
        'line_ids.amount_residual_usd',
    )
    def _compute_amount(self):
        for move in self:
            # activa flags para tu dual currency
            self.env.context = dict(self.env.context, tasa_factura=move.tax_today, calcular_dual_currency=True)
            # llama al compute core (recalcula amount_residual, payment_state, etc.)
            super(AccountMove, self)._compute_amount()

            # ahora tu lógica USD custom
            total_residual = 0.0
            total = 0.0
            if move.is_invoice(include_receipts=True):
                for line in move.line_ids:
                    if line.display_type in ('tax', 'rounding') and line.tax_repartition_line_id:
                        total += line.balance_usd
                    elif line.display_type in ('product', 'rounding'):
                        total += line.balance_usd
                    elif line.display_type == 'payment_term':
                        total_residual += line.amount_residual_usd
            move.amount_residual_usd = total_residual
            move.amount_total_signed_usd = abs(total) if move.move_type == 'entry' else -total

        # limpia contexto
        self.env.context = dict(self.env.context, tasa_factura=None, calcular_dual_currency=False)

    @api.depends('currency_id_dif')
    def _name_ref(self):
        for record in self:
            record.name_rate = record.currency_id_dif.currency_unit_label

    invoice_payments_widget_bs = fields.Text(groups="account.group_account_invoice", copy=False)

    same_currency = fields.Boolean(string="Mismo tipo de moneda", compute='_same_currency')

    @api.depends('currency_id')
    def _same_currency(self):
        self.same_currency = self.currency_id == self.env.company.currency_id

    @api.depends('move_type', 'line_ids.amount_residual_usd')
    def _compute_payments_widget_reconciled_info_bs(self):
        for move in self:
            if move.state != 'posted' or not move.is_invoice(include_receipts=True):
                move.invoice_payments_widget_bs = json.dumps(False)
                continue
            reconciled_vals = move._get_reconciled_info_JSON_values_bs()
            if reconciled_vals:
                info = {
                    'title': _('Less Payment'),
                    'outstanding': False,
                    'content': reconciled_vals,
                }
                move.invoice_payments_widget_bs = json.dumps(info, default=date_utils.json_default)
            else:
                move.invoice_payments_widget_bs = json.dumps(False)

    def _compute_payments_widget_to_reconcile_info(self):
        for move in self:
            move.invoice_outstanding_credits_debits_widget = False
            move.invoice_has_outstanding = False

            if move.state != 'posted' \
                    or move.payment_state not in ('not_paid', 'partial') \
                    or not move.is_invoice(include_receipts=True):
                continue

            pay_term_lines = move.line_ids \
                .filtered(lambda line: line.account_id.account_type in ('asset_receivable', 'liability_payable'))

            domain = [
                ('account_id', 'in', pay_term_lines.account_id.ids),
                ('parent_state', '=', 'posted'),
                ('partner_id', '=', move.commercial_partner_id.id),
                ('reconciled', '=', False),
                '|','|', ('amount_residual', '!=', 0.0), ('amount_residual_usd', '!=', 0.0),('amount_residual_currency', '!=', 0.0),
            ]

            payments_widget_vals = {'outstanding': True, 'content': [], 'move_id': move.id}

            if move.is_inbound():
                domain.append(('balance', '<', 0.0))
                payments_widget_vals['title'] = _('Outstanding credits')
            else:
                domain.append(('balance', '>', 0.0))
                payments_widget_vals['title'] = _('Outstanding debits')

            for line in self.env['account.move.line'].search(domain):
                if line.debit == 0 and line.credit == 0 and not line.full_reconcile_id:
                    if abs(line.amount_residual_usd) > 0:
                        payments_widget_vals['content'].append({
                            'journal_name': line.ref or line.move_id.name,
                            'amount': 0,
                            'amount_usd': abs(line.amount_residual_usd),
                            'currency_id': move.currency_id.id,
                            'currency_id_dif': move.currency_id_dif.id,
                            'id': line.id,
                            'move_id': line.move_id.id,
                            'date': fields.Date.to_string(line.date),
                            'account_payment_id': line.payment_id.id,
                        })
                        continue
                if line.currency_id == move.currency_id:
                    # Same foreign currency.
                    amount = abs(line.amount_residual_currency)
                    amount_usd = abs(line.amount_residual_usd)
                else:
                    # Different foreign currencies.
                    amount = line.company_currency_id._convert(
                        abs(line.amount_residual),
                        move.currency_id,
                        move.company_id,
                        line.date,
                    )
                    amount_usd = abs(line.amount_residual_usd)

                if move.currency_id.is_zero(amount) and amount_usd == 0:
                    continue

                payments_widget_vals['content'].append({
                    'journal_name': line.ref or line.move_id.name,
                    'amount': amount,
                    'amount_usd': amount_usd,
                    'currency_id': move.currency_id.id,
                    'currency_id_dif': move.currency_id_dif.id,
                    'id': line.id,
                    'move_id': line.move_id.id,
                    'date': fields.Date.to_string(line.date),
                    'account_payment_id': line.payment_id.id,
                })

            if not payments_widget_vals['content']:
                continue
            ###print(payments_widget_vals)
            move.invoice_outstanding_credits_debits_widget = payments_widget_vals
            move.invoice_has_outstanding = True
    
    def js_remove_outstanding_partial(self, partial_id):
        ''' Called by the 'payment' widget to remove a reconciled entry to the present invoice.

        :param partial_id: The id of an existing partial reconciled with the current invoice.
        '''
        self.ensure_one()
        partial = self.env['account.partial.reconcile'].browse(partial_id)
        debit_move_id = partial.debit_move_id
        credit_move_id = partial.credit_move_id
        partial.unlink()
        if debit_move_id and credit_move_id:
            debit_move_id._compute_amount_residual_usd()
            credit_move_id._compute_amount_residual_usd()
        return True

    def _get_reconciled_info_JSON_values_bs(self):
        self.ensure_one()
        reconciled_vals = []
        pay_term_line_ids = self.line_ids.filtered(
            lambda line: line.account_id.account_type in ('asset_receivable', 'liability_payable')
        )
        partials = pay_term_line_ids.mapped('matched_debit_ids') + pay_term_line_ids.mapped('matched_credit_ids')
        seen_lines = set()
        for partial in partials:
            # Busca la línea de pago (que NO es de la factura)
            lines = partial.debit_move_id + partial.credit_move_id
            counterpart_line = lines.filtered(lambda l: l not in self.line_ids)
            if not counterpart_line or counterpart_line.id in seen_lines:
                continue
            seen_lines.add(counterpart_line.id)
            # Solo pagos en Bs (VES o VEF)
            vef = self.env.ref('base.VEF', raise_if_not_found=False) or self.env['res.currency'].search([('name', 'in', ['VES', 'VEF'])], limit=1)
            if not vef or counterpart_line.currency_id.id != vef.id:
                continue
            pago_amount = abs(counterpart_line.amount_currency)
            ref = counterpart_line.move_id.name
            if counterpart_line.move_id.ref:
                ref += ' (' + counterpart_line.move_id.ref + ')'
            reconciled_vals.append({
                'name': counterpart_line.name,
                'journal_name': counterpart_line.journal_id.name,
                'amount': pago_amount,
                'currency': vef.symbol,
                'digits': [69, 2],
                'position': vef.position,
                'date': counterpart_line.date,
                'payment_id': counterpart_line.id,
                'account_payment_id': counterpart_line.payment_id.id,
                'payment_method_name': getattr(counterpart_line.payment_id.payment_method_line_id, "name", ""),
                'move_id': counterpart_line.move_id.id,
                'ref': ref,
            })
        return reconciled_vals

    def _get_all_reconciled_invoice_partials_USD(self):
        self.ensure_one()
        reconciled_lines = self.line_ids.filtered(lambda line: line.account_id.account_type in ('asset_receivable', 'liability_payable'))
        if not reconciled_lines:
            return {}

        query = '''
            SELECT
                part.id,
                part.exchange_move_id,
                part.amount_usd AS amount,
                part.credit_move_id AS counterpart_line_id
            FROM account_partial_reconcile part
            WHERE part.debit_move_id IN %s

            UNION ALL

            SELECT
                part.id,
                part.exchange_move_id,
                part.amount_usd AS amount,
                part.debit_move_id AS counterpart_line_id
            FROM account_partial_reconcile part
            WHERE part.credit_move_id IN %s
        '''
        self._cr.execute(query, [tuple(reconciled_lines.ids)] * 2)

        partial_values_list = []
        counterpart_line_ids = set()
        exchange_move_ids = set()
        for values in self._cr.dictfetchall():
            partial_values_list.append({
                'aml_id': values['counterpart_line_id'],
                'partial_id': values['id'],
                'amount': values['amount'],
                'currency': self.currency_id,
            })
            counterpart_line_ids.add(values['counterpart_line_id'])
            if values['exchange_move_id']:
                exchange_move_ids.add(values['exchange_move_id'])

        if exchange_move_ids:
            query = '''
                SELECT
                    part.id,
                    part.credit_move_id AS counterpart_line_id
                FROM account_partial_reconcile part
                JOIN account_move_line credit_line ON credit_line.id = part.credit_move_id
                WHERE credit_line.move_id IN %s AND part.debit_move_id IN %s

                UNION ALL

                SELECT
                    part.id,
                    part.debit_move_id AS counterpart_line_id
                FROM account_partial_reconcile part
                JOIN account_move_line debit_line ON debit_line.id = part.debit_move_id
                WHERE debit_line.move_id IN %s AND part.credit_move_id IN %s
            '''
            self._cr.execute(query, [tuple(exchange_move_ids), tuple(counterpart_line_ids)] * 2)

            for values in self._cr.dictfetchall():
                counterpart_line_ids.add(values['counterpart_line_id'])
                partial_values_list.append({
                    'aml_id': values['counterpart_line_id'],
                    'partial_id': values['id'],
                    'currency': self.company_id.currency_id,
                })

        counterpart_lines = {x.id: x for x in self.env['account.move.line'].browse(counterpart_line_ids)}
        for partial_values in partial_values_list:
            partial_values['aml'] = counterpart_lines[partial_values['aml_id']]
            partial_values['is_exchange'] = partial_values['aml'].move_id.id in exchange_move_ids
            if partial_values['is_exchange']:
                partial_values['amount'] = abs(partial_values['aml'].balance_usd)

        return partial_values_list

    @api.depends('move_type', 'line_ids.amount_residual_usd')
    def _compute_payments_widget_reconciled_info_USD(self):
        for move in self:
            payments_widget_vals = {'title': _('Less Payment'), 'outstanding': False, 'content': []}
            total_pagado = 0
            if move.state == 'posted' and move.is_invoice(include_receipts=True):
                reconciled_vals = []
                reconciled_partials = move._get_all_reconciled_invoice_partials_USD()

                for reconciled_partial in reconciled_partials:
                    counterpart_line = reconciled_partial['aml']
                    if counterpart_line.move_id.ref:
                        reconciliation_ref = '%s (%s)' % (counterpart_line.move_id.name, counterpart_line.move_id.ref)
                    else:
                        reconciliation_ref = counterpart_line.move_id.name
                    if counterpart_line.amount_currency and counterpart_line.currency_id != counterpart_line.company_id.currency_id:
                        foreign_currency = counterpart_line.currency_id
                    else:
                        foreign_currency = False
                    total_pagado = total_pagado + float(reconciled_partial['amount'])
                    reconciled_vals.append({
                        'name': counterpart_line.name,
                        'journal_name': counterpart_line.journal_id.name,
                        'amount': reconciled_partial['amount'],
                        'currency_id': move.company_id.currency_id_dif.id if move.company_id.currency_id_dif else
                        move.company_id.currency_id.id,
                        'date': counterpart_line.date,
                        'partial_id': reconciled_partial['partial_id'],
                        'account_payment_id': counterpart_line.payment_id.id,
                        'payment_method_name': counterpart_line.payment_id.payment_method_line_id.name,
                        'move_id': counterpart_line.move_id.id,
                        'ref': reconciliation_ref,
                        # these are necessary for the views to change depending on the values
                        'is_exchange': reconciled_partial['is_exchange'],
                        'amount_company_currency': formatLang(self.env, abs(counterpart_line.balance_usd),
                                                              currency_obj=counterpart_line.company_id.currency_id_dif),
                        'amount_foreign_currency': foreign_currency and formatLang(self.env,
                                                                                   abs(counterpart_line.amount_currency),
                                                                                   currency_obj=foreign_currency)
                    })
                payments_widget_vals['content'] = reconciled_vals

            if payments_widget_vals['content']:
                move.invoice_payments_widget_usd = payments_widget_vals
                if total_pagado < move.amount_total_usd:
                    move.amount_residual_usd = move.amount_total_usd - total_pagado
                else:
                    move.amount_residual_usd = 0
                # if move.amount_residual_usd > 0:
                #     move.payment_state = 'partial'
                # else:
                #     move.payment_state = 'paid'
            else:
                move.amount_residual_usd = move.amount_total_usd
                move.invoice_payments_widget_usd = False


    def _verificar_pagos(self):
        for rec in self:
            for line in rec.line_ids:
                if line.balance_usd == 0:
                    line._compute_balance_usd()
                line._compute_amount_residual_usd()
            rec.verificar_pagos = True

    @api.onchange('invoice_date', 'date', 'currency_id')
    def _onchange_update_tax_today(self):
        usd_currency = self.env.ref('base.USD')
        for move in self:
            fecha = move.invoice_date or move.date or fields.Date.context_today(self)
            tasa = self.env['res.currency.rate'].search([
                ('currency_id', '=', usd_currency.id),
                ('name', '=', fecha),
                ('company_id', '=', move.company_id.id)
            ], limit=1)
            move.tax_today = tasa.inverse_company_rate if tasa else 1.0

    @api.model
    def cron_recompute_tax_today(self):
        usd_currency = self.env.ref('base.USD')
        count = 0
        moves = self.search([('tax_today', '=', 1.0)])
        for move in moves:
            fecha = move.invoice_date or move.date or fields.Date.context_today(self)
            tasa = self.env['res.currency.rate'].search([
                ('currency_id', '=', usd_currency.id),
                ('name', '=', fecha),
                ('company_id', '=', move.company_id.id)
            ], limit=1)
            if tasa:
                move.tax_today = tasa.inverse_company_rate
                count += 1

        self.env['ir.logging'].create({
            'name': 'Recompute Tax Today (Move)',
            'type': 'server',
            'dbname': self.env.cr.dbname,
            'level': 'INFO',
            'message': f'{count} asientos contables actualizados con tasa USD',
            'path': 'account.move',
            'line': '0',
            'func': 'cron_recompute_tax_today',
        })
        return count

    @api.depends('currency_id')
    def _compute_is_bs_invoice(self):
        vef = self.env.ref('base.VEF', raise_if_not_found=False) or self.env['res.currency'].search([('name', 'in', ['VES', 'VEF'])], limit=1)
        for rec in self:
            rec.is_bs_invoice = bool(vef and rec.currency_id.id == vef.id)

    @api.depends('tax_totals', 'tax_today', 'currency_id')
    def _compute_amount_all_usd(self):
        vef = self.env.ref('base.VEF', raise_if_not_found=False) or self.env['res.currency'].search([('name', 'in', ['VES', 'VEF'])], limit=1)
        for rec in self:
            rec.amount_untaxed_usd = rec.amount_tax_usd = rec.amount_total_usd = 0
            rec.amount_untaxed_bs = rec.amount_tax_bs = rec.amount_total_bs = 0
            if not rec.tax_totals:
                continue
            amount_untaxed = rec.tax_totals.get('amount_untaxed', 0)
            amount_tax = sum(
                l['tax_group_amount']
                for group in rec.tax_totals.get('groups_by_subtotal', {}).values()
                for l in group
            )
            amount_total = rec.tax_totals.get('amount_total', 0)

            is_bs = bool(vef and rec.currency_id.id == vef.id)
            tasa = rec.tax_today or 1

            if is_bs:
                rec.amount_untaxed_usd = amount_untaxed / tasa if tasa else 0
                rec.amount_tax_usd = amount_tax / tasa if tasa else 0
                rec.amount_total_usd = amount_total / tasa if tasa else 0
                rec.amount_untaxed_bs = amount_untaxed
                rec.amount_tax_bs = amount_tax
                rec.amount_total_bs = amount_total
            else:
                rec.amount_untaxed_usd = amount_untaxed
                rec.amount_tax_usd = amount_tax
                rec.amount_total_usd = amount_total
                rec.amount_untaxed_bs = amount_untaxed * tasa
                rec.amount_tax_bs = amount_tax * tasa
                rec.amount_total_bs = amount_total * tasa

    
    def _fecha_para_tax_today(self, vals=None):
        # Para entradas de diario usar siempre la fecha contable
        if (vals and vals.get('move_type') == 'entry') or (not vals and self.move_type == 'entry'):
            if vals:
                return vals.get('date') or self.date
            return self.date
        # Para otros: invoice_date > date
        if vals:
            return vals.get('invoice_date') or vals.get('date') or self.invoice_date or self.date
        return self.invoice_date or self.date
    
    def _get_tasa_usd_by_date(self, fecha, company=None):
        # Normaliza fecha y busca la tasa USD → local (inverse_company_rate)
        if isinstance(fecha, (fields.Date.__class__,)):
            fecha_str = fields.Date.to_string(fecha)
        else:
            fecha_str = str(fecha)
        usd = self.env.ref('base.USD')
        company = company or self.env.company
        tasa = self.env['res.currency.rate'].search([
            ('currency_id', '=', usd.id),
            ('name', '=', fecha_str),
            ('company_id', '=', company.id)
        ], limit=1)
        return tasa.inverse_company_rate if tasa else 1.0
    
    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)

        for move, vals in zip(moves, vals_list):
            j = move.journal_id
            is_fx_journal = bool(getattr(j, 'is_exchange_diff_journal', False) or
                                getattr(j, 'is_fx_diff_journal', False))

            if is_fx_journal and move.move_type == 'entry':
                # Asientos de DIF CAMBIO → forzar tasa=0 y dual=0
                if move.tax_today != 0.0:
                    move.with_context(skip_tax_today_update=True).write({'tax_today': 0.0})
                move.line_ids.write({
                    'tax_today': 0.0,
                    'debit_usd': 0.0,
                    'credit_usd': 0.0,
                    'balance_usd': 0.0,
                })
                _logger.info("[DUAL] create(): move %s (FX diff) -> tasa=0 y dual=0", move.id)

            else:
                # Documentos normales (facturas/pagos)
                if move.move_type in ('out_refund', 'in_refund'):
                    continue  # no recalcular en NC

                if vals.get('tax_today'):
                    continue  # respetar si venía en vals

                fecha = move._fecha_para_tax_today()
                tasa = move._get_tasa_usd_by_date(fecha, move.company_id)
                if move.tax_today != tasa:
                    move.with_context(skip_tax_today_update=True).write({'tax_today': tasa})

                # Asegurar recompute dual currency en líneas
                # 🔧 FIX: No recomputar si viene con contexto de valorización
                if not self.env.context.get('skip_usd_recompute'):
                    try:
                        lines = move.line_ids
                        lines._compute_tax_today()
                        lines._compute_debit_usd()
                        lines._compute_credit_usd()
                        lines._compute_balance_usd()
                        _logger.info("[DUAL] create(): move %s recompute dual OK", move.id)
                    except Exception as e:
                        _logger.exception("[DUAL] create(): fallo recompute dual en move %s: %s", move.id, e)
                else:
                    _logger.info("[DUAL] create(): move %s SKIP recompute (valorización inventario)", move.id)
                
                # 🔧 FIX ADICIONAL: Restaurar valores USD de valorización de salidas
                # Esto se ejecuta DESPUÉS del recompute para asegurar valores correctos
                if hasattr(move, 'stock_valuation_layer_ids') and move.stock_valuation_layer_ids:
                    for svl in move.stock_valuation_layer_ids:
                        # Solo para salidas desde ubicaciones internas
                        if (svl.quantity < 0 and svl.stock_move_id and 
                            svl.stock_move_id.location_id.usage == 'internal' and
                            svl.product_id.standard_price_usd):
                            
                            _logger.info(f"[DUAL] Restaurando USD de valorización para SVL {svl.id}")
                            
                            qty_abs = abs(svl.quantity)
                            value_usd = qty_abs * svl.product_id.standard_price_usd

                            # Actualizar líneas con SQL directo
                            updated_ids = []
                            for line in move.line_ids:
                                if line.debit > 0:
                                    self.env.cr.execute("""
                                        UPDATE account_move_line 
                                        SET debit_usd = %s, credit_usd = 0.0, balance_usd = %s
                                        WHERE id = %s
                                    """, (value_usd, value_usd, line.id))
                                    updated_ids.append(line.id)
                                elif line.credit > 0:
                                    self.env.cr.execute("""
                                        UPDATE account_move_line 
                                        SET debit_usd = 0.0, credit_usd = %s, balance_usd = %s
                                        WHERE id = %s
                                    """, (value_usd, -value_usd, line.id))
                                    updated_ids.append(line.id)

                            # Invalidar caché
                            move.line_ids.invalidate_recordset(['debit_usd', 'credit_usd', 'balance_usd'])

                            # Bloquear las líneas actualizadas para evitar recomputes posteriores
                            if updated_ids:
                                try:
                                    move.line_ids.filtered(lambda l: l.id in updated_ids).sudo().write({'usd_locked': True})
                                except Exception:
                                    _logger.exception('[DUAL] No se pudo marcar usd_locked en las líneas del move %s', move.id)

                            _logger.info(f"[DUAL] USD restaurado: {value_usd:.4f}")

                # Si este move fue creado como reverso de otro (nota de devolución),
                # copiar los valores USD del move original pero invertidos (mirror):
                # debit_usd del reverso = credit_usd del original, y viceversa.
                if move.reversed_entry_id:
                    try:
                        orig = move.reversed_entry_id
                        _logger.info('[DUAL] move %s es reverso de %s - restaurando USD invertidos', move.id, orig.id)
                        updated_ids = []
                        for line in move.line_ids:
                            # Encontrar línea original que comparta la misma cuenta
                            candidates = orig.line_ids.filtered(lambda l: l.account_id.id == line.account_id.id)
                            orig_line = None
                            if len(candidates) == 1:
                                orig_line = candidates[0]
                            elif len(candidates) > 1:
                                # Preferir la línea con signo opuesto
                                if line.debit > 0:
                                    cand = candidates.filtered(lambda l: l.credit > 0)
                                    orig_line = cand and cand[0] or candidates[0]
                                elif line.credit > 0:
                                    cand = candidates.filtered(lambda l: l.debit > 0)
                                    orig_line = cand and cand[0] or candidates[0]

                            if not orig_line:
                                continue

                            # Asignar valores USD invertidos según el signo de la línea nueva
                            if line.debit > 0:
                                val = orig_line.credit_usd or 0.0
                                self.env.cr.execute("""
                                    UPDATE account_move_line
                                    SET debit_usd = %s, credit_usd = 0.0, balance_usd = %s
                                    WHERE id = %s
                                """, (val, val, line.id))
                                updated_ids.append(line.id)
                            elif line.credit > 0:
                                val = orig_line.debit_usd or 0.0
                                self.env.cr.execute("""
                                    UPDATE account_move_line
                                    SET debit_usd = 0.0, credit_usd = %s, balance_usd = %s
                                    WHERE id = %s
                                """, (val, -val, line.id))
                                updated_ids.append(line.id)

                        if updated_ids:
                            # Invalidar caché para los campos afectados
                            move.line_ids.invalidate_recordset(['debit_usd', 'credit_usd', 'balance_usd'])
                            try:
                                move.line_ids.filtered(lambda l: l.id in updated_ids).sudo().write({'usd_locked': True})
                            except Exception:
                                _logger.exception('[DUAL] No se pudo marcar usd_locked en las líneas del move reverso %s', move.id)
                            _logger.info('[DUAL] Restauración USD invertida aplicada en move %s (ids: %s)', move.id, updated_ids)
                    except Exception:
                        _logger.exception('[DUAL] Error al restaurar USD invertidos para move %s', move.id)

            # Si el asiento es de depreciación de activo y viene tax_today del activo en el contexto
            if self.env.context.get('asset_tax_today') and move.asset_id:
                move.with_context(skip_tax_today_update=True).write({'tax_today': self.env.context.get('asset_tax_today')})
                continue
            
            # No forzamos recalculo en notas de crédito (heredan)
            if move.move_type in ('out_refund', 'in_refund'):
                continue
            # Si ya venía tax_today explícito, lo dejamos (excepto si quieres sobrescribir)
            if vals.get('tax_today'):
                continue
            fecha = move._fecha_para_tax_today()
            tasa = move._get_tasa_usd_by_date(fecha, move.company_id)
            if move.tax_today != tasa:
                move.with_context(skip_tax_today_update=True).write({'tax_today': tasa})
        return moves

    def write(self, vals):
        if self.env.context.get('skip_tax_today_update'):
            return super().write(vals)

        # 1. Detect if something that affects the calculation date was modified
        necesita_recalc = any(k in vals for k in ('date', 'invoice_date', 'move_type', 'company_id'))

        # 2. Perform the actual database write first
        res = super().write(vals)

        for move in self:
            j = move.journal_id
            
            # Determine if the journal is an FX difference journal
            is_fx_journal = bool(getattr(j, 'is_exchange_diff_journal', False) or
                                 getattr(j, 'is_fx_diff_journal', False))

            if is_fx_journal and move.move_type == 'entry':
                # --- LOGIC FOR FX DIFF JOURNAL (DIF CAMBIO) ---
                
                # Keep rate=0 and dual=0 in FX Difference entries
                if move.tax_today != 0.0:
                    # Use the explicit super call to skip inherited logic on the move header
                    super(AccountMove, move.with_context(skip_tax_today_update=True)).write({'tax_today': 0.0})
                
                # Force 0.0 on all dual currency fields on the move lines
                move.line_ids.write({
                    'tax_today': 0.0,
                    'debit_usd': 0.0,
                    'credit_usd': 0.0,
                    'balance_usd': 0.0,
                })
                _logger.info("[DUAL] write(): move %s (FX diff) -> tasa=0 y dual=0", move.id)
                
                # Skip normal recalculation for this move
                continue

            # --- NORMAL DOCUMENT RECALCULATION LOGIC ---

            # Skip if no relevant fields were changed (optimization)
            if not necesita_recalc:
                continue

            if move.move_type in ('out_refund', 'in_refund'):
                continue  # no recalculate on credit notes (refunds)

            # Respect if 'tax_today' was set explicitly in vals
            if 'tax_today' in vals:
                continue

            # Calculate and update tax_today on the move header
            fecha = move._fecha_para_tax_today(vals)
            tasa = move._get_tasa_usd_by_date(fecha, move.company_id)
            if move.tax_today != tasa:
                move.with_context(skip_tax_today_update=True).write({'tax_today': tasa})

            # Ensure recompute of dual currency on lines
            try:
                lines = move.line_ids
                lines._compute_tax_today()
                lines._compute_debit_usd()
                lines._compute_credit_usd()
                lines._compute_balance_usd()
                _logger.info("[DUAL] write(): move %s recompute dual OK", move.id)
            except Exception as e:
                _logger.exception("[DUAL] write(): fallo recompute dual en move %s: %s", move.id, e)

            # Si este move acaba de recibir la referencia a un move original (reverso),
            # restaurar los valores USD invertidos igual que en create(). Esto cubre
            # el caso donde el reverso se crea primero y luego se vincula al original
            # mediante un write posterior.
            try:
                if 'reversed_entry_id' in vals or (move.reversed_entry_id and not move.line_ids.filtered('usd_locked')):
                    if move.reversed_entry_id:
                        orig = move.reversed_entry_id
                        _logger.info('[DUAL] write(): move %s es reverso de %s - aplicando USD invertidos', move.id, orig.id)
                        updated_ids = []
                        for line in move.line_ids:
                            candidates = orig.line_ids.filtered(lambda l: l.account_id.id == line.account_id.id)
                            orig_line = None
                            if len(candidates) == 1:
                                orig_line = candidates[0]
                            elif len(candidates) > 1:
                                if line.debit > 0:
                                    cand = candidates.filtered(lambda l: l.credit > 0)
                                    orig_line = cand and cand[0] or candidates[0]
                                elif line.credit > 0:
                                    cand = candidates.filtered(lambda l: l.debit > 0)
                                    orig_line = cand and cand[0] or candidates[0]

                            if not orig_line:
                                continue

                            if line.debit > 0:
                                val = orig_line.credit_usd or 0.0
                                self.env.cr.execute("""
                                    UPDATE account_move_line
                                    SET debit_usd = %s, credit_usd = 0.0, balance_usd = %s
                                    WHERE id = %s
                                """, (val, val, line.id))
                                updated_ids.append(line.id)
                            elif line.credit > 0:
                                val = orig_line.debit_usd or 0.0
                                self.env.cr.execute("""
                                    UPDATE account_move_line
                                    SET debit_usd = 0.0, credit_usd = %s, balance_usd = %s
                                    WHERE id = %s
                                """, (val, -val, line.id))
                                updated_ids.append(line.id)

                        if updated_ids:
                            move.line_ids.invalidate_recordset(['debit_usd', 'credit_usd', 'balance_usd'])
                            try:
                                move.line_ids.filtered(lambda l: l.id in updated_ids).sudo().write({'usd_locked': True})
                            except Exception:
                                _logger.exception('[DUAL] write(): No se pudo marcar usd_locked en las líneas del reverso %s', move.id)
                            _logger.info('[DUAL] write(): USD invertidos aplicados en move %s (ids: %s)', move.id, updated_ids)
            except Exception:
                _logger.exception('[DUAL] write(): fallo al aplicar USD invertidos en move %s', move.id)

        return res

    @api.depends('state', 'move_type', 'amount_total_usd', 'line_ids.matched_debit_ids.amount_usd', 'line_ids.matched_credit_ids.amount_usd')
    def _compute_amount_residual_usd(self):
        """
        El amount_residual_usd en la factura es simplemente el total en USD menos la suma
        de todos los amount_usd de los partial reconcile aplicados a sus líneas de cobro/pago.
        """
        for move in self:
            if not move.is_invoice(include_receipts=True) or move.state != 'posted':
                move.amount_residual_usd = 0.0
                continue

            # Total en USD de la factura
            total_usd = move.amount_total_usd or 0.0

            # Sumar los amount_usd de todos los partial reconcile de líneas cobrables/pagables
            pay_term_lines = move.line_ids.filtered(
                lambda l: l.account_id.account_type in ('asset_receivable', 'liability_payable')
            )
            # Todos los partials asociados a las líneas de pago/cobro
            partials = pay_term_lines.mapped('matched_debit_ids') + pay_term_lines.mapped('matched_credit_ids')
            total_pagado_usd = sum(p.amount_usd or 0.0 for p in partials)

            move.amount_residual_usd = max(0.0, round(total_usd - total_pagado_usd, 2))


    @api.depends('move_type', 'line_ids.amount_residual_usd')
    def _compute_payments_widget_usd(self):
        for move in self:
            payments_widget_vals = {'title': _('Less Payment'), 'outstanding': False, 'content': []}
            if move.state == 'posted' and move.is_invoice(include_receipts=True):
                reconciled_vals = []
                reconciled_partials = move._get_all_reconciled_invoice_partials_usd()
                lines_seen = set()
                for reconciled_partial in reconciled_partials:
                    line = reconciled_partial['aml']
                    if not line or line.id in lines_seen:
                        continue
                    lines_seen.add(line.id)
                    ref = line.move_id.name
                    if line.move_id.ref:
                        ref += ' (%s)' % line.move_id.ref

                    # SIEMPRE usa amount_usd del partial, sea pago en Bs o USD
                    pago_amount_usd = abs(reconciled_partial['amount'])  # Este campo siempre es USD

                    reconciled_vals.append({
                        'name': line.name,
                        'journal_name': line.journal_id.name,
                        'amount': round(pago_amount_usd, 2),
                        'currency_id': move.currency_id_dif.id,
                        'date': line.date,
                        'partial_id': reconciled_partial['partial_id'],
                        'account_payment_id': line.payment_id.id,
                        'payment_method_name': getattr(line.payment_id.payment_method_line_id, "name", ""),
                        'move_id': line.move_id.id,
                        'ref': ref,
                        'is_exchange': reconciled_partial['is_exchange'],
                    })
                payments_widget_vals['content'] = reconciled_vals

            move.invoice_payments_widget_usd = payments_widget_vals if payments_widget_vals['content'] else False

            pagado_real = sum(line['amount'] for line in payments_widget_vals['content']) if payments_widget_vals['content'] else 0.0
            move.amount_residual_usd = max(0.0, (move.amount_total_usd or 0.0) - pagado_real)


    def _get_all_reconciled_invoice_partials_usd(self):
        self.ensure_one()
        reconciled_lines = self.line_ids.filtered(
            lambda l: l.account_id.account_type in ('asset_receivable', 'liability_payable')
        )
        if not reconciled_lines:
            return []
        query = '''
            SELECT part.id, part.amount_usd, part.amount, part.debit_move_id, part.credit_move_id, 
                part.exchange_move_id, debit_line.currency_id AS debit_currency_id, debit_line.date AS debit_date,
                credit_line.currency_id AS credit_currency_id, credit_line.date AS credit_date
            FROM account_partial_reconcile part
            JOIN account_move_line debit_line ON debit_line.id = part.debit_move_id
            JOIN account_move_line credit_line ON credit_line.id = part.credit_move_id
            WHERE part.debit_move_id IN %s OR part.credit_move_id IN %s
        '''
        self.env.cr.execute(query, [tuple(reconciled_lines.ids)] * 2)
        results = self.env.cr.dictfetchall()
        aml_ids = set()
        for r in results:
            if r['credit_move_id']:
                aml_ids.add(r['credit_move_id'])
            if r['debit_move_id']:
                aml_ids.add(r['debit_move_id'])
        aml_map = {l.id: l for l in self.env['account.move.line'].browse(aml_ids)}
        output = []
        usd = self.env.ref('base.USD')
        for r in results:
            # Busca siempre la línea de pago (la que NO está en la factura)
            aml_id = r['credit_move_id'] if r['credit_move_id'] not in reconciled_lines.ids else r['debit_move_id']
            aml = aml_map.get(aml_id)
            amount_usd = r['amount_usd']
            # Si amount_usd es None o cero, recalcula por compatibilidad
            if not amount_usd or amount_usd == 0.0:
                pago_currency_id = r['debit_currency_id'] if aml_id == r['debit_move_id'] else r['credit_currency_id']
                pago_date = r['debit_date'] if aml_id == r['debit_move_id'] else r['credit_date']
                amount = r['amount']
                if pago_currency_id == usd.id:
                    amount_usd = amount
                else:
                    tasa_pago = self._get_tasa_usd_by_date(pago_date)
                    amount_usd = amount / tasa_pago if tasa_pago else 0
            output.append({
                'partial_id': r['id'],
                'amount': amount_usd,
                'aml': aml,
                'is_exchange': bool(r['exchange_move_id']),
            })
        return output
