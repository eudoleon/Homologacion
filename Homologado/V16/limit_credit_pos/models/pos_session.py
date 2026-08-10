# -*- coding: utf-8 -*-
from odoo import models

class PosSession(models.Model):
    _inherit = 'pos.session'

    def _loader_params_res_partner(self):
        result = super()._loader_params_res_partner()
        search_params = result.get('search_params') or {}
        result['search_params'] = search_params
        fields = search_params.setdefault('fields', [])
        for field_name in ['activate_credit', 'is_credit_restricted', 'total_invoiced_amount', 'credit_limit_custom']:
            if field_name not in fields:
                fields.append(field_name)
        return result
