from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class PosPaymentMethod(models.Model):
	_inherit = 'pos.payment.method'

	pago_usd = fields.Boolean("Pago $")

	@api.model
	def _load_pos_data_fields(self, config):
		fields_list = super()._load_pos_data_fields(config)
		if fields_list and 'pago_usd' not in fields_list:
			fields_list = list(fields_list) + ['pago_usd']
		return fields_list


class PosPayment(models.Model):
	_inherit="pos.payment"

	usd_amt = fields.Float("USD $")


class PosOrder(models.Model):
	_inherit = "pos.order"

	@api.model
	def _payment_fields(self, order, ui_paymentline):
		res = super(PosOrder, self)._payment_fields(order, ui_paymentline)
		res.update({
			'usd_amt': ui_paymentline.get('usd_amt')or 0.0,
		})
		return res


class PosSession(models.Model):
	_inherit = 'pos.session'

	def _loader_params_pos_payment_method(self):
		result = super(PosSession, self)._loader_params_pos_payment_method()
		result['search_params']['fields'].extend(['pago_usd'])
		return result


class PosConfig(models.Model):
	_inherit = "pos.config"

	show_dual_currency = fields.Boolean("Show dual currency", help="Show Other Currency in POS", default=False)
	rate_company = fields.Float(string='Rate', related='currency_id.rate')
	show_currency = fields.Many2one('res.currency', string='Currency.', default=lambda self: self.env['res.currency'].search([('name', '=', 'USD')], limit=1))
	show_currency_rate = fields.Float(string='Rate.', related='show_currency.rate',readonly=False)
	show_currency_symbol = fields.Char(related='show_currency.symbol',readonly=False)
	show_currency_position = fields.Selection(related='show_currency.position')
	cstm_default_location_src_id = fields.Many2one("stock.location", related="picking_type_id.default_location_src_id")

	@api.constrains('pricelist_id', 'use_pricelist', 'available_pricelist_ids', 'journal_id', 'invoice_journal_id', 'payment_method_ids')
	def _check_currencies(self):
		# Override del core: se omite la validación de que los métodos de pago estén en la misma
		# moneda que el POS, ya que los métodos en USD usan diarios en dólares.
		for config in self:
			if config.use_pricelist and config.pricelist_id and config.pricelist_id not in config.available_pricelist_ids:
				raise ValidationError(_("The default pricelist must be included in the available pricelists."))

			if config.use_pricelist and any(config.available_pricelist_ids.mapped(lambda pricelist: pricelist.currency_id != config.currency_id)):
				raise ValidationError(_("All available pricelists must be in the same currency as the company or"
										" as the Sales Journal set on this point of sale if you use"
										" the Accounting application."))
			if config.invoice_journal_id.currency_id and config.invoice_journal_id.currency_id != config.currency_id:
				raise ValidationError(_("The invoice journal must be in the same currency as the Sales Journal or the company currency if that is not set."))

	def _load_pos_self_data_fields(self, config_id):
		params = super()._load_pos_self_data_fields(config_id) if hasattr(super(), '_load_pos_self_data_fields') else []
		params.extend([
			'show_dual_currency',
			'show_currency_rate',
			'show_currency_symbol',
			'show_currency_position',
			'rate_company',
		])
		return params

	def _get_self_ordering_data(self):
		res = super()._get_self_ordering_data() if hasattr(super(), '_get_self_ordering_data') else {}
		if 'pos.config' in res and res['pos.config'].get('data'):
			cfg_dict = res['pos.config']['data'][0]
			cfg_dict.update({
				'show_dual_currency': self.show_dual_currency,
				'show_currency_rate': self.show_currency_rate,
				'show_currency_symbol': self.show_currency_symbol,
				'show_currency_position': self.show_currency_position,
				'rate_company': self.rate_company,
			})
		return res



class ResConfigSettings(models.TransientModel):
	_inherit = 'res.config.settings'
	
	show_dual_currency = fields.Boolean(related='pos_config_id.show_dual_currency',readonly=False)
	rate_company = fields.Float(related='pos_config_id.rate_company',readonly=False)
	show_currency = fields.Many2one(related='pos_config_id.show_currency',readonly=False)
	show_currency_rate = fields.Float(related='pos_config_id.show_currency_rate',readonly=False)
	show_currency_symbol = fields.Char(related='pos_config_id.show_currency_symbol',readonly=False)
	show_currency_position = fields.Selection(related='pos_config_id.show_currency_position',readonly=False)
	cstm_default_location_src_id = fields.Many2one(related='pos_config_id.cstm_default_location_src_id',readonly=False)


class AccountMove(models.Model):
	_inherit = "account.move"

	currency_rate = fields.Monetary(string='Tasa' , currency_field='vef_currency_id')
	#impuesto_en_vef = fields.Monetary(string='Impuesto en USD', compute='_compute_currency_amount', currency_field='vef_currency_id')
	# total_amount_vef = fields.Monetary(string='Total en USD', compute='_compute_currency_amount', currency_field='vef_currency_id')
	vef_currency_id = fields.Many2one('res.currency', 'Currency.', default=lambda self: self.env.ref('base.USD') )
	usd_currency_id = fields.Many2one('res.currency', 'Currency..', default=lambda self: self.env.ref('base.VEF'))
	
	@api.onchange('vef_currency_id')
	def onchange_vef_currency(self):
		for move in self:
			move.currency_id = move.vef_currency_id.id
