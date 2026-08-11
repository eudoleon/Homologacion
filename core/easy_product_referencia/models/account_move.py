# -*- coding: utf-8 -*-
# Adaptado para Odoo 19
from odoo import models, fields


class AccountMove(models.Model):
    _inherit = 'account.move'

    x_studio_bultos = fields.Integer(string='Bultos', default=0)