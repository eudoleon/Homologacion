from odoo import models, fields, api, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    currency_rate_bcv = fields.Boolean(string='Automatic Currency BCV',
        related='company_id.currency_rate_bcv', readonly=False,)
    currency_available_ids = fields.Many2many('res.currency',
        string='Currencies Available (BCV)', readonly=False,
        related='company_id.currency_available_ids', )
    block_days_bcv = fields.Boolean(string='Block days BCV',
        related='company_id.block_days_bcv', readonly=False)
    days_bcv_ids = fields.Many2many(
        'days.bcv',
        string='Days',
        related='company_id.days_bcv_ids',
        readonly=False,
    )