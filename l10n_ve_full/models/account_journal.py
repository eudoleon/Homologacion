# coding: utf-8

from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    type = fields.Selection(
        selection_add=[
            ('sale_debit', 'Débito de venta'),
            ('purchase_debit', 'Débito de compra'),
        ],
        ondelete={
            'sale_debit': 'cascade',
            'purchase_debit': 'cascade',
        },
    )

    default_iva_account = fields.Many2one('account.account', string='Cuenta retención IVA')
    default_islr_account = fields.Many2one('account.account', string='Cuenta retención ISLR')
    is_iva_journal = fields.Boolean(default=False)
    is_islr_journal = fields.Boolean(default=False)
    default_municipal_account = fields.Many2one('account.account', string='Cuenta retención Municipal')
    is_municipal_journal = fields.Boolean(default=False)
    eliminar_impuestos = fields.Boolean(default=False, string="Eliminar impuestos")
    permitir_itf = fields.Boolean(default=False, string="Permitir ITF")

