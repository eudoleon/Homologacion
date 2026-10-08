# -*- coding: utf-8 -*-

from odoo import models, api
import logging

_logger = logging.getLogger(__name__)

class PosSession(models.Model):
    _inherit = 'pos.session'

    def _loader_params_product_product(self):
        result = super()._loader_params_product_product()
        fields = result.get('search_params', {}).get('fields', [])
        for f in ['qty_available', 'type', 'is_storable', 'detailed_type']:
            if f not in fields:
                fields.append(f)
        result['search_params']['fields'] = fields
        return result

    def _pos_data_process(self, loaded_data):
        super()._pos_data_process(loaded_data)
        stock_map = {}
        try:
            config = self.config_id
            stock_location_id = False
            if config and config.picking_type_id and config.picking_type_id.default_location_src_id:
                stock_location_id = config.picking_type_id.default_location_src_id.id
            
            prods = loaded_data.get('product.product', [])
            # Incluir únicamente productos con rastreo de inventario activo (is_storable = True)
            storable_ids = []
            for p in prods:
                ptype = (p.get('type') or p.get('detailed_type') or '').lower()
                if ptype in ('service', 'combo'):
                    continue
                if 'is_storable' in p and p.get('is_storable') is not None:
                    if p.get('is_storable'):
                        storable_ids.append(p['id'])
                elif ptype == 'product':
                    storable_ids.append(p['id'])
            
            if storable_ids:
                domain = [('product_id', 'in', storable_ids)]
                if stock_location_id:
                    domain.append(('location_id', '=', stock_location_id))
                else:
                    domain.append(('location_id.usage', '=', 'internal'))
                    
                quants = self.env['stock.quant'].sudo().search(domain)
                for q in quants:
                    pid = q.product_id.id
                    stock_map[pid] = stock_map.get(pid, 0.0) + (q.quantity or 0.0)
                        
            for prod in prods:
                pid = prod['id']
                if pid in stock_map:
                    prod['qty_available'] = stock_map[pid]
                elif 'qty_available' not in prod:
                    prod['qty_available'] = 0.0

        except Exception as e:
            _logger.error("Error al calcular pos_product_stock_map en pos_session.py: %s", str(e))
            
        loaded_data['pos_product_stock_map'] = stock_map

    @api.model
    def get_realtime_product_stock(self, product_id, config_id=None):
        try:
            product = self.env['product.product'].sudo().browse(int(product_id))
            if product and hasattr(product, 'is_storable') and not product.is_storable:
                return float('inf')
            if product and product.type in ('service', 'combo'):
                return float('inf')

            domain = [('product_id', '=', int(product_id))]
            if config_id:
                config = self.env['pos.config'].sudo().browse(int(config_id))
                if config and config.picking_type_id and config.picking_type_id.default_location_src_id:
                    domain.append(('location_id', '=', config.picking_type_id.default_location_src_id.id))
                else:
                    domain.append(('location_id.usage', '=', 'internal'))
            else:
                domain.append(('location_id.usage', '=', 'internal'))

            quants = self.env['stock.quant'].sudo().search(domain)
            return sum(quants.mapped('quantity'))
        except Exception as e:
            _logger.error("Error al consultar get_realtime_product_stock: %s", str(e))
            return 0.0
