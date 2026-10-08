# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.http import request


class IrUiMenu(models.Model):
    _inherit = "ir.ui.menu"

    @api.model
    def _filter_visible_menus(self):
        """Hide menu which is selected inside User management only for the selected users"""
        menus = super(IrUiMenu, self)._filter_visible_menus()
        current_user = self.env.user
        company_ids = (
            request.httprequest.cookies.get("cids")
            if request and hasattr(request, 'httprequest') and request.httprequest.cookies.get("cids")
            else False
        )
        if company_ids:
            cids_str = request.httprequest.cookies.get("cids", "")
            cids_str = cids_str.replace("%2C", ",").replace("-", ",")
            lst = [int(x.strip()) for x in cids_str.split(",") if x.strip().isdigit()]
            access_hide_menu_ids = (
                self.env["user.management"]
                .sudo()
                .search(
                    [
                        ("access_user_ids", "in", current_user.ids),
                        ("active", "=", True),
                        ("access_company_ids", "in", lst),
                    ]
                )
                .mapped("access_hide_menu_ids")
            )
        else:
            access_hide_menu_ids = (
                self.env["user.management"]
                .sudo()
                .search(
                    [("access_user_ids", "in", current_user.ids),
                     ("active", "=", True)]
                )
                .mapped("access_hide_menu_ids")
            )
        return menus - access_hide_menu_ids
