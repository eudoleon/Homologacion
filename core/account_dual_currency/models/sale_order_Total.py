from odoo import models, fields, api

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    currency_id_ref = fields.Many2one(
        'res.currency', 
        string="Moneda Referencia", 
        default=lambda self: self.env.ref('base.USD')
    )

    amount_ref_untaxed = fields.Monetary(string="Subtotal (USD)", compute='_compute_ref_totals', currency_field='currency_id_ref', store=True)
    amount_ref_tax = fields.Monetary(string="Impuestos (USD)", compute='_compute_ref_totals', currency_field='currency_id_ref', store=True)
    amount_ref_total = fields.Monetary(string="Total (USD)", compute='_compute_ref_totals', currency_field='currency_id_ref', store=True)

    @api.depends('order_line.ref', 'order_line.tax_ids')
    def _compute_ref_totals(self):
        for order in self:
            untaxed = 0.0
            tax_amount = 0.0
            for line in order.order_line:
                val_ref = line.ref or 0.0
                untaxed += val_ref
                
                if line.tax_ids:
                    taxes = line.tax_ids.compute_all(
                        val_ref, 
                        quantity=1.0, 
                        currency=order.currency_id_ref, 
                        product=line.product_id, 
                        partner=order.partner_id
                    )
                    tax_amount += sum(t.get('amount', 0.0) for t in taxes.get('taxes', []))
            
            order.amount_ref_untaxed = untaxed
            order.amount_ref_tax = tax_amount
            order.amount_ref_total = untaxed + tax_amount

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # Declaramos el campo para que el ORM lo cargue en el objeto 'line'
    ref = fields.Float(string="Ref Subtotal")