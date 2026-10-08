from odoo import models, fields, api

class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    price_unit_usd = fields.Monetary(
        string="Precio Unitario Ref",
        compute="_compute_usd_amounts", store=True, currency_field='currency_id_usd'
    )
    price_subtotal_usd = fields.Monetary(
        string="Subtotal sin Imp. Ref",
        compute="_compute_usd_amounts", store=True, currency_field='currency_id_usd'
    )
    price_subtotal_incl_usd = fields.Monetary(
        string="Subtotal con Imp. Ref",
        compute="_compute_usd_amounts", store=True, currency_field='currency_id_usd'
    )

    currency_id_usd = fields.Many2one('res.currency', string="Moneda USD", default=lambda self: self.env.ref('base.USD'), store=False)

    @api.depends('price_unit', 'qty', 'order_id.tasa_usd', 'tax_ids')
    def _compute_usd_amounts(self):
        for line in self:
            tasa = line.order_id.tasa_usd or 1.0
            line.price_unit_usd = line.price_unit / tasa if tasa else 0.0
            line.price_subtotal_usd = line.price_subtotal / tasa if tasa else 0.0
            line.price_subtotal_incl_usd = line.price_subtotal_incl / tasa if tasa else 0.0
