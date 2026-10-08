# -*- coding: utf-8 -*-

from odoo import models, fields, api
import json

class ProductProduct(models.Model):
    _inherit = 'product.product'

    quant_ids = fields.One2many("stock.quant", "product_id", string="Quants",
        domain=[('location_id.usage', '=', 'internal')])
    quant_text = fields.Text('Quant Qty', compute='_compute_avail_locations', store=False)

    @api.depends('quant_ids', 'quant_ids.location_id', 'quant_ids.quantity')
    def _compute_avail_locations(self):
        for rec in self:
            rec.quant_text = ''
            all_data = {}
            for quant in rec.quant_ids:
                loc = quant.location_id.id
                if loc in all_data:
                    all_data[loc] += quant.quantity
                else:
                    all_data[loc] = quant.quantity
            rec.quant_text = json.dumps(all_data)
