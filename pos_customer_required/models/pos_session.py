from odoo import models

class PosSession(models.Model):
    _inherit = 'pos.session'

    def _pos_ui_models_to_load(self):
        result = super()._pos_ui_models_to_load()
        if 'pos.config' not in result:
            result.append('pos.config')
        return result

    def _loader_params_pos_config(self):
        result = super()._loader_params_pos_config()
        if 'require_customer' not in result['search_params']['fields']:
            result['search_params']['fields'].append('require_customer')
        return result
