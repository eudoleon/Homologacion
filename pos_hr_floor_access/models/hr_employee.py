# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    pos_floor_access_type = fields.Selection(
        [
            ("all", "1. Acceso a Todos los Pisos (Ver todos los pisos creados automáticamente)"),
            ("specific", "2. Seleccionar Pisos Específicos (Asignar manualmente los pisos autorizados)"),
        ],
        string="Tipo de Acceso a Pisos",
        default="specific",
        help="Seleccione si el empleado puede ver todos los pisos o solo los seleccionados.",
    )
    pos_all_floors_access = fields.Boolean(
        string="Acceso a Todos los Pisos",
        default=False,
        compute="_compute_pos_all_floors_access",
        inverse="_inverse_pos_all_floors_access",
        store=True,
        help="Si está marcado, este empleado podrá ver y acceder a todos los pisos del restaurante en el Punto de Venta.",
    )
    pos_floor_ids = fields.Many2Many(
        "restaurant.floor",
        "hr_employee_restaurant_floor_rel",
        "employee_id",
        "floor_id",
        string="Pisos Permitidos en TPV",
        help="Seleccione los pisos creados a los que este empleado tendrá acceso en el Punto de Venta.",
    )

    @api.depends("pos_floor_access_type")
    def _compute_pos_all_floors_access(self):
        for employee in self:
            employee.pos_all_floors_access = (employee.pos_floor_access_type == "all")

    def _inverse_pos_all_floors_access(self):
        for employee in self:
            if employee.pos_all_floors_access:
                employee.pos_floor_access_type = "all"
            else:
                employee.pos_floor_access_type = "specific"

    @api.onchange("pos_floor_access_type")
    def _onchange_pos_floor_access_type(self):
        if self.pos_floor_access_type == "all":
            self.pos_all_floors_access = True
        else:
            self.pos_all_floors_access = False

    @api.onchange("pos_all_floors_access")
    def _onchange_pos_all_floors_access(self):
        if self.pos_all_floors_access:
            self.pos_floor_access_type = "all"
        else:
            self.pos_floor_access_type = "specific"


class HrEmployeePublic(models.Model):
    _inherit = "hr.employee.public"

    pos_floor_access_type = fields.Selection(
        [
            ("all", "1. Acceso a Todos los Pisos"),
            ("specific", "2. Seleccionar Pisos Específicos"),
        ],
        string="Tipo de Acceso a Pisos",
        readonly=True,
    )
    pos_all_floors_access = fields.Boolean(
        string="Acceso a Todos los Pisos",
        readonly=True,
    )
    pos_floor_ids = fields.Many2Many(
        "restaurant.floor",
        "hr_employee_restaurant_floor_rel",
        "employee_id",
        "floor_id",
        string="Pisos Permitidos en TPV",
        readonly=True,
    )

