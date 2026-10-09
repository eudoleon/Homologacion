# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, tools, http, exceptions
from odoo.http import request
from odoo.exceptions import AccessError
from odoo.addons.web.controllers.dataset import DataSet


class accessDatasetInherit(DataSet):

    @http.route(['/web/dataset/call_kw', '/web/dataset/call_kw/<path:path>'], type='json', auth="user")
    def call_kw(self, model, method, args, kwargs, path=None):
        uid = (request.env.user.id if request and hasattr(request, 'env') and request.env.user else (request.session.uid if request and hasattr(request, 'session') else False))
        # If system is readonly then restrict rpc calls
        if uid and method in ['create', 'write', 'unlink'] and request.env['user.management'].sudo().search(
                [('access_readonly', '=', True),
                 ('access_user_ids', 'in', [uid]),
                 ('active', '=', True)], limit=1):
            raise AccessError(_("No tienes permisos para crear, editar o eliminar registros en este momento."))

        profile_management = request.env['model.access'].sudo().search(
            [('access_model_id.model', '=', model),
             ('access_user_manager_id.access_user_ids', 'in', [uid]),
             ('access_user_manager_id.active', '=', True)], limit=1) if uid else False

        if profile_management:
            if method == 'create' and profile_management.access_hide_create:
                raise AccessError(_("No tienes permisos para crear registros en este modelo."))
            elif method == 'write' and profile_management.access_hide_edit:
                raise AccessError(_("No tienes permisos para editar registros en este modelo."))
            elif method == 'unlink' and profile_management.access_hide_delete:
                raise AccessError(_("No tienes permisos para eliminar registros en este modelo."))
            
        return super(accessDatasetInherit, self).call_kw(model, method, args, kwargs, path=path)


class accessRemoveAction(models.Model):
    _name = 'model.access'
    _description = 'Remove Action from model'

    access_model_id = fields.Many2one('ir.model', string='Model', domain="[('id', 'in', access_profile_domain_model)]")
    access_server_action_ids = fields.Many2many('report.action.data', 'server_action_data_rel_ah',
                                            'action_action_id', 'server_action_id', 'Hide Actions',
                                            domain="[('access_action_id.binding_model_id','=',access_model_id),('access_action_id.type','!=','ir.actions.report')]")
    access_report_action_ids = fields.Many2many('report.action.data', 'remove_action_report_action_data_rel_ah',
                                            'action_action_id', 'report_action_id', 'Hide Reports',
                                            domain="[('access_action_id.binding_model_id','=',access_model_id),('access_action_id.type','=','ir.actions.report')]")

    access_model_readonly = fields.Boolean('Solo Lectura')
    access_hide_create = fields.Boolean(string='Ocultar Crear')
    access_hide_edit = fields.Boolean(string='Ocultar Editar')
    access_hide_delete = fields.Boolean(string='Ocultar Eliminar')
    access_hide_archive_unarchive = fields.Boolean(string='Ocultar Archivar/Desarchivar')
    access_hide_duplicate = fields.Boolean(string='Ocultar Duplicar')
    access_hide_export = fields.Boolean(string='Ocultar Exportar')
    access_user_manager_id = fields.Many2one('user.management', string='Administrar ID')
    access_profile_domain_model = fields.Many2many('ir.model', related='access_user_manager_id.access_profile_domain_model')


class accessRemoveActionData(models.Model):
    _name = 'report.action.data'
    _description = "Store Action Button Data"

    name = fields.Char(string='Nombre')
    access_action_id = fields.Many2one('ir.actions.actions', string='Acción')
