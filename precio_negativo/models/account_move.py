from odoo import models, _
from odoo.exceptions import ValidationError


class AccountMove(models.Model):
    _inherit = 'account.move'

    def action_post(self):
        # Odoo 19: se mantiene la validación en el momento de publicar.
        for move in self:
            if move.move_type not in ['out_invoice', 'out_refund']:
                continue

            if not move.invoice_line_ids:
                raise ValidationError(_("No se puede confirmar una factura sin líneas."))

            for line in move.invoice_line_ids:
                if not line.product_id:
                    raise ValidationError(_("Todas las líneas deben tener un producto asignado para confirmar la factura."))
                if line.quantity is None or line.quantity <= 0:
                    raise ValidationError(_("La cantidad en todas las líneas debe ser mayor a cero."))
                if line.price_unit is None or line.price_unit <= 0:
                    raise ValidationError(_("El precio unitario en todas las líneas debe ser mayor a cero."))

        return super().action_post()
