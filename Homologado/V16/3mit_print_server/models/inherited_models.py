# -*- coding: utf-8 -*-
from datetime import datetime

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class PosSession(models.Model):
    _inherit = "pos.session"

    def _loader_params_res_partner(self):
        result = super()._loader_params_res_partner()
        result['search_params']['fields'].extend(['company_type'])
        return result