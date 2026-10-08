# -*- coding: utf-8 -*-
#################################################################################
#
#   Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#   See LICENSE file for full copyright and licensing details.
#   License URL : <https://store.webkul.com/license.html/>
#
#################################################################################
from odoo import api, fields, models
from odoo.exceptions import ValidationError
import logging
_logger = logging.getLogger(__name__)


class POsCustomDiscount(models.Model):
    _name = "pos.custom.discount"
    _description = "Pos Custom Discounts"

    name = fields.Char(string="Nombre", required=1)
    discount_percent = fields.Float(string="Porcentaje de Descuento", required=1)
    description = fields.Text(string="Descripción")
    available_in_pos = fields.Many2many(
        'pos.config', string="Disponible en el Pos")

    @api.constrains('discount_percent')
    def check_validation_discount_percent(self):
        """This is to validate discount percentage"""
        if self.discount_percent <= 0 or self.discount_percent > 100:
            raise ValidationError(
                "El porcentaje de descuento debe estar entre 0 y 100.")


class PosConfig(models.Model):
    _inherit = 'pos.config'

    discount_ids = fields.Many2many('pos.custom.discount')
    allow_custom_discount = fields.Boolean(
        'Permitir personalizar descuento', default=True)
    allow_security_pin = fields.Boolean('Permitir pin de seguridad')


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pos_discount_ids = fields.Many2many(
        related='pos_config_id.discount_ids', readonly=False)
    pos_allow_custom_discount = fields.Boolean(
        related='pos_config_id.allow_custom_discount', readonly=False)
    pos_allow_security_pin = fields.Boolean(
        related='pos_config_id.allow_security_pin', readonly=False)


class PosSession(models.Model):
    _inherit = 'pos.session'

    def _pos_ui_models_to_load(self):
        result = super()._pos_ui_models_to_load()
        new_model_pos_custom_discount = 'pos.custom.discount'
        if new_model_pos_custom_discount not in result:
            result.append(new_model_pos_custom_discount)
        return result

    def _loader_params_pos_custom_discount(self):
        domain_list = [('id', 'in', self.config_id.discount_ids.ids)]
        model_fields = ['name', 'discount_percent',
                        'description', 'available_in_pos']
        return {'search_params': {'domain': domain_list, 'fields': model_fields}}

    def _get_pos_ui_pos_custom_discount(self, params):
        pos_custom_discount = self.env['pos.custom.discount'].search_read(
            **params['search_params'])
        return pos_custom_discount


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'
    custom_discount_reason = fields.Text('Motivo del descuento')

    @api.model
    def _order_line_fields(self, line, session_id=None):
        fields_return = super(
            PosOrderLine, self)._order_line_fields(line, session_id)
        fields_return[2].update(
            {'custom_discount_reason': line[2].get('custom_discount_reason', '')})
        return fields_return
