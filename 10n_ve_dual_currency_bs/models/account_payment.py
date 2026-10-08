# -*- coding: utf-8 -*-
###############################################################################
# Author: Jesus Pozzo / Andres Castillo
# Copyleft: 2023-Present.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).
#
# Migrado a Odoo v19:
# - Eliminado import de osv (no existe en v19)
# - Eliminado import de Warning (usar UserError)
# - tax_day cambiado de Monetary a Float (Monetary con currency_field
#   puede causar ciclos de dependencia en la vista)
###############################################################################
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
import logging
import requests
from decimal import Decimal, ROUND_DOWN

_logger = logging.getLogger(__name__)


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    currency_ref_id = fields.Many2one(
        'res.currency',
        string='Moneda Bs.',
        default=lambda self: self.env.ref('base.VEF')
    )

    @api.model
    def getRate(self):
        res_currency_id = self.env['res.currency'].sudo().search(
            [('name', '=', 'VEF'), ('active', '=', True)], limit=1
        )
        if res_currency_id and res_currency_id.rate_ids:
            rate_day = res_currency_id.rate_ids.sorted('name', reverse=True)[:1]
            tx = Decimal(str(rate_day.company_rate))
            tx_amount = tx.quantize(Decimal('1.00'), rounding=ROUND_DOWN)
            return float(tx_amount)
        else:
            return 3.00

    # Cambiado de Monetary a Float para evitar ciclos con currency_field
    tax_day = fields.Float(
        string='Tasa del día',
        digits=(16, 3),
        default=getRate,
    )

    amount_total_bs = fields.Monetary(
        string="Importe en BS.",
        store=True,
        compute='_compute_amounts_bs',
        currency_field='currency_ref_id',
        tracking=4
    )

    rel_code_currency_id = fields.Char(
        related='currency_id.name',
        string='Codigo moneda'
    )

    @api.depends('tax_day', 'amount')
    def _compute_amounts_bs(self):
        for payment in self:
            if payment.tax_day > 0:
                if payment.rel_code_currency_id == 'USD':
                    payment.amount_total_bs = round(
                        round(payment.amount, 3) * round(payment.tax_day, 3), 3
                    )
                elif payment.rel_code_currency_id == 'VEF':
                    payment.amount_total_bs = round(
                        round(payment.amount, 3) / round(payment.tax_day, 3), 3
                    )
                else:
                    payment.amount_total_bs = payment.amount
            else:
                payment.amount_total_bs = 0.000
