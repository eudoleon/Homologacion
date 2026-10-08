from odoo import models, fields

class ResCompany(models.Model):
    _inherit = 'res.company'

    vat_retention_rate = fields.Float(string='Porcentaje de Retención IVA (%)')

    account_vat_retention_id = fields.Many2one(
        'account.account', string='Cuenta IVA Retenido',
        help='Cuenta contable para el IVA retenido en POS')
    account_payable_retention_id = fields.Many2one(
        'account.account', string='Cuenta por Pagar Retención',
        help='Cuenta contable para la cuenta por pagar de la retención en POS')