# -*- coding: utf-8 -*-
###############################################################################
# Author: Jesus Pozzo / Andres Castillo
# Copyleft: 2023-Present.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).
#
# Migrado a Odoo v19:
# - Eliminado import de osv (no existe en v19)
# - Corregido: internal_type fue eliminado en v16+; usar account_type
# - Corregido: rel_code_currency_id no estaba definido en este modelo; se agregó
# - Corregido: _create_payments() ahora retorna el resultado del super()
###############################################################################
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class InhAccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    currency_ref_id = fields.Many2one(
        'res.currency',
        string='Moneda Bs.',
        default=lambda self: self.env.ref('base.USD')
    )

    tax_day = fields.Float(
        string='Tasa del día',
        default=36,
        digits='Product Price',
    )

    amount_total_bs = fields.Monetary(
        string="DOLARES",
        store=True,
        compute='_compute_amounts_bs',
        currency_field='currency_ref_id',
        tracking=4
    )

    # Campo relacionado necesario para usar en _compute_amounts_bs
    rel_code_currency_id = fields.Char(
        related='currency_id.name',
        string='Codigo moneda',
        readonly=True
    )

    def _create_payments(self):
        """
        Override para propagar la tasa del día al pago creado.
        En v19, _create_payments() devuelve un recordset account.payment.
        """
        res = super(InhAccountPaymentRegister, self)._create_payments()

        for payment in res:
            payment.tax_day = self.tax_day

            # Buscar líneas de cuentas por cobrar usando account_type (v16+)
            # account_type reemplaza a internal_type (eliminado en v16)
            l_cliente = payment.line_ids.filtered(
                lambda line: line.account_id.account_type == 'asset_receivable'
            )
            if l_cliente:
                monto_diferencia = sum(
                    line.debit if line.debit > 0 else line.credit
                    for line in l_cliente
                )
                _logger.info("Monto diferencia cliente: %s", monto_diferencia)

        return res

    @api.depends('tax_day', 'amount')
    def _compute_amounts_bs(self):
        for payment in self:
            if payment.tax_day > 0 and payment.rel_code_currency_id == 'USD':
                payment.amount_total_bs = round(payment.amount / payment.tax_day, 3)
            else:
                payment.amount_total_bs = 0.000
