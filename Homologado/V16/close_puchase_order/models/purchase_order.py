from odoo import api, fields, models
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    def action_mark_fully_invoiced(self):
        """Marca el/los pedidos cambiando `invoice_status` de 'to invoice' a 'invoiced'.

        - No actúa sobre pedidos cancelados.
        - Solo cambia pedidos cuyo `invoice_status` sea 'to invoice'.
        - Añade un mensaje en el chatter indicando la acción y el usuario.
        """
        for order in self:
            if order.state == "cancel":
                raise UserError("No se puede marcar un pedido cancelado como facturado.")
            # Sólo cambiar si está pendiente de factura
            if order.invoice_status != "to invoice":
                # no hacer nada si ya está facturado o no aplicable
                continue
            try:
                order.write({"invoice_status": "invoiced"})
            except Exception as e:
                # Si no se puede escribir, informar claramente
                raise UserError(
                    "No fue posible actualizar el estado de factura (invoice_status): %s" % e
                )
            # Registrar en el chatter
            order.message_post(
                body=(
                    "El estado de factura se marcó como 'invoiced' manualmente por %s."
                    % (self.env.user.name)
                ),
                subtype_xmlid="mail.mt_note",
            )
        return True
