from odoo import models, fields, api
from datetime import date

class PosPayment(models.Model):
    _inherit = 'pos.payment'

    tasa_usd = fields.Float(string="Tasa", compute='_compute_amount_usd', store=True)
    amount_usd = fields.Float(string="Importe en USD", compute='_compute_amount_usd', store=True)

    @api.depends('amount', 'payment_date')
    def _compute_amount_usd(self):
        usd_currency = self.env.ref('base.USD')
        for rec in self:
            fecha = rec.payment_date or date.today()
            rate = self.env['res.currency.rate'].search([
                ('currency_id', '=', usd_currency.id),
                ('name', '<=', fecha)
            ], order='name desc', limit=1)
            tasa = rate.inverse_company_rate if rate else 1.0
            rec.tasa_usd = tasa
            rec.amount_usd = rec.amount / tasa if tasa else 0.0
