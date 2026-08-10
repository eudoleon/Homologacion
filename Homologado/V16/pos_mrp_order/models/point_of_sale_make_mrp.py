# -*- coding: utf-8 -*-
##############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2019-TODAY Cybrosys Technologies(<https://www.cybrosys.com>).
#    Author: Nikhil krishnan(odoo@cybrosys.com)
#    you can modify it under the terms of the GNU AFFERO
#    GENERAL PUBLIC LICENSE (AGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU AFFERO GENERAL PUBLIC LICENSE (AGPL v3) for more details.
#
#    You should have received a copy of the GNU AFFERO GENERAL PUBLIC LICENSE
#    GENERAL PUBLIC LICENSE (AGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from odoo import models, fields, api
from odoo.exceptions import ValidationError
try:
    from odoo.tools.float_utils import float_round
except Exception:
    from odoo.tools import float_round


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    def create_mrp_from_pos(self, products):
        product_ids = []
        if products:
            for product in products:
                if self.env['product.product'].browse(int(product['id'])).to_make_mrp:
                    flag = 1
                    if product_ids:
                        for product_id in product_ids:
                            if product_id['id'] == product['id']:
                                product_id['qty'] += product['qty']
                                flag = 0
                    if flag:
                        product_ids.append(product)
            for prod in product_ids:
                if prod['qty'] > 0:
                    product = self.env['product.product'].browse(int(prod['id']))
                    # Buscar primero la BoM por variante, luego por template
                    bom = self.env['mrp.bom'].search([
                        ('product_id', '=', product.id)
                    ], limit=1)
                    if not bom:
                        bom = self.env['mrp.bom'].search([
                            ('product_tmpl_id', '=', product.product_tmpl_id.id),
                            ('product_id', '=', False)
                        ], limit=1)
                    if not bom:
                        continue  # No hay BoM, no crear MRP
                    vals = {
                        'origin': 'POS-' + prod['pos_reference'],
                        'state': 'confirmed',
                        'product_id': product.id,
                        'product_tmpl_id': product.product_tmpl_id.id,
                        'product_uom_id': product.uom_id.id,
                        'product_qty': prod['qty'],
                        'bom_id': bom.id,
                    }
                    mrp_order = self.sudo().create(vals)
                    # Si el POS envió una ubicación de stock, usarla como ubicación origen y destino del pedido
                    pos_loc = False
                    if isinstance(prod, dict):
                        pos_loc = prod.get('location_id') or prod.get('pos_location_id')
                    if pos_loc:
                        try:
                            pos_loc_id = int(pos_loc)
                            loc = self.env['stock.location'].browse(pos_loc_id)
                            if loc.exists():
                                # Establecer ubicación origen y destino a la ubicación de la caja
                                mrp_order.sudo().write({
                                    'location_src_id': pos_loc_id,
                                    'location_dest_id': pos_loc_id,
                                })
                        except Exception:
                            pass
                    list_value = []
                    # Calcular la cantidad base de la BoM
                    bom_qty = bom.product_qty if bom.product_qty else 1.0
                    for bom_line in bom.bom_line_ids:
                        # Determinar ubicación origen más adecuada (buscar sububicaciones del POS con stock suficiente)
                        required_qty = (bom_line.product_qty * prod['qty']) / bom_qty
                        # Redondear la cantidad requerida al múltiplo de la precisión de la UoM para que "A consumir" y "La cantidad consumida" coincidan
                        try:
                            uom_rounding_line = bom_line.product_uom_id.rounding if bom_line.product_uom_id else bom_line.product_id.uom_id.rounding
                            if uom_rounding_line and uom_rounding_line > 0:
                                from math import ceil
                                rounded_qty = float(ceil((required_qty) / uom_rounding_line) * uom_rounding_line)
                            else:
                                rounded_qty = required_qty
                        except Exception:
                            rounded_qty = required_qty
                        source_loc_id = mrp_order.location_src_id.id if mrp_order.location_src_id else False
                        if mrp_order.location_src_id:
                            # Buscar únicamente sububicaciones internas (excluyendo la ubicación padre)
                            candidate_locs = self.env['stock.location'].search([
                                ('usage', '=', 'internal'),
                                ('id', 'child_of', mrp_order.location_src_id.id),
                                ('id', '!=', mrp_order.location_src_id.id),
                            ])
                            best_loc = None
                            # Primero buscar una ubicación con stock suficiente
                            for loc in candidate_locs:
                                try:
                                    avail = bom_line.product_id.with_company(mrp_order.company_id.id).with_context(location=loc.id).qty_available
                                except Exception:
                                    avail = 0.0
                                if avail >= required_qty - 1e-6:
                                    best_loc = loc
                                    break
                            # Si no hay ninguna con stock suficiente, elegir la que tenga más stock disponible
                            if not best_loc and candidate_locs:
                                best_qty = 0.0
                                for loc in candidate_locs:
                                    try:
                                        avail = bom_line.product_id.with_company(mrp_order.company_id.id).with_context(location=loc.id).qty_available
                                    except Exception:
                                        avail = 0.0
                                    if avail > best_qty:
                                        best_qty = avail
                                        best_loc = loc
                            # Si se encontró una sububicación usarla, si no, usar la ubicación padre
                            if best_loc:
                                source_loc_id = best_loc.id
                            else:
                                # Fallback a la ubicación padre si no hay sububicaciones
                                source_loc_id = mrp_order.location_src_id.id if mrp_order.location_src_id else source_loc_id
                        list_value.append((0, 0, {
                            'raw_material_production_id': mrp_order.id,
                            'name': mrp_order.name,
                            'product_id': bom_line.product_id.id,
                            'product_uom': bom_line.product_uom_id.id,
                            'product_uom_qty': rounded_qty,
                            'picking_type_id': mrp_order.picking_type_id.id,
                            'location_id': source_loc_id,
                            'location_dest_id': bom_line.product_id.with_company(self.company_id.id).property_stock_production.id,
                            'company_id': mrp_order.company_id.id,
                        }))
                    finished_vals = {
                        'product_id': product.id,
                        'product_uom_qty': prod['qty'],
                        'product_uom': product.uom_id.id,
                        'name': mrp_order.name,
                        'date_deadline': mrp_order.date_deadline,
                        'picking_type_id': mrp_order.picking_type_id.id,
                        'location_id': mrp_order.location_src_id.id,
                        'location_dest_id': mrp_order.location_dest_id.id,
                        'company_id': mrp_order.company_id.id,
                        'production_id': mrp_order.id,
                        'warehouse_id': mrp_order.location_dest_id.warehouse_id.id,
                        'origin': mrp_order.name,
                        'group_id': mrp_order.procurement_group_id.id,
                        'propagate_cancel': mrp_order.propagate_cancel,
                    }
                    mrp_order.update({'move_raw_ids': list_value,
                                      'move_finished_ids': [
                                          (0, 0, finished_vals)]
                                      })
                    # Confirmar y marcar como hecho automáticamente
                    mrp_order.action_confirm()
                    mrp_order.write({'qty_producing': prod['qty']})
                    for line in mrp_order.move_raw_ids:
                        # Ajustar quantity_done según redondeo de la UoM para evitar error de precisión
                        uom_rounding = line.product_uom.rounding if line.product_uom else line.product_id.uom_id.rounding
                        qty = line.product_uom_qty
                        try:
                            # Redondear hacia arriba al múltiplo de la precisión de la UoM para asegurar suficiente cantidad
                            if uom_rounding and uom_rounding > 0:
                                from math import ceil
                                qty_done = float(ceil((qty) / uom_rounding) * uom_rounding)
                            else:
                                qty_done = qty
                        except Exception:
                            qty_done = qty
                        # Asegurar precisión final con float_round
                        try:
                            qty_done = float_round(qty_done, precision_rounding=uom_rounding)
                        except Exception:
                            pass
                        line.write({'quantity_done': qty_done})
                    # Validar stock de materiales por ubicación origen para evitar inventario negativo
                    needed = {}
                    for line in mrp_order.move_raw_ids:
                        qty_needed = line.product_uom_qty
                        if not qty_needed or qty_needed <= 0:
                            continue
                        src_loc = line.location_id or mrp_order.location_src_id
                        loc_id = src_loc.id if src_loc else False
                        key = (line.product_id.id, loc_id)
                        needed[key] = needed.get(key, 0.0) + qty_needed
                    materiales_sin_stock = False
                    for (prod_id, loc_id), qty_needed in needed.items():
                        product_rec = self.env['product.product'].browse(prod_id)
                        try:
                            if loc_id:
                                available = product_rec.with_context(location=loc_id).qty_available
                            else:
                                available = product_rec.qty_available
                        except Exception:
                            available = 0.0
                        if available < (qty_needed - 1e-6):
                            materiales_sin_stock = True
                            break
                    # Si todos los materiales tienen stock suficiente, marcar como hecho
                    if not materiales_sin_stock:
                        mrp_order.button_mark_done()
        return True


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    to_make_mrp = fields.Boolean(string='To Create MRP Order',
                                 help="Check if the product should be make mrp order")

    @api.onchange('to_make_mrp')
    def onchange_to_make_mrp(self):
        if self.to_make_mrp:
            if not self.bom_count:
                raise ValidationError('Please set Bill of Material for this product.')


class ProductProduct(models.Model):
    _inherit = 'product.product'

    @api.onchange('to_make_mrp')
    def onchange_to_make_mrp(self):
        if self.to_make_mrp:
            if not self.bom_count:
                raise Warning('Please set Bill of Material for this product.')