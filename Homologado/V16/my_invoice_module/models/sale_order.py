from odoo import models, fields, api
from odoo.exceptions import UserError  # Importar UserError

class SaleOrderInherit(models.Model):
    _inherit = 'sale.order'

    # Sobrescribimos el método action_cancel
    def action_cancel(self):
        for order in self:
            # Verificar si alguna línea del pedido ha sido facturada
            if any(line.qty_invoiced > 0 for line in order.order_line):
                raise UserError("No se puede cancelar un pedido que ya ha sido facturado.")

            # Verificar si el pedido ha sido transferido al POS (pos_order_count > 0)
            if order.pos_order_count > 0:
                raise UserError("No se puede cancelar un pedido que ya ha sido transferido al Punto de Venta.")
        
        return super(SaleOrderInherit, self).action_cancel()
