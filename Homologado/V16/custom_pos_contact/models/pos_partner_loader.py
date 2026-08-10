from odoo import models

class PosSession(models.Model):
    _inherit = 'pos.session'

    def _loader_params_res_partner(self):
        result = super()._loader_params_res_partner()
        if 'identification_id' not in result['search_params']['fields']:
            result['search_params']['fields'].append('identification_id')
        return result
