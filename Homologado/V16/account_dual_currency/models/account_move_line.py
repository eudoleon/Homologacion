# -*- coding: utf-8 -*-
from collections import defaultdict
from contextlib import contextmanager
from datetime import date, timedelta
from functools import lru_cache

from odoo import api, fields, models, Command, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import frozendict, formatLang, format_date, float_compare, Query



class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    debit_usd = fields.Monetary(
        string='Débito $',
        currency_field='currency_id_dif',
        store=True,
        compute='_compute_debit_usd',
        readonly=False
    )
    credit_usd = fields.Monetary(
        string='Crédito $',
        currency_field='currency_id_dif',
        store=True,
        compute='_compute_credit_usd',
        readonly=False
    )
    balance_usd = fields.Monetary(
        string='Balance $',
        currency_field='currency_id_dif',
        store=True,
        compute='_compute_balance_usd',
        readonly=False
    )
    tax_today = fields.Float(
        string='Tasa',
        store=True,
        compute='_compute_tax_today'
    )
    currency_id_dif = fields.Many2one(
        'res.currency',
        related='move_id.currency_id_dif',
        store=True
    )
    amount_residual_usd = fields.Monetary(
        string="Residual USD",
        currency_field="currency_id_dif",
        compute="_compute_amount_residual_usd",
        store=True,
    )
    reconciled = fields.Boolean(
        string="Conciliado USD",
        compute="_compute_reconciled_usd",
        store=True,
    )

    @api.model
    def recompute_tax_today_and_usd_fields(self):
        lines = self.search([
            ('tax_today', 'in', [0.0, 0.01, 1.0])
        ])
        count = 0
        for line in lines:
            line._compute_tax_today()
            line._compute_debit_usd()
            line._compute_credit_usd()
            line._compute_balance_usd()
            line._compute_amount_residual_usd()
            line._compute_reconciled_usd()
            count += 1
        _logger = self.env['ir.logging']
        _logger.create({
            'name': 'Recompute Tax Today',
            'type': 'server',
            'dbname': self.env.cr.dbname,
            'level': 'INFO',
            'message': f'{count} líneas contables actualizadas con recompute de tasa y USD',
            'path': 'account.move.line',
            'line': '0',
            'func': 'recompute_tax_today_and_usd_fields',
        })
        return count

    @api.depends('move_id.tax_today')
    def _compute_tax_today(self):
        for rec in self:
            # Si el move tiene una tasa explícita, úsala directamente
            if rec.move_id and rec.move_id.tax_today and rec.move_id.tax_today != 1.0:
                rec.tax_today = rec.move_id.tax_today
                continue
            
            # Si es una nota de crédito con reversed_entry_id, heredar tasa de la factura original
            if rec.move_id and rec.move_id.move_type in ('out_refund', 'in_refund') and rec.move_id.reversed_entry_id:
                if rec.move_id.reversed_entry_id.tax_today and rec.move_id.reversed_entry_id.tax_today != 1.0:
                    rec.tax_today = rec.move_id.reversed_entry_id.tax_today
                    continue

            # Si no tiene una tasa válida, la calculas
            rate = 1.0
            usd_currency = rec.env.ref('base.USD')
            vef_currency = rec.env.ref('base.VEF', raise_if_not_found=False) or rec.env['res.currency'].search([
                ('name', 'in', ['VES', 'VEF'])], limit=1)

            if rec.move_id and rec.move_id.date and rec.move_id.company_id:
                rate_obj = rec.env['res.currency.rate'].search([
                    ('currency_id', '=', usd_currency.id),
                    ('name', '=', rec.move_id.invoice_date or rec.move_id.date),
                    ('company_id', '=', rec.move_id.company_id.id)
                ], limit=1)
                if rate_obj:
                    rate = rate_obj.inverse_company_rate or 1.0

            rec.tax_today = rate

    def _get_real_tax_today(self):
        self.ensure_one()
        
        # Si es una nota de crédito con reversed_entry_id, usar la tasa de la factura original
        if self.move_id.move_type in ('out_refund', 'in_refund') and self.move_id.reversed_entry_id:
            if self.move_id.reversed_entry_id.tax_today and self.move_id.reversed_entry_id.tax_today != 1.0:
                return self.move_id.reversed_entry_id.tax_today
        
        # Si tiene una tasa válida, usarla
        if self.tax_today and self.tax_today != 1.0:
            return self.tax_today
            
        # Buscar la tasa del día
        usd_currency = self.env.ref('base.USD')
        vef_currency = self.env.ref('base.VEF', raise_if_not_found=False) or self.env['res.currency'].search([('name', 'in', ['VES', 'VEF'])], limit=1)
        rate_obj = self.env['res.currency.rate'].search([
            ('currency_id', '=', usd_currency.id),
            ('name', '=', self.move_id.invoice_date or self.move_id.date),
            ('company_id', '=', self.company_id.id)
        ], limit=1)
        return rate_obj.inverse_company_rate if rate_obj else 1.0

    @api.depends('debit', 'tax_today')
    def _compute_debit_usd(self):
        for rec in self:
            rate = rec._get_real_tax_today()
            rec.debit_usd = rec.debit / rate if rec.debit > 0 and rate else 0.0

    @api.depends('credit', 'tax_today')
    def _compute_credit_usd(self):
        for rec in self:
            rate = rec._get_real_tax_today()
            rec.credit_usd = rec.credit / rate if rec.credit > 0 and rate else 0.0

    @api.depends('debit_usd', 'credit_usd')
    def _compute_balance_usd(self):
        for rec in self:
            rec.balance_usd = rec.debit_usd - rec.credit_usd

    @api.depends('debit','credit','debit_usd', 'credit_usd', 'amount_currency', 'account_id', 'currency_id', 'move_id.state',
                 'company_id',
                 'matched_debit_ids', 'matched_credit_ids')
    def _compute_amount_residual_usd(self):
        """ Computes the residual amount of a move line from a reconcilable account in the company currency and the line's currency.
            This amount will be 0 for fully reconciled lines or lines from a non-reconcilable account, the original line amount
            for unreconciled lines, and something in-between for partially reconciled lines.
        """
        for line in self:
            if line.id and (line.account_id.reconcile or line.account_id.account_type in ('asset_cash', 'liability_credit_card')):
                reconciled_balance = sum(line.matched_credit_ids.mapped('amount_usd')) \
                                     - sum(line.matched_debit_ids.mapped('amount_usd'))

                line.amount_residual_usd = (line.debit_usd - line.credit_usd) - reconciled_balance

                line.reconciled = (line.amount_residual_usd == 0)
            else:
                # Must not have any reconciliation since the line is not eligible for that.
                line.amount_residual_usd = 0.0
                line.reconciled = False

    def reconcile(self):
        ''' Reconcile the current move lines all together.
        :return: A dictionary representing a summary of what has been done during the reconciliation:
                * partials:             A recorset of all account.partial.reconcile created during the reconciliation.
                * exchange_partials:    A recorset of all account.partial.reconcile created during the reconciliation
                                        with the exchange difference journal entries.
                * full_reconcile:       An account.full.reconcile record created when there is nothing left to reconcile
                                        in the involved lines.
                * tax_cash_basis_moves: An account.move recordset representing the tax cash basis journal entries.
        '''
        self = self.with_context(no_exchange_difference=True)
        results = {'exchange_partials': self.env['account.partial.reconcile']}

        if not self:
            return results

        not_paid_invoices = self.move_id.filtered(lambda move:
            move.is_invoice(include_receipts=True)
            and move.payment_state not in ('paid', 'in_payment')
        )

        # ==== Check the lines can be reconciled together ====
        company = None
        account = None
        for line in self:
            #if line.reconciled:
            #    raise UserError(_("You are trying to reconcile some entries that are already reconciled."))
            if not line.account_id.reconcile and line.account_id.account_type not in ('asset_cash', 'liability_credit_card'):
                raise UserError(_("Account %s does not allow reconciliation. First change the configuration of this account to allow it.")
                                % line.account_id.display_name)
            if line.move_id.state != 'posted':
                raise UserError(_('You can only reconcile posted entries.'))
            if company is None:
                company = line.company_id
            elif line.company_id != company:
                raise UserError(_("Entries doesn't belong to the same company: %s != %s")
                                % (company.display_name, line.company_id.display_name))
            if account is None:
                account = line.account_id
            elif line.account_id != account:
                raise UserError(_("Entries are not from the same account: %s != %s")
                                % (account.display_name, line.account_id.display_name))

        sorted_lines = self.sorted(key=lambda line: (line.date_maturity or line.date, line.currency_id, line.amount_currency))

        # ==== Collect all involved lines through the existing reconciliation ====

        involved_lines = sorted_lines._all_reconciled_lines()
        involved_partials = involved_lines.matched_credit_ids | involved_lines.matched_debit_ids

        # ==== Create partials ====

        partial_no_exch_diff = bool(self.env['ir.config_parameter'].sudo().get_param('account.disable_partial_exchange_diff'))
        sorted_lines_ctx = sorted_lines.with_context(no_exchange_difference=self._context.get('no_exchange_difference') or partial_no_exch_diff)
        partials = sorted_lines_ctx._create_reconciliation_partials()
        results['partials'] = partials
        involved_partials += partials
        exchange_move_lines = partials.exchange_move_id.line_ids.filtered(lambda line: line.account_id == account)
        involved_lines += exchange_move_lines
        exchange_diff_partials = exchange_move_lines.matched_debit_ids + exchange_move_lines.matched_credit_ids
        involved_partials += exchange_diff_partials
        results['exchange_partials'] += exchange_diff_partials

        # ==== Create entries for cash basis taxes ====

        is_cash_basis_needed = account.company_id.tax_exigibility and account.account_type in ('asset_receivable', 'liability_payable')
        if is_cash_basis_needed and not self._context.get('move_reverse_cancel'):
            tax_cash_basis_moves = partials._create_tax_cash_basis_moves()
            results['tax_cash_basis_moves'] = tax_cash_basis_moves

        # ==== Check if a full reconcile is needed ====

        def is_line_reconciled(line, has_multiple_currencies):
            # Check if the journal item passed as parameter is now fully reconciled.
            return line.reconciled \
                   or (line.company_currency_id.is_zero(line.amount_residual)
                       if has_multiple_currencies
                       else line.currency_id.is_zero(line.amount_residual_currency)
                   )

        has_multiple_currencies = len(involved_lines.currency_id) > 1
        if all(is_line_reconciled(line, has_multiple_currencies) for line in involved_lines):
            # ==== Create the exchange difference move ====
            # This part could be bypassed using the 'no_exchange_difference' key inside the context. This is useful
            # when importing a full accounting including the reconciliation like Winbooks.

            exchange_move = self.env['account.move']
            caba_lines_to_reconcile = None
            if not self._context.get('no_exchange_difference'):
                # In normal cases, the exchange differences are already generated by the partial at this point meaning
                # there is no journal item left with a zero amount residual in one currency but not in the other.
                # However, after a migration coming from an older version with an older partial reconciliation or due to
                # some rounding issues (when dealing with different decimal places for example), we could need an extra
                # exchange difference journal entry to handle them.
                exchange_lines_to_fix = self.env['account.move.line']
                amounts_list = []
                exchange_max_date = date.min
                for line in involved_lines:
                    if not line.company_currency_id.is_zero(line.amount_residual):
                        exchange_lines_to_fix += line
                        amounts_list.append({'amount_residual': line.amount_residual})
                    elif not line.currency_id.is_zero(line.amount_residual_currency):
                        exchange_lines_to_fix += line
                        amounts_list.append({'amount_residual_currency': line.amount_residual_currency})
                    exchange_max_date = max(exchange_max_date, line.date)
                exchange_diff_vals = exchange_lines_to_fix._prepare_exchange_difference_move_vals(
                    amounts_list,
                    company=involved_lines[0].company_id,
                    exchange_date=exchange_max_date,
                )

                # Exchange difference for cash basis entries.
                if is_cash_basis_needed:
                    caba_lines_to_reconcile = involved_lines._add_exchange_difference_cash_basis_vals(exchange_diff_vals)

                # Create the exchange difference.
                if exchange_diff_vals['move_vals']['line_ids']:
                    exchange_move = involved_lines._create_exchange_difference_move(exchange_diff_vals)
                    if exchange_move:
                        exchange_move_lines = exchange_move.line_ids.filtered(lambda line: line.account_id == account)

                        # Track newly created lines.
                        involved_lines += exchange_move_lines

                        # Track newly created partials.
                        exchange_diff_partials = exchange_move_lines.matched_debit_ids \
                                                 + exchange_move_lines.matched_credit_ids
                        involved_partials += exchange_diff_partials
                        results['exchange_partials'] += exchange_diff_partials

            # ==== Create the full reconcile ====
            results['full_reconcile'] = self.env['account.full.reconcile'] \
                .with_context(
                    skip_invoice_sync=True,
                    skip_invoice_line_sync=True,
                    skip_account_move_synchronization=True,
                    check_move_validity=False,
                ) \
                .create({
                    'exchange_move_id': exchange_move and exchange_move.id,
                    'partial_reconcile_ids': [Command.set(involved_partials.ids)],
                    'reconciled_line_ids': [Command.set(involved_lines.ids)],
                })

            # === Cash basis rounding autoreconciliation ===
            # In case a cash basis rounding difference line got created for the transition account, we reconcile it with the corresponding lines
            # on the cash basis moves (so that it reaches full reconciliation and creates an exchange difference entry for this account as well)

            if caba_lines_to_reconcile:
                for (dummy, account, repartition_line), amls_to_reconcile in caba_lines_to_reconcile.items():
                    if not account.reconcile:
                        continue

                    exchange_line = exchange_move.line_ids.filtered(
                        lambda l: l.account_id == account and l.tax_repartition_line_id == repartition_line
                    )

                    (exchange_line + amls_to_reconcile).filtered(lambda l: not l.reconciled).reconcile()

        not_paid_invoices.filtered(lambda move:
            move.payment_state in ('paid', 'in_payment')
        )._invoice_paid_hook()
        for parcial in results['partials']:
            amount_usd = min(abs(parcial.debit_move_id.amount_residual_usd),
                             abs(parcial.credit_move_id.amount_residual_usd))
            parcial.write({'amount_usd': abs(amount_usd)})
            self.env.cr.commit()
        return results

    @api.model
    def _prepare_reconciliation_single_partial(self, debit_vals, credit_vals):
        """ Prepare the values to create an account.partial.reconcile later when reconciling the dictionaries passed
        as parameters, each one representing an account.move.line.
        :param debit_vals:  The values of account.move.line to consider for a debit line.
        :param credit_vals: The values of account.move.line to consider for a credit line.
        :return:            A dictionary:
            * debit_vals:   None if the line has nothing left to reconcile.
            * credit_vals:  None if the line has nothing left to reconcile.
            * partial_vals: The newly computed values for the partial.
        """

        def get_odoo_rate(vals):
            # if vals.get('record') and vals['record'].move_id.is_invoice(include_receipts=True):
            #     exchange_rate_date = vals['record'].move_id.invoice_date
            # else:
            #     exchange_rate_date = vals['date']
            # return recon_currency._get_conversion_rate(company_currency, recon_currency, vals['company'],
            #                                            exchange_rate_date)
            if vals.get('record') and vals['record'].move_id.is_invoice(include_receipts=True):
                exchange_rate_date = vals['record'].move_id.invoice_date
            else:
                exchange_rate_date = vals['date']
            to_re = recon_currency._get_conversion_rate(company_currency, recon_currency, vals['company'],
                                                        exchange_rate_date)
            return  1 / vals['record'].move_id.tax_today if vals['record'].move_id.tax_today > 0 else 1
            if debit_vals['record'].move_id.is_invoice(include_receipts=True):
                return (1 / credit_vals['record'].move_id.tax_today if credit_vals['record'].move_id.tax_today > 0 else 1)
            elif credit_vals['record'].move_id.is_invoice(include_receipts=True):
                return 1 / debit_vals['record'].move_id.tax_today if debit_vals['record'].move_id.tax_today > 0 else 1
            else:
                return to_re


        def get_accounting_rate(vals):
            if company_currency.is_zero(vals['balance']) or vals['currency'].is_zero(vals['amount_currency']):
                return None
            else:
                return abs(vals['amount_currency']) / abs(vals['balance'])

        # ==== Determine the currency in which the reconciliation will be done ====
        # In this part, we retrieve the residual amounts, check if they are zero or not and determine in which
        # currency and at which rate the reconciliation will be done.

        res = {
            'debit_vals': debit_vals,
            'credit_vals': credit_vals,
        }
        remaining_debit_amount_curr = debit_vals['amount_residual_currency']
        remaining_credit_amount_curr = credit_vals['amount_residual_currency']
        remaining_debit_amount = debit_vals['amount_residual']
        remaining_credit_amount = credit_vals['amount_residual']

        company_currency = debit_vals['company'].currency_id
        has_debit_zero_residual = company_currency.is_zero(remaining_debit_amount)
        has_credit_zero_residual = company_currency.is_zero(remaining_credit_amount)
        has_debit_zero_residual_currency = debit_vals['currency'].is_zero(remaining_debit_amount_curr)
        has_credit_zero_residual_currency = credit_vals['currency'].is_zero(remaining_credit_amount_curr)
        is_rec_pay_account = debit_vals.get('record') \
                             and debit_vals['record'].account_type in ('asset_receivable', 'liability_payable')

        if debit_vals['currency'] == credit_vals['currency'] == company_currency \
                and not has_debit_zero_residual \
                and not has_credit_zero_residual:
            # Everything is expressed in company's currency and there is something left to reconcile.
            recon_currency = company_currency
            debit_rate = credit_rate = 1.0
            recon_debit_amount = remaining_debit_amount
            recon_credit_amount = -remaining_credit_amount
        elif debit_vals['currency'] == company_currency \
                and is_rec_pay_account \
                and not has_debit_zero_residual \
                and credit_vals['currency'] != company_currency \
                and not has_credit_zero_residual_currency:
            # The credit line is using a foreign currency but not the opposite line.
            # In that case, convert the amount in company currency to the foreign currency one.
            recon_currency = credit_vals['currency']
            debit_rate = get_odoo_rate(debit_vals)
            credit_rate = get_accounting_rate(credit_vals)
            recon_debit_amount = recon_currency.round(remaining_debit_amount * debit_rate)
            recon_credit_amount = -remaining_credit_amount_curr
        elif debit_vals['currency'] != company_currency \
                and is_rec_pay_account \
                and not has_debit_zero_residual_currency \
                and credit_vals['currency'] == company_currency \
                and not has_credit_zero_residual:
            # The debit line is using a foreign currency but not the opposite line.
            # In that case, convert the amount in company currency to the foreign currency one.
            recon_currency = debit_vals['currency']
            debit_rate = get_accounting_rate(debit_vals)
            credit_rate = get_odoo_rate(credit_vals)
            recon_debit_amount = remaining_debit_amount_curr
            recon_credit_amount = recon_currency.round(-remaining_credit_amount * credit_rate)
        elif debit_vals['currency'] == credit_vals['currency'] \
                and debit_vals['currency'] != company_currency \
                and not has_debit_zero_residual_currency \
                and not has_credit_zero_residual_currency:
            # Both lines are sharing the same foreign currency.
            recon_currency = debit_vals['currency']
            debit_rate = get_accounting_rate(debit_vals)
            credit_rate = get_accounting_rate(credit_vals)
            recon_debit_amount = remaining_debit_amount_curr
            recon_credit_amount = -remaining_credit_amount_curr
        elif debit_vals['currency'] == credit_vals['currency'] \
                and debit_vals['currency'] != company_currency \
                and (has_debit_zero_residual_currency or has_credit_zero_residual_currency):
            # Special case for exchange difference lines. In that case, both lines are sharing the same foreign
            # currency but at least one has no amount in foreign currency.
            # In that case, we don't want a rate for the opposite line because the exchange difference is supposed
            # to reduce only the amount in company currency but not the foreign one.
            recon_currency = company_currency
            debit_rate = None
            credit_rate = None
            recon_debit_amount = remaining_debit_amount
            recon_credit_amount = -remaining_credit_amount
        else:
            # Multiple involved foreign currencies. The reconciliation is done using the currency of the company.
            recon_currency = company_currency
            debit_rate = get_accounting_rate(debit_vals)
            credit_rate = get_accounting_rate(credit_vals)
            recon_debit_amount = remaining_debit_amount
            recon_credit_amount = -remaining_credit_amount

        # Check if there is something left to reconcile. Move to the next loop iteration if not.
        skip_reconciliation = False
        if recon_currency.is_zero(recon_debit_amount):
            res['debit_vals'] = None
            skip_reconciliation = True
        if recon_currency.is_zero(recon_credit_amount):
            res['credit_vals'] = None
            skip_reconciliation = True
        if skip_reconciliation:
            return res

        # ==== Match both lines together and compute amounts to reconcile ====

        # Determine which line is fully matched by the other.
        compare_amounts = recon_currency.compare_amounts(recon_debit_amount, recon_credit_amount)
        min_recon_amount = min(recon_debit_amount, recon_credit_amount)
        debit_fully_matched = compare_amounts <= 0
        credit_fully_matched = compare_amounts >= 0

        # ==== Computation of partial amounts ====
        if recon_currency == company_currency:
            # Compute the partial amount expressed in company currency.
            partial_amount = min_recon_amount

            # Compute the partial amount expressed in foreign currency.
            if debit_rate:
                partial_debit_amount_currency = debit_vals['currency'].round(debit_rate * min_recon_amount)
                partial_debit_amount_currency = min(partial_debit_amount_currency, remaining_debit_amount_curr)
            else:
                partial_debit_amount_currency = 0.0
            if credit_rate:
                partial_credit_amount_currency = credit_vals['currency'].round(credit_rate * min_recon_amount)
                partial_credit_amount_currency = min(partial_credit_amount_currency, -remaining_credit_amount_curr)
            else:
                partial_credit_amount_currency = 0.0

        else:
            # recon_currency != company_currency
            # Compute the partial amount expressed in company currency.
            if debit_rate:
                partial_debit_amount = company_currency.round(min_recon_amount / debit_rate)
                partial_debit_amount = min(partial_debit_amount, remaining_debit_amount)
            else:
                partial_debit_amount = 0.0
            if credit_rate:
                partial_credit_amount = company_currency.round(min_recon_amount / credit_rate)
                partial_credit_amount = min(partial_credit_amount, -remaining_credit_amount)
            else:
                partial_credit_amount = 0.0
            partial_amount = min(partial_debit_amount, partial_credit_amount)

            # Compute the partial amount expressed in foreign currency.
            # Take care to handle the case when a line expressed in company currency is mimicking the foreign
            # currency of the opposite line.
            if debit_vals['currency'] == company_currency:
                partial_debit_amount_currency = partial_amount
            else:
                partial_debit_amount_currency = min_recon_amount
            if credit_vals['currency'] == company_currency:
                partial_credit_amount_currency = partial_amount
            else:
                partial_credit_amount_currency = min_recon_amount

        # Computation of the partial exchange difference. You can skip this part using the
        # `no_exchange_difference` context key (when reconciling an exchange difference for example).
        if not self._context.get('no_exchange_difference'):
            exchange_lines_to_fix = self.env['account.move.line']
            amounts_list = []
            if recon_currency == company_currency:
                if debit_fully_matched:
                    debit_exchange_amount = remaining_debit_amount_curr - partial_debit_amount_currency
                    if not debit_vals['currency'].is_zero(debit_exchange_amount):
                        if debit_vals.get('record'):
                            exchange_lines_to_fix += debit_vals['record']
                        amounts_list.append({'amount_residual_currency': debit_exchange_amount})
                        remaining_debit_amount_curr -= debit_exchange_amount
                if credit_fully_matched:
                    credit_exchange_amount = remaining_credit_amount_curr + partial_credit_amount_currency
                    if not credit_vals['currency'].is_zero(credit_exchange_amount):
                        if credit_vals.get('record'):
                            exchange_lines_to_fix += credit_vals['record']
                        amounts_list.append({'amount_residual_currency': credit_exchange_amount})
                        remaining_credit_amount_curr += credit_exchange_amount

            else:
                if debit_fully_matched:
                    # Create an exchange difference on the remaining amount expressed in company's currency.
                    debit_exchange_amount = remaining_debit_amount - partial_amount
                    if not company_currency.is_zero(debit_exchange_amount):
                        if debit_vals.get('record'):
                            exchange_lines_to_fix += debit_vals['record']
                        amounts_list.append({'amount_residual': debit_exchange_amount})
                        remaining_debit_amount -= debit_exchange_amount
                        if debit_vals['currency'] == company_currency:
                            remaining_debit_amount_curr -= debit_exchange_amount
                else:
                    # Create an exchange difference ensuring the rate between the residual amounts expressed in
                    # both foreign and company's currency is still consistent regarding the rate between
                    # 'amount_currency' & 'balance'.
                    debit_exchange_amount = partial_debit_amount - partial_amount
                    if company_currency.compare_amounts(debit_exchange_amount, 0.0) > 0:
                        if debit_vals.get('record'):
                            exchange_lines_to_fix += debit_vals['record']
                        amounts_list.append({'amount_residual': debit_exchange_amount})
                        remaining_debit_amount -= debit_exchange_amount
                        if debit_vals['currency'] == company_currency:
                            remaining_debit_amount_curr -= debit_exchange_amount

                if credit_fully_matched:
                    # Create an exchange difference on the remaining amount expressed in company's currency.
                    credit_exchange_amount = remaining_credit_amount + partial_amount
                    if not company_currency.is_zero(credit_exchange_amount):
                        if credit_vals.get('record'):
                            exchange_lines_to_fix += credit_vals['record']
                        amounts_list.append({'amount_residual': credit_exchange_amount})
                        remaining_credit_amount += credit_exchange_amount
                        if credit_vals['currency'] == company_currency:
                            remaining_credit_amount_curr -= credit_exchange_amount
                else:
                    # Create an exchange difference ensuring the rate between the residual amounts expressed in
                    # both foreign and company's currency is still consistent regarding the rate between
                    # 'amount_currency' & 'balance'.
                    credit_exchange_amount = partial_amount - partial_credit_amount
                    if company_currency.compare_amounts(credit_exchange_amount, 0.0) < 0:
                        if credit_vals.get('record'):
                            exchange_lines_to_fix += credit_vals['record']
                        amounts_list.append({'amount_residual': credit_exchange_amount})
                        remaining_credit_amount -= credit_exchange_amount
                        if credit_vals['currency'] == company_currency:
                            remaining_credit_amount_curr -= credit_exchange_amount

            if exchange_lines_to_fix:
                res['exchange_vals'] = exchange_lines_to_fix._prepare_exchange_difference_move_vals(
                    amounts_list,
                    exchange_date=max(debit_vals['date'], credit_vals['date']),
                )

        # ==== Create partials ====

        remaining_debit_amount -= partial_amount
        remaining_credit_amount += partial_amount
        remaining_debit_amount_curr -= partial_debit_amount_currency
        remaining_credit_amount_curr += partial_credit_amount_currency

        res['partial_vals'] = {
            'amount': partial_amount,
            'debit_amount_currency': partial_debit_amount_currency,
            'credit_amount_currency': partial_credit_amount_currency,
            'debit_move_id': debit_vals.get('record') and debit_vals['record'].id,
            'credit_move_id': credit_vals.get('record') and credit_vals['record'].id,
        }

        debit_vals['amount_residual'] = remaining_debit_amount
        debit_vals['amount_residual_currency'] = remaining_debit_amount_curr
        credit_vals['amount_residual'] = remaining_credit_amount
        credit_vals['amount_residual_currency'] = remaining_credit_amount_curr

        if debit_fully_matched:
            res['debit_vals'] = None
        if credit_fully_matched:
            res['credit_vals'] = None
        return res

    @api.depends('amount_residual_usd')
    def _compute_reconciled_usd(self):
        for line in self:
            # Considera redondeos, si es cero es conciliado en dualidad
            line.reconciled = abs(line.amount_residual_usd) < (line.currency_id_dif.rounding if line.currency_id_dif else 0.01)
