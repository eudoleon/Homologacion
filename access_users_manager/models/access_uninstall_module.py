# -*- coding: utf-8 -*-

from odoo import models


class accessBaseModuleUninstall(models.TransientModel):
    _inherit = "base.module.uninstall"

    def action_uninstall(self):
        """ Delete group which is created for user profiles and Domain access"""
        groups = self.env['res.groups']
        category_groups = self.env['res.groups']
        modules = self.env['ir.module.module']
        if hasattr(self, 'module_ids') and self.module_ids:
            modules = self.module_ids
        elif hasattr(self, 'module_id') and self.module_id:
            modules = self.module_id

        if 'access_users_manager' in modules.mapped('name'):
            groups = self.env['res.groups'].sudo().search([('custom', '=', True)])
            if 'category_id' in self.env['res.groups']._fields:
                cat_ref = self.env.ref('access_users_manager.ir_module_category_profiles', raise_if_not_found=False)
                if cat_ref:
                    category_groups = self.env['res.groups'].sudo().search(
                        [('category_id', '=', cat_ref.id)])
        res = super(accessBaseModuleUninstall, self).action_uninstall()
        all_groups = groups | category_groups
        if all_groups:
            all_groups.sudo().unlink()
        return res