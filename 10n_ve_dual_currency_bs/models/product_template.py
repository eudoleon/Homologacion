# -*- coding: utf-8 -*-
###############################################################################
# Author: Jesús Pozzo
# Copyleft: 2023-Present.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).
#
# Migrado a Odoo v19:
# - Corregida indentación incorrecta en primera línea
# - _get_tax_day_bcv adaptado para manejar multi-record (loop for)
# - Eliminado import innecesario de base64
###############################################################################
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class ProductTemplate(models.Model):
    _inherit = "product.template"

    price_bs = fields.Float(
        string='Precio de venta BS',
        help="Precio calculado con la tasa BCV del día",
        digits='Product Price',
    )
    currency_ref_id = fields.Many2one(
        'res.currency',
        string='Moneda Bs.',
        default=lambda self: self.env.ref('base.VEF')
    )
    tax_day = fields.Float(
        string='Tasa del dia',
        compute="_get_tax_day_bcv"
    )

    def getRate(self):
        _logger.info("=----------------getRate-------------")
        res_currency_id = self.env['res.currency'].search(
            [('name', '=', 'VEF'), ('active', '=', True)], limit=1
        )
        _logger.info(res_currency_id)
        if res_currency_id and res_currency_id.rate_ids:
            rate_day = res_currency_id.rate_ids.sorted('name', reverse=True)[:1]
            return round(rate_day.company_rate, 3)
        return 0.000

    @api.depends()
    def _get_tax_day_bcv(self):
        """Calcula la tasa del día BCV para cada registro del producto."""
        rate_day = self.getRate()
        for record in self:
            record.tax_day = rate_day if rate_day else 0

    def action_update_price(self):
        """Actualiza el precio del producto con la tasa BCV actual."""
        rate_day = self.getRate()
        for product in self:
            if rate_day <= 0:
                raise UserError("No se ha encontrado ninguna tasa en VEF registrada")
            if product.list_price <= 0:
                raise UserError(
                    "El campo 'Precio en dolar' es obligatorio para calcular el precio con la tasa del día."
                )
            product.price_bs = product.list_price * rate_day

    def action_update_all_price(self, dolar_value):
        """
        Actualiza el precio de todos los productos.
        Este método es utilizado en el Cron de actualización automática.
        """
        if dolar_value <= 0:
            _logger.info("No se ha encontrado ninguna tasa en VEF registrada")
            return
        if self.list_price <= 0:
            _logger.info("El campo 'Precio en dolar' es obligatorio para calcular el precio con la tasa del día.")
        self.price_bs = self.list_price * dolar_value

    def show_tax(self):
        """Abre la vista de la moneda VEF para consultar la tasa."""
        res_currency_id = self.env['res.currency'].search([
            ('name', '=', 'VEF'),
            ('active', '=', True)
        ], limit=1)

        if res_currency_id:
            return {
                'type': 'ir.actions.act_window',
                'name': res_currency_id.name,
                'res_model': 'res.currency',
                'res_id': res_currency_id.id,
                'view_mode': 'form',
                'target': 'self',
                'context': {
                    'form_view_initial_mode': 'edit',
                }
            }
        else:
            raise UserError("La moneda con código VEF no existe o no está activa.")