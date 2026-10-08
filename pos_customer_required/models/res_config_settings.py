# -*- coding: utf-8 -*-
from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pos_require_customer = fields.Selection(
        related='pos_config_id.require_customer',
        readonly=False
    )
