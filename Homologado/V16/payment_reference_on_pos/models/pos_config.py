from odoo import models, fields, api, _

class pos_config(models.Model):
    _inherit = 'pos.config'

    is_allow_payment_reference = fields.Boolean(
        string="Payment Reference",
        default=True,
        help="If enabled, the cashier will be able to add payment references on each POS payment line.")

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    is_allow_payment_reference = fields.Boolean(
        related='pos_config_id.is_allow_payment_reference', 
        string='If enabled, the cashier will be able to add payment references on each POS payment line.',
        readonly=False)

