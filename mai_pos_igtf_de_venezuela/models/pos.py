# -*- coding: utf-8 -*-

from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError


class PosPaymentMethod(models.Model):
	_inherit = 'pos.payment.method'

	is_igtf = fields.Boolean("Is IGTF ?")


class AccountBankStatementLine(models.Model):
	_inherit = 'account.bank.statement.line'

	igtf_pos_amount = fields.Float("IGTF Amount",compute="_compute_igtf_amt",store=True)

	@api.depends('pos_session_id', 'pos_session_id.order_ids', 'pos_session_id.order_ids.igtf_amount')
	def _compute_igtf_amt(self):
		for rec in self:
			rec.igtf_pos_amount = 0
			if rec.pos_session_id :
				rec.igtf_pos_amount = sum(rec.pos_session_id.order_ids.mapped('igtf_amount'))


class PosConfig(models.Model):
	_inherit = 'pos.config'

	igtf_product_id = fields.Many2one('product.product',string="Product IGTF ",domain=[('type', '=', 'service'),('available_in_pos','=',True)])


class ResConfigSettings(models.TransientModel):
	_inherit = 'res.config.settings'
	
	igtf_product_id = fields.Many2one(related='pos_config_id.igtf_product_id',readonly=False)


class PosOrder(models.Model):
	_inherit = 'pos.order'

	igtf_amount = fields.Float("IGTF Amount",store=True)

	igtf_percentage = fields.Float(string='% IGTF Divisa',related="company_id.igtf_percentage",store=False)
	igtf_payment_method_id = fields.Many2one("pos.payment.method","IGTF Payment Method" ,compute="_compute_pos_igtf_amt",store=False)
	igtf_total_amount = fields.Float("Total Amount + IGTF" ,compute="_compute_pos_igtf_amt",store=False)

	@api.depends('payment_ids.payment_method_id', 'payment_ids.amount', 'amount_total', 'igtf_amount')
	def _compute_pos_igtf_amt(self):
		for rec in self:
			pay_method = False
			for pl in rec.payment_ids :
				if pl.payment_method_id.is_igtf :
					pay_method = pl.payment_method_id.id

			rec.igtf_payment_method_id = pay_method
			rec.igtf_total_amount = rec.amount_total

	@api.model
	def _order_fields(self, ui_order):
		res = super(PosOrder, self)._order_fields(ui_order)
		igtf_charge = ui_order.get('igtf_amount') or ui_order.get('igtf_charge') or 0.0
		res['igtf_amount'] = igtf_charge
		return res

	@api.model
	def sync_from_ui(self, orders):
		for order_data in orders:
			data = order_data.get('data') or order_data
			igtf_amount = data.get('igtf_amount') or data.get('igtf_charge') or 0.0
			data['igtf_amount'] = igtf_amount
			if igtf_amount > 0:
				current_total = float(data.get('amount_total', 0.0))
				data['amount_total'] = current_total + float(igtf_amount)
		return super(PosOrder, self).sync_from_ui(orders)

	@api.depends('igtf_amount')
	def _compute_amount_all(self):
		super(PosOrder, self)._compute_amount_all()
		for order in self:
			if order.igtf_amount:
				order.amount_total += order.igtf_amount
				order.amount_paid += order.igtf_amount

	def _prepare_igtf_invoice_line(self):
		return {
			'product_id': self.session_id.config_id.igtf_product_id.id,
			'quantity': 1,
			'price_unit': self.igtf_amount,
			'name': 'IGTF',
			'tax_ids': [(6, 0, [])],
		}

	def _prepare_invoice_vals(self):
		res = super(PosOrder, self)._prepare_invoice_vals()
		invoice_line_ids = list(res.get('invoice_line_ids', []))
		if self.igtf_amount and self.igtf_amount > 0 and self.session_id.config_id.igtf_product_id:
			existing_igtf_line = any((line and len(line) > 2 and line[2] and line[2].get('name') == 'IGTF') for line in invoice_line_ids)
			if not existing_igtf_line:
				invoice_line_ids.append((0, 0, self._prepare_igtf_invoice_line()))
		res['invoice_line_ids'] = invoice_line_ids
		return res


	def _prepare_refund_values(self, current_session):
		res = super(PosOrder, self)._prepare_refund_values(current_session)
		res['igtf_amount'] = -self.igtf_amount
		res['ticket_fiscal'] = False
		res['serial_fiscal'] = False
		res['fecha_fiscal'] = False

		return res


class AccountMove(models.Model):
	_inherit = 'account.move'

	pos_order_id = fields.Many2one('pos.order',string="POS order")
	igtf_percentage = fields.Float(string='% IGTF Divisa',related="pos_order_id.igtf_percentage",store=False)
	igtf_payment_method_id = fields.Many2one("pos.payment.method","IGTF Payment Method" ,related="pos_order_id.igtf_payment_method_id",store=False)
	igtf_amount = fields.Float("IGTF Amount" ,related="pos_order_id.igtf_amount",store=False)
	igtf_total_amount = fields.Float("Total Amount + IGTF" ,related="pos_order_id.igtf_total_amount",store=False)


