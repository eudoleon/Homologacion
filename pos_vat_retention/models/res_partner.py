from odoo import models, fields

class ResPartner(models.Model):
    _inherit = 'res.partner'

    vat_retention_rate = fields.Float(string='Porcentaje de Retención IVA (%)')
