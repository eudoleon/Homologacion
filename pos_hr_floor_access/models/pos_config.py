# -*- coding: utf-8 -*-
from odoo import fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    restrict_floors_by_employee = fields.Boolean(
        string="Restringir Pisos por Empleado",
        default=True,
        help="Si está activo, en el Punto de Venta solo se mostrarán los pisos autorizados para el empleado activo.",
    )


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pos_restrict_floors_by_employee = fields.Boolean(
        related="pos_config_id.restrict_floors_by_employee",
        readonly=False,
        string="Restricción de Pisos por Empleado",
    )
