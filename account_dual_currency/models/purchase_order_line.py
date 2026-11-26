from odoo import models, fields, api

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    def _prepare_account_move_line(self, move=False):
        self.ensure_one()
        res = super()._prepare_account_move_line(move=move)

        company = self.order_id.company_id or self.env.company
        currency = self.currency_id or company.currency_id
        date = self.order_id.date_order or fields.Date.today()

        price_unit = self.price_unit
        quantity = self.qty_to_invoice
        amount = price_unit * quantity

        # Conversión si aplica
        if currency and currency != company.currency_id:
            amount_converted = currency._convert(
                amount,
                company.currency_id,
                company,
                date,
            )
        else:
            amount_converted = amount

        res.update({
            'price_unit': price_unit,
            'quantity': quantity,
            'balance': amount_converted,
        })
        return res
