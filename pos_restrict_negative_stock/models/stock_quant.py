# -*- coding: utf-8 -*-

from odoo import models, api

class StockQuant(models.Model):
    _inherit = 'stock.quant'

    @api.model
    def get_product_stock(self, location, other_locations, product):
        def _loc_id(loc):
            if not loc:
                return False
            if isinstance(loc, (list, tuple)) and len(loc) > 0:
                return int(loc[0])
            if isinstance(loc, dict) and 'id' in loc:
                return int(loc['id'])
            try:
                return int(loc)
            except Exception:
                return False

        loc_id = _loc_id(location)
        domain = [('product_id', '=', int(product))]
        if loc_id:
            domain.append(('location_id', '=', loc_id))
        else:
            domain.append(('location_id.usage', '=', 'internal'))

        quants1 = self.sudo().search(domain)
        qty = sum(quants1.mapped('quantity'))

        res = []
        if other_locations and isinstance(other_locations, (list, tuple)):
            for locs in other_locations:
                other_loc_id = _loc_id(locs)
                if other_loc_id:
                    quants2 = self.sudo().search([('product_id', '=', int(product)), ('location_id', '=', int(other_loc_id))])
                    qty1 = sum(quants2.mapped('quantity'))
                    res.append({'quantity': qty1, 'location': {'id': int(other_loc_id)}, 'product': product})
                
        return [qty, res]
