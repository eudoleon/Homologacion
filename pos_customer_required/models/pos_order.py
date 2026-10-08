# Copyright 2004 apertoso NV - Jos DE GRAEVE <Jos.DeGraeve@apertoso.be>
# Copyright 2016 La Louve - Sylvain LE GAL <https://twitter.com/legalsylvain>
# Copyright 2019 Druidoo - (https://www.druidoo.io)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import _, api, exceptions, fields, models


class PosOrder(models.Model):
    _inherit = "pos.order"

    require_customer = fields.Selection(
        related="session_id.config_id.require_customer",
    )

    @api.constrains("partner_id", "session_id", "state")
    def _check_partner(self):
        for rec in self:
            # 1. Órdenes en borrador (draft) no requieren cliente obligatorio;
            # el cajero lo solicitará y asignará al momento de facturar en caja.
            if rec.state == 'draft':
                continue

            # 2. Órdenes de quiosco de autoservicio (self-ordering)
            cfg = rec.session_id.config_id
            if cfg and getattr(cfg, 'self_ordering_mode', 'nothing') != 'nothing':
                continue

            # 3. En caja, si require_customer está activo y no tiene partner
            if rec.require_customer != "no" and not rec.partner_id:
                raise exceptions.ValidationError(
                    _("Customer is required for this order and is missing.")
                )
