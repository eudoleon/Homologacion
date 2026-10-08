from odoo import api, fields, models

class Impresoraadaptacion(models.Model):
    _inherit = 'pos.order'
    # estado_impreso = fields.Boolean('Estado_impresion', default=True)
    rate_order = fields.Float(string="Tasa")

    # def refund(self):
    #     """Create a copy of order  for refund order"""
    #     refund_orders = self.env['pos.order']
    #     for order in self:
    #         # When a refund is performed, we are creating it in a session having the same config as the original
    #         # order. It can be the same session, or if it has been closed the new one that has been opened.
    #         current_session = order.session_id.config_id.current_session_id
    #         if not current_session:
    #             raise UserError(_('To return product(s), you need to open a session in the POS %s') % order.session_id.config_id.display_name)
    #         refund_order = order.copy({
    #             'name': order.name + _(' REFUND'),
    #             'session_id': current_session.id,
    #             'date_order': fields.Datetime.now(),
    #             'pos_reference': order.pos_reference,
    #             'lines': False,
    #             'amount_tax': -order.amount_tax,
    #             'amount_total': -order.amount_total,
    #             'amount_paid': 0,
    #             'estado_impreso': True,
    #         })
    #         for line in order.lines:
    #             PosOrderLineLot = self.env['pos.pack.operation.lot']
    #             for pack_lot in line.pack_lot_ids:
    #                 PosOrderLineLot += pack_lot.copy()
    #             line.copy({
    #                 'name': line.name + _(' REFUND'),
    #                 'qty': -line.qty,
    #                 'order_id': refund_order.id,
    #                 'price_subtotal': -line.price_subtotal,
    #                 'price_subtotal_incl': -line.price_subtotal_incl,
    #                 'pack_lot_ids': PosOrderLineLot,
    #                 })
    #         refund_orders |= refund_order
    #
    #     return {
    #         'name': _('Return Products'),
    #         'view_mode': 'form',
    #         'res_model': 'pos.order',
    #         'res_id': refund_orders.ids[0],
    #         'view_id': False,
    #         'context': self.env.context,
    #         'type': 'ir.actions.act_window',
    #         'target': 'current',
    #     }
    #
    # def reimprimir_orden(self):
    #     self.estado_impreso = True

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)

        # Prioriza monedas VE comunes para mantener compatibilidad historica.
        currency = self.env['res.currency'].search([
            ('name', 'in', ['VED', 'VES', 'VEF'])
        ], limit=1)

        for order in orders:
            if order.rate_order:
                continue
            
            # Obtener la tasa del POS Config (mai_pos_dual_currency) si existe
            config = order.session_id.config_id
            if config and hasattr(config, 'show_currency_rate') and config.show_currency_rate:
                order.rate_order = 1 / config.show_currency_rate
            elif currency:
                order.rate_order = currency.rate
            else:
                order.rate_order = order.company_id.currency_id.rate

        return orders
