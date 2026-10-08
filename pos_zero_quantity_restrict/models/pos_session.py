# -*- coding: utf-8 -*-

from odoo import models, api

class PosSession(models.Model):
    _inherit = 'pos.session'

    def _loader_params_product_product(self):
        result = super()._loader_params_product_product()
        result['search_params']['fields'].extend(['standard_price', 'standard_price_usd'])
        return result

    @api.model
    def get_product_cost(self, product_id):
        product = self.env['product.product'].sudo().browse(product_id)
        standard_price_usd = getattr(product, 'standard_price_usd', 0.0)
        return {
            'standard_price': product.standard_price,
            'standard_price_usd': standard_price_usd
        }
