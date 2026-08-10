from odoo import models, fields, api

class ResPartner(models.Model):
    _inherit = 'res.partner'

    last_sale_order_date = fields.Date(
        string='Última fecha de pedido de venta',
        compute='_compute_last_sale_order_date',
        store=True
    )

    purchase_order_ids = fields.One2many(
        'purchase.order',
        'partner_id',
        string='Pedidos de compra'
    )

    last_purchase_order_date = fields.Date(
        string='Última fecha de pedido de compra',
        compute='_compute_last_purchase_order_date',
        store=True
    )

    @api.depends('sale_order_ids.date_order')
    def _compute_last_sale_order_date(self):
        for partner in self:
            orders = partner.sale_order_ids.filtered(lambda o: o.state not in ['cancel'])
            if orders:
                partner.last_sale_order_date = max(orders.mapped('date_order')).date()
            else:
                partner.last_sale_order_date = False

    @api.depends('purchase_order_ids.date_order')
    def _compute_last_purchase_order_date(self):
        for partner in self:
            orders = partner.purchase_order_ids.filtered(lambda o: o.state not in ['cancel'])
            if orders:
                partner.last_purchase_order_date = max(orders.mapped('date_order')).date()
            else:
                partner.last_purchase_order_date = False
