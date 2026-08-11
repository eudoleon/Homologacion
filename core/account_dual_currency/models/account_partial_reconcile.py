# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from datetime import date
import logging

_logger = logging.getLogger(__name__)


class AccountPartialReconcile(models.Model):
    _inherit = "account.partial.reconcile"

    company_currency_id_dif = fields.Many2one(
        comodel_name='res.currency',
        string="Company Currency",
        related='company_id.currency_id_dif')

    # ==== Amount fields ====
    amount_usd = fields.Monetary(
        currency_field='company_currency_id_dif',
    )

    @api.model_create_multi
    def create(self, vals_list):
        res = super(AccountPartialReconcile, self).create(vals_list)
        for parcial in res:
            amount_usd = min(abs(parcial.debit_move_id.amount_residual_usd),
                             abs(parcial.credit_move_id.amount_residual_usd))
            parcial.amount_usd = abs(amount_usd)

            # --- Sincronización de tasa: Extracto Bancario ← Pago ---
            # Portado desde account_dual_currency_V18:
            # Al conciliar un extracto bancario con un pago, el extracto
            # adopta la tasa de cambio (tax_today) del pago para que los
            # montos en dual currency queden consistentes.
            try:
                move_1 = parcial.debit_move_id.move_id
                move_2 = parcial.credit_move_id.move_id

                st_move = False
                py_move = False

                if hasattr(move_1, 'statement_line_id') and move_1.statement_line_id:
                    st_move = move_1
                    py_move = move_2
                elif hasattr(move_2, 'statement_line_id') and move_2.statement_line_id:
                    st_move = move_2
                    py_move = move_1

                if st_move and py_move and py_move.tax_today > 0:
                    tasa_pago = py_move.tax_today
                    if st_move.tax_today != tasa_pago:
                        _logger.info(
                            "[RECON-RATE] Sincronizando tasa: extracto move=%s (tasa=%s) → tasa pago=%s (move=%s)",
                            st_move.id, st_move.tax_today, tasa_pago, py_move.id
                        )
                        st_move.with_context(check_move_validity=False).write({'tax_today': tasa_pago})
                        if hasattr(st_move, 'statement_line_id') and st_move.statement_line_id:
                            st_move.statement_line_id.with_context(check_move_validity=False).write({
                                'tasa_referencia_statement': tasa_pago
                            })
                        st_move._onchange_tax_today()
            except Exception as e:
                _logger.warning("[RECON-RATE] Error sincronizando tasa en conciliación parcial %s: %s", parcial.id, e)

        return res

    def unlink(self):
        # Identificar las facturas involucradas antes de desconciliar
        moves = self.mapped('debit_move_id.move_id') | self.mapped('credit_move_id.move_id')
        
        res = super(AccountPartialReconcile, self).unlink()
        
        # Forzar la actualización del estado de pago y saldo
        if moves:
            if hasattr(moves, 'invalidate_recordset'):
                moves.invalidate_recordset([
                    'payment_state', 
                    'amount_residual',
                    'invoice_payments_widget_usd',
                    'invoice_payments_widget_bs',
                    'invoice_outstanding_credits_debits_widget'
                ])
                moves.mapped('line_ids').invalidate_recordset(['amount_residual', 'amount_residual_currency', 'amount_residual_usd'])
            moves._compute_amount()
            if hasattr(moves, '_compute_payment_state'):
                moves._compute_payment_state()
            if hasattr(moves, '_compute_payments_widget_reconciled_info_USD'):
                moves._compute_payments_widget_reconciled_info_USD()
            if hasattr(moves, '_compute_payments_widget_reconciled_info_bs'):
                moves._compute_payments_widget_reconciled_info_bs()
                
        return res

