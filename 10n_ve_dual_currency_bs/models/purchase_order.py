# -*- coding: utf-8 -*-
###############################################################################
# Author: Jesus Pozzo / Andres Castillo
# Copyleft: 2023-Present.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).
#
# Migrado a Odoo v19:
# - Eliminado import de osv (no existe en v19)
# - Eliminado import de Warning (usar UserError)
# - Eliminado digits= de campo Many2one (no válido)
# - Eliminado states= de campo tax_day (deprecated en v17+, eliminado en v19)
# - Corregido bug: amount_residual_bs no se asignaba en _compute_amounts_bs
###############################################################################
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
import logging
import requests
from decimal import Decimal, ROUND_DOWN

_logger = logging.getLogger(__name__)


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    validate_Check_orderline = fields.Boolean(
        string='Validar si tiene lineas',
        compute='_compute_validate_order_line'
    )

    amount_untaxed_bs = fields.Float(
        string="Base Imponible Bs.",
        store=True,
        compute='_compute_amounts_bs',
        tracking=5,
        digits=(16, 4)
    )
    amount_tax_bs = fields.Float(
        string="Impuesto Bs",
        store=True,
        compute='_compute_amounts_bs',
        digits=(16, 4)
    )
    amount_total_bs = fields.Float(
        string="Total BS",
        store=True,
        compute='_compute_amounts_bs',
        tracking=4,
        digits=(16, 4)
    )
    # Many2one no acepta digits=, se eliminó ese parámetro
    currency_ref_id = fields.Many2one(
        'res.currency',
        string='Moneda Bs.',
        default=lambda self: self.env.ref('base.VEF')
    )
    amount_residual_bs = fields.Monetary(
        string='Bs. Monto Deudor',
        compute='_compute_amounts_bs',
        store=True,
        digits=(16, 4),
        currency_field='currency_ref_id'
    )

    @api.model
    def getRate(self):
        res_currency_id = self.env['res.currency'].sudo().search(
            [('name', '=', 'VEF'), ('active', '=', True)], limit=1
        )
        if res_currency_id and res_currency_id.rate_ids:
            rate_day = res_currency_id.rate_ids.sorted('name', reverse=True)[:1]
            return round(rate_day.company_rate, 2)
        else:
            return 1.00

    # En v19, states= en campos fue eliminado. Usar readonly en la vista XML.
    tax_day = fields.Float(
        string='Tasa del día',
        default=getRate,
        digits='Product Price',
    )

    def calcular_totales_por_impuesto(self):
        impuestos_totales = {}
        for order in self:
            for line in order.order_line:
                subtoal_amount_bs = Decimal(str(line.subtoal_amount_bs))
                for impuesto in line.taxes_id:
                    if impuesto.amount != 0:
                        impuestod = Decimal(str(impuesto.amount))
                        impuesto_nombre = impuesto.name
                        impuesto_valor = subtoal_amount_bs * impuestod / 100
                        impuesto_valor = impuesto_valor.quantize(Decimal('1.00'), rounding=ROUND_DOWN)
                        if impuesto_nombre in impuestos_totales:
                            impuestos_totales[impuesto_nombre] += impuesto_valor
                        else:
                            impuestos_totales[impuesto_nombre] = impuesto_valor
        return impuestos_totales

    @api.depends('order_line')
    def _compute_validate_order_line(self):
        for rec in self:
            # Si no tiene líneas, habilita para editar la tasa
            rec.validate_Check_orderline = not bool(rec.order_line)

    def calcular_totales_por_impuesto_USD(self):
        impuestos_totales = {}
        for order in self:
            for line in order.order_line:
                for impuesto in line.taxes_id:
                    if impuesto.amount != 0:
                        impuesto_nombre = impuesto.name
                        impuesto_valor = (line.price_subtotal * impuesto.amount) / 100
                        if impuesto_nombre in impuestos_totales:
                            impuestos_totales[impuesto_nombre] += impuesto_valor
                        else:
                            impuestos_totales[impuesto_nombre] = impuesto_valor
        return impuestos_totales

    @api.depends('amount_untaxed', 'amount_tax', 'amount_total')
    def _compute_amounts_bs(self):
        for order in self:
            if order.tax_day > 0:
                tax_day = Decimal(str(order.tax_day))

                total_amount_untaxed = sum(line.price_subtotal for line in order.order_line)
                str_total_amount_untaxed = (
                    Decimal(str(total_amount_untaxed)) * tax_day
                ).quantize(Decimal('1.0000'))

                total_impuestoUSD = sum(
                    round(valor, 6)
                    for valor in self.calcular_totales_por_impuesto_USD().values()
                )
                str_total_impuestoUSD = (
                    Decimal(str(total_impuestoUSD)) * tax_day
                ).quantize(Decimal('1.0000'))

                TOTAL = (
                    Decimal(str(total_amount_untaxed)) * tax_day
                    + Decimal(str(total_impuestoUSD)) * tax_day
                ).quantize(Decimal('1.0000'), rounding=ROUND_DOWN)

                order.amount_untaxed_bs = str_total_amount_untaxed
                order.amount_tax_bs = str_total_impuestoUSD
                order.amount_total_bs = TOTAL
                # Bug corregido: se asigna amount_residual_bs (antes no se asignaba)
                order.amount_residual_bs = 0.0000
            else:
                order.amount_untaxed_bs = 0.0000
                order.amount_tax_bs = 0.0000
                order.amount_total_bs = 0.0000
                order.amount_residual_bs = 0.0000

    def _compute_amounts_line_bs(self):
        for line in self.order_line:
            line._compute_price_unit_bs()

    def updateRateDate(self):
        self._compute_amounts_bs()
        self._compute_amounts_line_bs()


class InheritPurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    currency_ref_id = fields.Many2one(
        'res.currency',
        string='Moneda Bolivar',
        default=lambda self: self.env.ref('base.VEF')
    )
    price_unit_bs = fields.Monetary(
        string="Precio Bs.",
        currency_field='currency_ref_id',
        compute='_compute_price_unit_bs',
        digits='Product Price',
        store=True,
        readonly=False,
        required=True,
        precompute=True
    )
    subtoal_amount_bs = fields.Monetary(
        string="Subtotal Bs.",
        currency_field='currency_ref_id',
        store=True,
        compute='_compute_amounts_bs',
        tracking=4
    )

    @api.depends('price_subtotal')
    def _compute_amounts_bs(self):
        for line in self:
            price_subtotal = Decimal(str(line.price_subtotal))
            tax_day = Decimal(str(line.order_id.tax_day))

            if line.price_subtotal and line.order_id.tax_day:
                subtoal_amount_bs = price_subtotal * tax_day
                subtoal_amount_bs = subtoal_amount_bs.quantize(Decimal('1.00'), rounding=ROUND_DOWN)
                line.subtoal_amount_bs = subtoal_amount_bs
            else:
                line.subtoal_amount_bs = 0.00

    @api.depends('product_id', 'price_unit')
    def _compute_price_unit_bs(self):
        for line in self:
            price_subtotal = Decimal(str(line.price_unit))
            tax_day = Decimal(str(line.order_id.tax_day))

            if line.price_unit and line.order_id.tax_day:
                price_unit_bs = price_subtotal * tax_day
                price_unit_bs = price_unit_bs.quantize(Decimal('1.00'), rounding=ROUND_DOWN)
                line.price_unit_bs = price_unit_bs
            elif line.product_id:
                line.price_unit_bs = line.product_id.price_bs
            else:
                line.price_unit_bs = 0.00