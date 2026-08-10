from odoo import models, fields, api

class PosOrder(models.Model):
    _inherit = 'pos.order'

    tasa_usd = fields.Float(string="Tasa USD", compute='_compute_tasa_usd', store=True)
    monto_usd = fields.Float(string="Monto en USD", compute='_compute_monto_usd', store=True)

    @api.depends('date_order')
    def _compute_tasa_usd(self):
        usd_currency = self.env.ref('base.USD')
        for order in self:
            rate = self.env['res.currency.rate'].search([
                ('currency_id', '=', usd_currency.id),
                ('name', '<=', order.date_order.date())
            ], order='name desc', limit=1)
            order.tasa_usd = rate.inverse_company_rate if rate else 0.0

    @api.depends('amount_total', 'tasa_usd')
    def _compute_monto_usd(self):
        for order in self:
            order.monto_usd = order.amount_total / order.tasa_usd if order.tasa_usd else 0.0
