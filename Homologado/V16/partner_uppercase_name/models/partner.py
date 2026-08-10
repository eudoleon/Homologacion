# -*- coding: utf-8 -*-
from odoo import models, api

class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def create(self, vals):
        if 'name' in vals and vals['name']:
            vals['name'] = vals['name'].upper()
        return super(ResPartner, self).create(vals)

    def write(self, vals):
        if 'name' in vals and vals['name']:
            vals['name'] = vals['name'].upper()
        return super(ResPartner, self).write(vals)