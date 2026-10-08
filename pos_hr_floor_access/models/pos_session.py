# -*- coding: utf-8 -*-
from odoo import models


class PosSession(models.Model):
    _inherit = "pos.session"

    def _loader_params_hr_employee(self):
        result = super()._loader_params_hr_employee()
        if "search_params" in result and "fields" in result["search_params"]:
            fields_to_add = ["pos_floor_ids", "pos_all_floors_access", "pos_floor_access_type"]
            for field in fields_to_add:
                if field not in result["search_params"]["fields"]:
                    result["search_params"]["fields"].append(field)
        return result

    def _loader_params_restaurant_floor(self):
        result = super()._loader_params_restaurant_floor()
        if "search_params" in result and "fields" in result["search_params"]:
            if "employee_ids" not in result["search_params"]["fields"]:
                result["search_params"]["fields"].append("employee_ids")
        return result

    def _loader_params_pos_config(self):
        result = super()._loader_params_pos_config()
        if "search_params" in result and "fields" in result["search_params"]:
            if "restrict_floors_by_employee" not in result["search_params"]["fields"]:
                result["search_params"]["fields"].append("restrict_floors_by_employee")
        return result

    def _get_pos_ui_hr_employee(self, params):
        employees = super()._get_pos_ui_hr_employee(params)
        return employees

    def _get_pos_ui_restaurant_floor(self, params):
        floors = super()._get_pos_ui_restaurant_floor(params)
        return floors
