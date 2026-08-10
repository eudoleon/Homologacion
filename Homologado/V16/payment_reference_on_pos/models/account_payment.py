from odoo import models, fields, api, _

class AccountPayment(models.Model):
    _inherit = "account.payment"

    payment_reference = fields.Char(string='Payment Reference', tracking=True)