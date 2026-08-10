# coding: utf-8

from odoo import fields, api, models


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    facturad_journal = fields.Boolean(string='Activar Facturacion Digital', help='Cuando sea Verdadero, la facturacion digital estará disponible', default= False)
    
    visible_facturad = fields.Boolean(string='Visible para Facturacion Digital', store=True, readonly=False)
    facturaciond = fields.Boolean(string='Activar Facturacion Digital', store=True, readonly=False)
    
