from odoo import fields, models


class PosConfig(models.Model):
    _inherit = 'pos.config'

    required_name = fields.Boolean('Required name', default=True)
    required_vat = fields.Boolean('Required vat / RIF', default=True)
    required_phone = fields.Boolean('Required phone', default=True)
    required_street = fields.Boolean('Required street', default=True)
    required_email = fields.Boolean('Required email', default=True)

    unique_name = fields.Boolean('Unique name')
    unique_vat = fields.Boolean('Unique vat')
    unique_phone = fields.Boolean('Unique phone')
    unique_street = fields.Boolean('Unique street')
    unique_email = fields.Boolean('Unique email')


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    required_name = fields.Boolean('Required name', related='pos_config_id.required_name', readonly=False)
    required_vat = fields.Boolean('Required vat', related='pos_config_id.required_vat', readonly=False)
    required_phone = fields.Boolean('Required phone', related='pos_config_id.required_phone', readonly=False)
    required_street = fields.Boolean('Required street', related='pos_config_id.required_street', readonly=False)
    required_email = fields.Boolean('Required email', related='pos_config_id.required_email', readonly=False)

    unique_name = fields.Boolean('Unique name', related='pos_config_id.unique_name', readonly=False)
    unique_vat = fields.Boolean('Unique vat', related='pos_config_id.unique_vat', readonly=False)
    unique_phone = fields.Boolean('Unique phone', related='pos_config_id.unique_phone', readonly=False)
    unique_street = fields.Boolean('Unique street', related='pos_config_id.unique_street', readonly=False)
    unique_email = fields.Boolean('Unique email', related='pos_config_id.unique_email', readonly=False)
