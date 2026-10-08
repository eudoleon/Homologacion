from odoo import models, fields, api, _

class ResCompany(models.Model):
    _inherit = "res.company"

    currency_rate_bcv = fields.Boolean(string='Automatic Currency BCV')
    currency_available_ids = fields.Many2many('res.currency',
        string='Currencies Available', )
    block_days_bcv = fields.Boolean(string='Block days BCV', default=False)
    days_bcv_ids = fields.Many2many('days.bcv', string='Days')