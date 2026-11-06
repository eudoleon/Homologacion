# -*- coding: utf-8 -*-
from odoo import fields, models, tools, api, _
from collections import defaultdict
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_is_zero


class AdjustmentLines(models.Model):
    _inherit = 'stock.valuation.adjustment.lines'

    former_cost_usd = fields.Monetary(currency_field='currency_id_dif', string='Valor Original $')
    tax_today = fields.Float(string="Tasa", store=True)
    currency_id_dif = fields.Many2one(related="cost_id.company_id.currency_id_dif")
    additional_landed_cost_usd = fields.Monetary(currency_field='currency_id_dif',string='Costo adicionales $')
    final_cost_usd = fields.Monetary(currency_field='currency_id_dif', string=
    'Nevo Valor $', compute='_compute_final_cost_usd',
                                     store=True)

    @api.depends('former_cost_usd', 'additional_landed_cost_usd')
    def _compute_final_cost_usd(self):
        for line in self:
            line.final_cost_usd = line.former_cost_usd + line.additional_landed_cost_usd
