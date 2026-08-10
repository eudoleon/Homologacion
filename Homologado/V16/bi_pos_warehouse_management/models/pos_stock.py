# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api,tools, _
from datetime import datetime, timedelta
import json
from odoo.exceptions import RedirectWarning, UserError, ValidationError ,Warning
import logging
from itertools import groupby
from collections import defaultdict
from odoo.tools import float_is_zero, float_compare
_logger = logging.getLogger(__name__)


class POSConfigShop(models.Model):
	_inherit = 'pos.config'

	def _get_default_location(self):
		return self.env['stock.warehouse'].search([('company_id', '=', self.env.user.company_id.id)], limit=1).lot_stock_id
	
	display_stock_pos = fields.Boolean('Display Stock in POS')
	stock_location_id = fields.Many2one(
		'stock.location', string='Stock Location',
		domain=[('usage', '=', 'internal')], default=_get_default_location)
	unavailable_msg = fields.Char('Unavailable Message')
	warehouse_available_ids = fields.Many2many('stock.location', string='Related Stock Location',domain=[('usage', '=', 'internal')])
	
	def get_locations(self):    
		warehouse_loc_obj = self.env['stock.location'].search([('id', 'in', self.warehouse_available_ids)]) 
		return warehouse_loc_obj

	@api.model_create_multi
	def create(self, vals_list):
		res=super(POSConfigShop, self).create(vals_list)
		for vals in vals_list:
			if vals.get('display_stock_pos'):
				if vals.get('stock_location_id') not in vals.get('warehouse_available_ids'):
					raise ValidationError(_('Please add default location in available locations'))
		return res


	def write(self, vals):
		if vals.get('stock_location_id'):
			vals['warehouse_available_ids']=[(4,vals.get('stock_location_id'))]

		res=super(POSConfigShop, self).write(vals)
		return res

class ResConfigSettings(models.TransientModel):
	_inherit = 'res.config.settings'

	

	pos_display_stock_pos = fields.Boolean(related='pos_config_id.display_stock_pos',string='Display Stock in POS',readonly=False)
	pos_stock_location_id = fields.Many2one(
		related='pos_config_id.stock_location_id', string='Stock Location',
		domain=[('usage', '=', 'internal')],readonly=False)
	pos_unavailable_msg = fields.Char(related='pos_config_id.unavailable_msg',string='Unavailable Message',readonly=False)
	pos_warehouse_available_ids = fields.Many2many(related='pos_config_id.warehouse_available_ids',readonly=False)
		

class PosOrderLineInherit(models.Model):
	_inherit = 'pos.order.line'

	stock_location_id = fields.Char(string="stock location id")


class RelatedPickingsPos(models.Model):
	_inherit = 'pos.order'


	def _create_order_picking(self):
		self.ensure_one()
		if self.to_ship:
			self.lines._launch_stock_rule_from_pos_order_lines()
		else:
			if self._should_create_picking_real_time():
				picking_type = self.config_id.picking_type_id
				if self.partner_id.property_stock_customer:
					destination_id = self.partner_id.property_stock_customer.id
				elif not picking_type or not picking_type.default_location_dest_id:
					destination_id = self.env['stock.warehouse']._get_partner_locations()[0].id
				else:
					destination_id = picking_type.default_location_dest_id.id

				for line in self.lines:
					if line.qty < 0 and not line.stock_location_id and 'refunded_orderline_id' in line._fields and line.refunded_orderline_id:
						if line.refunded_orderline_id.stock_location_id:
							line.stock_location_id = line.refunded_orderline_id.stock_location_id
						else:
							# Fallback: infer original source location from done moves of the
							# refunded order, so returns go back to the same location where
							# stock was deducted.
							original_order = line.refunded_orderline_id.order_id
							move = self.env['stock.move'].search([
								('picking_id.pos_order_id', '=', original_order.id),
								('product_id', '=', line.product_id.id),
								('state', '=', 'done'),
								('quantity_done', '>', 0),
								('location_dest_id.usage', '=', 'customer'),
							], limit=1, order='id desc')
							if move and move.location_id:
								line.stock_location_id = str(move.location_id.id)

				# Dividir líneas con ubicación asignada y sin ella
				different = self.lines.filtered(lambda l: l.stock_location_id)
				normal = self.lines - different

				# 🔒 Solo crear picking general si hay líneas sin ubicación personalizada
				if normal:
					pickings = self.env['stock.picking']._create_picking_from_pos_order_lines(
						destination_id, normal, picking_type, self.partner_id
					)
					pickings.write({
						'pos_session_id': self.session_id.id,
						'pos_order_id': self.id,
						'origin': self.name
					})

				# 🔁 Crear pickings personalizados por línea con ubicación definida
				for line in different:
					diff_pick = self.env['stock.picking'].with_context(
						diff_loc=line.stock_location_id
					)._create_picking_from_pos_order_lines(
						destination_id, line, picking_type, self.partner_id
					)
					diff_pick.write({
						'pos_session_id': self.session_id.id,
						'pos_order_id': self.id,
						'origin': self.name
					})	


class RelatedPosStock(models.Model):
	_inherit = 'stock.picking'
	
	pos_id = fields.Many2one('pos.order', 'Related POS')



	def _prepare_stock_move_vals_for_sub_product(self, first_line, order_lines,loc):
		qty = sum(order_lines.mapped('qty'))
		location_id = int(loc)
		location_dest_id = self.location_dest_id.id
		if qty < 0:
			location_id = self.location_id.id
			location_dest_id = int(loc)
			qty = abs(qty)
			
		return {
			'name': first_line.name,
			'product_uom': first_line.product_id.uom_id.id,
			'picking_id': self.id,
			'picking_type_id': self.picking_type_id.id,
			'product_id': first_line.product_id.id,
			'product_uom_qty': qty,
			'state': 'draft',
			'location_id': location_id,
			'location_dest_id': location_dest_id,
			'company_id': self.company_id.id,
		}

	def _create_move_from_pos_order_lines(self, lines):
		self.ensure_one()
		lines_by_product = groupby(sorted(lines, key=lambda l: l.product_id.id), key=lambda l: l.product_id.id)
		move_vals = []
		for dummy, olines in lines_by_product:
			order_lines = self.env['pos.order.line'].concat(*olines)
			first_line = order_lines[0]
			if first_line.stock_location_id:
				move_vals.append(self._prepare_stock_move_vals_for_sub_product(order_lines[0], order_lines,first_line.stock_location_id))
			else:
				# Distribute the qty across configured POS locations when possible so
				# stock is reserved/deducted only from allowed locations.
				product = first_line.product_id
				total_qty = sum(order_lines.mapped('qty'))
				# For returns (negative qty), keep the standard move creation behavior.
				# The positive-allocation logic below is only for outgoing quantities.
				if total_qty < 0:
					move_vals.append(self._prepare_stock_move_vals(order_lines[0], order_lines))
					continue
				config = False
				if first_line.order_id and first_line.order_id.config_id:
					config = first_line.order_id.config_id
				allocated = 0.0
				if config and config.warehouse_available_ids:
					for loc in config.warehouse_available_ids:
						if allocated >= total_qty:
							break
						# compute available qty at this loc
						quants = self.env['stock.quant'].sudo().search([('product_id','=',product.id),('location_id','=',loc.id)])
						avail = 0.0
						for q in quants:
							avail += q.quantity
						# qty to take from this loc
						take = min(avail, total_qty - allocated)
						if take > 0:
							# create a move taking 'take' qty from this loc
							move_vals.append(self._prepare_stock_move_vals_for_sub_product(order_lines[0], order_lines, loc.id))
							# But adjust the last appended move's qty to 'take'
							move_vals[-1]['product_uom_qty'] = take
							allocated += take
				# If nothing was allocated (no configured locs or insufficient), fallback
				if allocated < total_qty:
					# fallback to default behavior (may consume from other locations)
					move_vals.append(self._prepare_stock_move_vals(order_lines[0], order_lines))
		moves = self.env['stock.move'].create(move_vals)
		confirmed_moves = moves._action_confirm()
		confirmed_moves._add_mls_related_to_order(lines, are_qties_done=True)
		self._link_owner_on_return_picking(lines)


	@api.model
	def _create_picking_from_pos_order_lines(self, location_dest_id, lines, picking_type, partner=False):
		"""We'll create some picking based on order_lines"""

		pickings = self.env['stock.picking']
		stockable_lines = lines.filtered(lambda l: l.product_id.type in ['product', 'consu'] and not float_is_zero(l.qty, precision_rounding=l.product_id.uom_id.rounding))
		if not stockable_lines:
			return pickings

		pos_order_id = []
		for rec in stockable_lines:
			if rec.order_id not in pos_order_id:
				pos_order_id.append(rec.order_id)
		if len(pos_order_id)>0:
			config_id = pos_order_id[0].config_id.id

		positive_lines = stockable_lines.filtered(lambda l: l.qty > 0)
		negative_lines = stockable_lines - positive_lines
		location_id = picking_type.default_location_src_id.id
		if positive_lines:
			config_search = self.env['pos.config'].sudo().browse(config_id)
			if config_search:
				location_id = config_search.stock_location_id.id
			
			if self._context.get('diff_loc'):
				location_id = self._context.get('diff_loc')

			positive_picking = self.env['stock.picking'].create(
				self._prepare_picking_vals(partner, picking_type, location_id, location_dest_id)
			)

			positive_picking._create_move_from_pos_order_lines(positive_lines)
			self.env.flush_all()
			try:
				with self.env.cr.savepoint():
					positive_picking._action_done()
			except (UserError, ValidationError):
				pass

			pickings |= positive_picking
		if negative_lines:
			if picking_type.return_picking_type_id:
				return_picking_type = picking_type.return_picking_type_id
				return_location_id = return_picking_type.default_location_dest_id.id
			else:
				return_picking_type = picking_type
				return_location_id = picking_type.default_location_src_id.id

			if self._context.get('diff_loc'):
				return_location_id = int(self._context.get('diff_loc'))

			negative_picking = self.env['stock.picking'].create(
				self._prepare_picking_vals(partner, return_picking_type, location_dest_id, return_location_id)
			)
			negative_picking._create_move_from_pos_order_lines(negative_lines)
			self.env.flush_all()
			try:
				with self.env.cr.savepoint():
					negative_picking._action_done()
			except (UserError, ValidationError):
				pass
			pickings |= negative_picking
		return pickings



class WarehouseStockQty(models.Model):
	_inherit = 'stock.quant'


	def get_product_stock(self, location, other_locations, product):
		# Normalize location parameter: it can be an int, an array like [id, name], or a dict/object
		def _loc_id(loc):
			if loc is None:
				return False
			# list/tuple like [id, name]
			if isinstance(loc, (list, tuple)) and len(loc) > 0:
				return int(loc[0])
			# dict/object like {'id': id}
			if isinstance(loc, dict) and 'id' in loc:
				return int(loc['id'])
			# otherwise assume it's an id
			try:
				return int(loc)
			except Exception:
				return False

		loc_id = _loc_id(location)
		quants1 = self.env['stock.quant'].search([('product_id', '=', product),('location_id','=', loc_id)])
		if len(quants1) > 1:
				qty = 0.0
				for quant in quants1:
					qty += quant.quantity
		else:
			qty = quants1.quantity
		
		res = []
		for locations in other_locations:
			other_loc_id = _loc_id(locations)
			quants2 = self.env['stock.quant'].search([('product_id', '=', int(product)),('location_id','=', int(other_loc_id))])
			if len(quants2) > 1:
				qty1 = 0.0
				for quant in quants2:
					qty1 += quant.quantity
				res.append({'quantity': qty1, 'location': locations, 'product': product})
				
			else:
				qty1 = quants2.quantity
				res.append({'quantity' : qty1, 'location': locations, 'product': product})
		return [qty, res]
		
	def get_loc_stock(self,location_id, product_id):
		quants1 = self.env['stock.quant'].search([('product_id', '=', int(product_id)),('location_id','=', int(location_id))])
		if quants1:
			return quants1.quantity 
	

class Product(models.Model):
	_inherit = 'product.product'

	quant_ids = fields.One2many("stock.quant","product_id",string="Quants",
		domain=[('location_id.usage','=','internal')])

	quant_text = fields.Text('Quant Qty',compute='_compute_avail_locations',store=False)
	has_bom = fields.Boolean(compute='_compute_has_bom', string='Has BOM')

	def _compute_has_bom(self):
		for rec in self:
			bom_count = self.env['mrp.bom'].sudo().search_count([
				'|',
				('product_id', '=', rec.id),
				'&',
				('product_id', '=', False),
				('product_tmpl_id', '=', rec.product_tmpl_id.id)
			])
			rec.has_bom = bom_count > 0

	@api.depends('quant_ids','quant_ids.location_id','quant_ids.quantity')
	def _compute_avail_locations(self):
		for rec in self:
			rec.quant_text = ''
			quants = self.env['stock.quant'].sudo().search([('product_id', 'in', rec.ids)])

			all_data = {}
			for quant in rec.quant_ids:
				loc = quant.location_id.id
				if loc in all_data:
					all_data[loc] += quant.quantity
				else:
					all_data[loc] = quant.quantity

			# qnt = dict(zip( rec.quant_ids.mapped('location_id.id') , rec.quant_ids.mapped('quantity') ))
			rec.quant_text = json.dumps(all_data)

class POSSession(models.Model):
	_inherit = 'pos.session'


	def _pos_ui_models_to_load(self):
		result = super()._pos_ui_models_to_load()
		new_model = 'stock.location'
		if new_model not in result:
			result.append(new_model)
		return result

	def _loader_params_stock_location(self):
		return {
			'search_params': {
				'domain': [('id', 'in', self.config_id.warehouse_available_ids.ids)], 
				'fields': ['name','complete_name']
			}
		}
		
	def _get_pos_ui_stock_location(self, params):
		return self.env['stock.location'].search_read(**params['search_params'])

	def _loader_params_product_product(self):
		res = super(POSSession, self)._loader_params_product_product()
		fields = res.get('search_params').get('fields')
		fields.extend(['name','type','quant_text','has_bom'])
		res['search_params']['fields'] = fields
		return res

	def _pos_data_process(self, loaded_data):
		super()._pos_data_process(loaded_data)
		prods = {}
		# Build a set of allowed location ids coming from loaded stock.location (these are already
		# filtered by the POS config loader params). This ensures we only expose quant data
		# for locations actually configured in the POS.
		allowed_loc_ids = set()
		for loc in loaded_data.get('stock.location', []):
			try:
				allowed_loc_ids.add(int(loc.get('id')))
			except Exception:
				pass

		for rec in loaded_data['product.product'] :
			# Convertir el JSON de quant_text a un dict y filtrar sólo las ubicaciones permitidas
			if rec.get('quant_text'):
				try:
					raw = json.loads(rec['quant_text'])
					# Keep only keys that are in allowed_loc_ids
					filtered = {}
					for k, v in (raw.items() if isinstance(raw, dict) else []):
						try:
							kid = int(k)
							if kid in allowed_loc_ids:
								filtered[kid] = v
						except Exception:
							continue
					prods[rec['id']] = filtered
					# Also update the incoming record so the client-side `product.quant_text`
					# does not contain quant info for unallowed locations. Keep it as JSON
					# so older client code that still reads `quant_text` will only see
					# permitted locations.
					try:
						rec['quant_text'] = json.dumps(filtered)
					except Exception:
						rec['quant_text'] = '{}'
				except Exception:
					prods[rec['id']] = {}
			else:
				prods[rec['id']] = {}
		loaded_data['prod_with_quant'] = prods
		loc_by_id={}
		for rec in loaded_data['stock.location']:
			loc_by_id[rec['id']]=rec
		loaded_data['pos_custom_location'] = loaded_data['stock.location']
		loaded_data['loc_by_id'] = loc_by_id    




