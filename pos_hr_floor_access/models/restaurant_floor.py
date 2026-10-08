# -*- coding: utf-8 -*-
from odoo import fields, models


class RestaurantFloor(models.Model):
    _inherit = "restaurant.floor"

    employee_ids = fields.Many2Many(
        "hr.employee",
        "hr_employee_restaurant_floor_rel",
        "floor_id",
        "employee_id",
        string="Empleados Autorizados",
        help="Empleados que tienen permiso para visualizar y atender mesas en este piso.",
    )
