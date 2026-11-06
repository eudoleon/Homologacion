from odoo import models, fields, api
from odoo.fields import Date

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    currency_id_ref = fields.Many2one(
        'res.currency', 
        string="Moneda Referencia", 
        default=lambda self: self.env.ref('base.USD')
    )

    tasa_bcv = fields.Float(
            string="Tasa BCV", 
            digits=(12, 4), 
            compute='_compute_tasa_bcv', 
            store=True,
            help="Tasa de cambio aplicada según la fecha de la orden."
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
                    # En compras el campo es 'tax_ids' (singular con ID)
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

    @api.depends('date_order', 'currency_id', 'company_id')
    def _compute_tasa_bcv(self):
        currency_usd = self.env.ref('base.USD', raise_if_not_found=False)
        for order in self:
            if order.date_order and currency_usd:
                target_curr = order.currency_id if order.currency_id.name == 'VEF' else order.company_id.currency_id
                order.tasa_bcv = self.env['res.currency']._get_conversion_rate(
                    from_currency=currency_usd,
                    to_currency=target_curr,
                    company=order.company_id or self.env.company,
                    date=order.date_order,
                )
            else:
                order.tasa_bcv = 1.0

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    # Declaramos 'ref' para Purchase Order Line
    ref = fields.Float(string="REF Subtotal")