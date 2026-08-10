from odoo import models, fields, api, _

class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    payment_reference = fields.Char(related="payment_id.payment_reference", store=True)