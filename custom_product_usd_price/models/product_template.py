from odoo import models, fields, api

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    list_price_usd = fields.Float(string="Precio de venta USD")

    list_price_usd_with_tax = fields.Float(
        string="Precio USD c/IVA",
        compute="_compute_list_price_usd_with_tax",
        store=True,
    )

    @api.depends('list_price_usd')
    def _compute_list_price_usd_with_tax(self):
        for rec in self:
            tax_total_percent = 0.0
            for tax in rec.taxes_id:
                if tax.amount_type == 'percent':
                    tax_total_percent += tax.amount
            rec.list_price_usd_with_tax = rec.list_price_usd * (1 + tax_total_percent / 100)

    @api.onchange('list_price_usd')
    def _onchange_list_price_usd(self):
        for rec in self:
            # Actualiza el precio de venta (list_price) con el valor ingresado en USD.
            # No se realiza conversión a otra moneda para evitar afectar otros módulos o lógicas externas.
            rec.list_price = rec.list_price_usd
