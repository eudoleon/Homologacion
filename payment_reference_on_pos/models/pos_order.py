from odoo import models, fields, api, _

class PoSPayment(models.Model):
    _inherit = "pos.payment"

    payment_reference = fields.Char(
        string='Payment Reference',
        readonly=True,
        copy=False,
        help="The document that was utilized to issue this payment. For example, check number, file name, and so on."
    )

    def _create_payment_moves(self, is_reverse=False):
        moves = super()._create_payment_moves(is_reverse=is_reverse)
        for payment in self:
            if payment.payment_reference and payment.account_move_id:
                payment.account_move_id.line_ids.write({'payment_reference': payment.payment_reference})
        return moves

class PosSession(models.Model):
    _inherit = 'pos.session'

    def _loader_params_pos_payment(self):
        result = super()._loader_params_pos_payment()
        result['search_params']['fields'].append('payment_reference')
        return result

class PosOrder(models.Model):
    _inherit = "pos.order"

    @api.model
    def _payment_fields(self, order, ui_paymentline):
        result = super(PosOrder, self)._payment_fields(order, ui_paymentline)
        if 'payment_reference' in ui_paymentline:
            result['payment_reference'] = ui_paymentline['payment_reference']
        return result
