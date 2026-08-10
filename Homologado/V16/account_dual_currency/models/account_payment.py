# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
import logging
_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = 'account.payment'

    tax_today = fields.Float(string="Tasa", default=lambda self: self._get_default_tasa(), digits='Dual_Currency_rate')
    currency_id_dif = fields.Many2one("res.currency",
                                      string="Divisa de Referencia",
                                      default=lambda self: self.env.company.currency_id_dif )
    currency_id_company = fields.Many2one("res.currency",
                                      string="Divisa compañia",
                                      default=lambda self: self.env.company.currency_id )
    amount_local = fields.Monetary(string="Importe local", currency_field='currency_id_company')
    amount_ref = fields.Monetary(string="Importe referencia", currency_field='currency_id_dif' )
    currency_equal = fields.Boolean(compute="_currency_equal")
    move_id_dif = fields.Many2one(
        'account.move', 'Asiento contable diferencia',  # required=True,
        readonly=True,
        help="Asiento contable de diferencia en tipo de cambio")

    currency_id_name = fields.Char(related="currency_id.name")
    journal_igtf_id = fields.Many2one('account.journal', string='Diario IGTF', check_company=True)
    aplicar_igtf_divisa = fields.Boolean(string="Aplicar IGTF")
    igtf_divisa_porcentage = fields.Float('% IGTF', related='company_id.igtf_divisa_porcentage')

    mount_igtf = fields.Monetary(currency_field='currency_id', string='Importe IGTF', readonly=True,
                                 digits='Dual_Currency')

    amount_total_pagar = fields.Monetary(currency_field='currency_id', string="Total Pagar(Importe + IGTF):",
                                         readonly=True)

    move_id_igtf_divisa = fields.Many2one(
        'account.move', 'Asiento IGTF Divisa',
        readonly=True)

    def _get_default_tasa(self):
        return self.env.company.currency_id_dif.inverse_rate

    @api.onchange("date")
    def onchange_date_change_tax_today(self):
        currency_USD = self.env['res.currency'].search([('name', '=', 'USD')], limit=1)
        company_currency = self.env.company.currency_id
        self.tax_today = company_currency._get_conversion_rate(currency_USD, company_currency, self.env.company, self.date)


    @api.depends('currency_id_dif','currency_id','amount','tax_today')
    def _currency_equal(self):
        for rec in self:
            currency_equal = rec.currency_id_company != rec.currency_id
            if currency_equal:
                rec.amount_local = rec.amount * rec.tax_today
                rec.amount_ref = rec.amount
            else:
                rec.amount_local = rec.amount
                rec.amount_ref = (rec.amount / rec.tax_today) if rec.amount > 0 and rec.tax_today > 0 else 0
            rec.currency_equal = currency_equal

            if rec.aplicar_igtf_divisa:
                if rec.currency_id.name == 'USD':
                    rec.mount_igtf = rec.amount * rec.igtf_divisa_porcentage / 100
                    rec.amount_total_pagar = rec.mount_igtf + rec.amount
                else:
                    rec.mount_igtf = 0
                    rec.amount_total_pagar = rec.amount
            else:
                rec.mount_igtf = 0
                rec.amount_total_pagar = rec.amount

    def action_draft(self):
        ''' posted -> draft '''
        res = super().action_draft()
        self.move_id_dif.button_draft()
        if self.move_id_igtf_divisa:
            if self.move_id_igtf_divisa.state == 'done':
                self.move_id_igtf_divisa.button_draft()


    def action_cancel(self):
        ''' draft -> cancelled '''
        res = super().action_cancel()
        self.move_id_dif.button_cancel()
        if self.move_id_igtf_divisa:
            self.move_id_igtf_divisa.button_cancel()

    def action_post(self):
        res = super().action_post()
        ''' draft -> posted '''
        self.move_id_dif._post(soft=False)
        """Genera la retencion IGTF """
        for pago in self:
            if not pago.move_id_igtf_divisa:
                if pago.aplicar_igtf_divisa:
                    pago.register_move_igtf_divisa_payment()
            else:
                if pago.move_id_igtf_divisa.state == 'draft':
                    pago.move_id_igtf_divisa.action_post()

    def _auto_reconcile_payment_dif(self):
        """
        Conciliar (parcialmente si aplica) las líneas AR/AP del pago con las del
        asiento de diferencia cambiaria. No exigimos suma = 0; dejamos que Odoo
        cree un partial sobre el menor monto (la línea del DIF).
        """
        for payment in self:
            move_pay = getattr(payment, 'move_id', False)
            move_dif = getattr(payment, 'move_id_dif', False)
            if not move_pay or not move_dif:
                continue

            pay_lines = move_pay.line_ids.filtered(
                lambda l: l.account_id.account_type in ('asset_receivable', 'liability_payable')
                and l.partner_id == payment.partner_id
                and not l.reconciled
            )
            dif_lines = move_dif.line_ids.filtered(
                lambda l: l.account_id.account_type in ('asset_receivable', 'liability_payable')
                and l.partner_id == payment.partner_id
                and not l.reconciled
            )

            # Conciliar por cuenta (parcial si corresponde)
            for account in (pay_lines.account_id | dif_lines.account_id):
                p_acc = pay_lines.filtered(lambda l: l.account_id == account and not l.reconciled)
                d_acc = dif_lines.filtered(lambda l: l.account_id == account and not l.reconciled)

                if p_acc and d_acc:
                    # Tomamos una línea de pago y una de DIF y conciliamos.
                    # Si los importes no cuadran a 0, Odoo crea un partial reconcile
                    # por el menor (normalmente el DIF), dejando residual en el pago.
                    group = (p_acc[:1] + d_acc[:1]).filtered(lambda l: not l.reconciled)
                    try:
                        group.reconcile()
                        _logger.info(
                            "[AUTO-RECON] Conciliación (posible PARCIAL) Pago %s ↔ DIF en cuenta %s: líneas %s",
                            payment.id, account.code, list(group.mapped('id'))
                        )
                    except Exception as e:
                        _logger.exception("[AUTO-RECON] Error conciliando Pago %s con DIF: %s", payment.id, e)

            # Recompute de seguridad
            try:
                (move_pay | move_dif).mapped('line_ids')._compute_amount_residual()
            except Exception:
                pass
                        
    def register_move_igtf_divisa_payment(self):
        '''Este método realiza el asiento contable de la comisión según el porcentaje que indica la compañia'''
        diario = self.journal_igtf_id or self.journal_id
        vals = {
            'date': self.date,
            'journal_id': diario.id,
            'currency_id': self.currency_id.id,
            'state': 'draft',
            'tax_today': self.tax_today,
            'ref': self.ref,
            'move_type': 'entry',
            'line_ids': []  # Iniciar con una lista vacía en lugar de False
        }

        move_id = self.env['account.move'].with_context(check_move_validity=False).create(vals)

        # Preparar las líneas contables
        line_ids = [
            (0, 0, {
                'account_id': diario.company_id.account_journal_payment_debit_account_id.id 
                            if self.payment_type == 'inbound' 
                            else diario.company_id.account_journal_payment_credit_account_id.id,
                'company_id': self.company_id.id,
                'currency_id': self.currency_id.id,
                'date_maturity': False,
                'ref': "Comisión IGTF Divisa",
                'date': self.date,
                'partner_id': self.partner_id.id,
                'name': "Comisión IGTF Divisa",
                'journal_id': self.journal_id.id,
                'credit': float(self.mount_igtf * self.tax_today) 
                        if not self.payment_type == 'inbound' 
                        else float(0.0),
                'debit': float(self.mount_igtf * self.tax_today) 
                        if self.payment_type == 'inbound' 
                        else float(0.0),
                'amount_currency': -self.mount_igtf 
                                if not self.payment_type == 'inbound' 
                                else self.mount_igtf,
            }),
            (0, 0, {
                'account_id': self.company_id.account_debit_wh_igtf_id.id 
                            if self.payment_type == 'inbound' 
                            else self.company_id.account_credit_wh_igtf_id.id,
                'company_id': self.company_id.id,
                'currency_id': self.currency_id.id,
                'date_maturity': False,
                'ref': "Comisión IGTF Divisa",
                'date': self.date,
                'name': "Comisión IGTF Divisa",
                'journal_id': self.journal_id.id,
                'credit': float(self.mount_igtf * self.tax_today) 
                        if self.payment_type == 'inbound' 
                        else float(0.0),
                'debit': float(self.mount_igtf * self.tax_today) 
                        if not self.payment_type == 'inbound' 
                        else float(0.0),
                'amount_currency': -self.mount_igtf 
                                if self.payment_type == 'inbound' 
                                else self.mount_igtf,
            }),
        ]

        # Usar el método `write` para añadir líneas al asiento
        move_id.write({'line_ids': line_ids})

        if move_id:
            res = {'move_id_igtf_divisa': move_id.id}
            self.write(res)
            move_id.action_post()
        return True
