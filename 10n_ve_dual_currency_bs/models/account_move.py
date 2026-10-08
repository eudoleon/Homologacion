# -*- coding: utf-8 -*-
###############################################################################
# Author: Jesus Pozzo / Andres Castillo
# Copyleft: 2023-Present.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).
#
# Migrado a Odoo v19:
# - Eliminado import de osv (no existe en v19)
# - Eliminado import de Warning (usar UserError)
# - Eliminado atributo states= de campos (deprecated/eliminado en v19)
# - Corregido create() para multi-create pattern de v19 (vals_list)
# - Eliminada definición duplicada de currency_ref_id en InheritMoveLine
# - Corregida dependencia invoice_line_ids.currency_rate
###############################################################################
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
import logging
import requests
from decimal import Decimal, ROUND_DOWN, ROUND_UP, ROUND_HALF_UP

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    amount_untaxed_bs = fields.Monetary(
        string="Base Imponible Bs.",
        store=True,
        compute='_compute_amount_untaxed_bs',
        currency_field='currency_ref_id'
    )
    amount_tax_bs = fields.Monetary(
        string="Impuesto Bs.",
        store=True,
        compute='_compute_amount_tax_bs',
        currency_field='currency_ref_id'
    )
    amount_total_bs = fields.Monetary(
        string="Total Bs.",
        store=True,
        compute='_compute_amount_total_bs',
        currency_field='currency_ref_id'
    )
    amount_residual_bs = fields.Monetary(
        string="Monto Deudor Bs.",
        compute='_compute_amount_residual_bs',
        store=True,
        currency_field='currency_ref_id'
    )

    currency_ref_id = fields.Many2one(
        'res.currency',
        string='Moneda Bolivar',
        default=lambda self: self.env.ref('base.VEF')
    )

    type_report_currency = fields.Selection(
        [
            ('usd', 'Dolares.'),
            ('bs',  'Bolívares'),
            ('usd_bs', 'Dual'),
        ],
        default="usd",
        string="Totales en factura (PDF)"
    )

    price_unit_bs = fields.Monetary(
        string="Bs. Precio",
        currency_field='currency_ref_id',
        digits='Product Price',
        store=True,
        readonly=False,
        required=True,
        precompute=True,
    )

    subtoal_amount_bs = fields.Monetary(
        string="Bs. Subtotal",
        currency_field='currency_ref_id',
        store=True,
        compute='_compute_amounts_bs',
        tracking=4
    )

    related_currency_name = fields.Char(
        string='moneda del documento',
        related='currency_id.name',
        readonly=True,
        store=True,
        precompute=True
    )

    display_tax_currency = fields.Boolean(
        string='Mostrar Tasa del día (PDF)',
        default=True,
    )

    @api.model
    def getRate(self):
        res_currency_id = self.env['res.currency'].sudo().search(
            [('name', '=', 'VEF'), ('active', '=', True)], limit=1
        )
        if res_currency_id and res_currency_id.rate_ids:
            rate_day = res_currency_id.rate_ids.sorted('name', reverse=True)[:1]
            tx = Decimal(str(rate_day.company_rate))
            tx_amount = tx.quantize(Decimal('1.00'), rounding=ROUND_DOWN)
            return tx_amount
        else:
            return 4.00

    # En v19, states= en campos fue eliminado. Usar readonly en la vista XML.
    tax_day = fields.Float(
        string='Tasa del día',
        default=getRate,
        digits='Product Price',
    )

    @api.depends('invoice_line_ids.price_subtotal', 'invoice_line_ids.product_id')
    def _compute_amount_untaxed_bs(self):
        for move in self:
            subtotal_amount_bs = Decimal('0.00')
            for line in move.invoice_line_ids:
                if line.product_id.name != "IGTF":  # Excluir IGTF
                    subtotal_amount_bs += Decimal(str(line.subtoal_amount_bs))
            move.amount_untaxed_bs = subtotal_amount_bs

    @api.depends('invoice_line_ids.subtoal_amount_bs', 'invoice_line_ids.tax_ids')
    def _compute_amount_tax_bs(self):
        for move in self:
            taxes_amount_bs = Decimal('0.00')
            for line in move.invoice_line_ids:
                if line.tax_ids:
                    for tax in line.tax_ids:
                        if tax.amount > 0:
                            taxes_amount_bs += (
                                Decimal(str(line.subtoal_amount_bs))
                                * (Decimal(str(tax.amount)) / Decimal('100'))
                            )
            move.amount_tax_bs = taxes_amount_bs

    @api.depends('amount_untaxed_bs', 'amount_tax_bs')
    def _compute_amount_total_bs(self):
        for move in self:
            if move.currency_id.name == "USD" and move.tax_day:
                move.amount_total_bs = move.amount_untaxed_bs + move.amount_tax_bs
            else:
                move.amount_total_bs = move.amount_total

    @api.depends('amount_residual', 'tax_day')
    def _compute_amount_residual_bs(self):
        for move in self:
            if move.currency_id.name == "USD" and move.tax_day:
                rate = Decimal(str(move.tax_day))
                move.amount_residual_bs = (
                    Decimal(str(move.amount_residual)) * rate
                ).quantize(Decimal('1.00'), rounding=ROUND_DOWN)
            else:
                move.amount_residual_bs = move.amount_residual if move.amount_residual else 0.00

    @api.model_create_multi
    def create(self, vals_list):
        """
        Override para heredar la tasa del día desde el pedido de venta/compra
        origen al crear una factura.
        En Odoo v17+, create() recibe una lista de diccionarios (vals_list).
        """
        for vals in vals_list:
            if vals.get('invoice_origin', False):
                order_id = self.env['sale.order'].search([
                    ('name', '=', vals.get('invoice_origin')),
                    ('company_id', '=', self.env.user.company_id.id)
                ])
                if order_id:
                    vals.update({'tax_day': order_id.tax_day})
                else:
                    order_id = self.env['purchase.order'].search([
                        ('name', '=', vals.get('invoice_origin')),
                        ('company_id', '=', self.env.user.company_id.id)
                    ])
                    if order_id:
                        vals.update({'tax_day': order_id.tax_day})

        return super(AccountMove, self).create(vals_list)

    @api.depends(
        'amount_untaxed',
        'amount_tax',
        'amount_total',
        'invoice_line_ids.price_unit_bs',
        'invoice_line_ids.tax_base_amount',
        'invoice_line_ids.price_total',
        'invoice_line_ids.price_subtotal',
        'invoice_payment_term_id',
        'partner_id',
        'currency_id',
    )
    def _compute_amounts_bs(self):
        for move in self:
            if move.currency_id.name == "USD":
                if move.tax_day > 0:
                    move.amount_untaxed_bs = move.amount_untaxed_bs or 0.00
                    move.amount_tax_bs = move.amount_tax_bs or 0.00
                    move.amount_total_bs = move.amount_total_bs or 0.00
                    move.amount_residual_bs = move.amount_residual_bs or 0.00
                else:
                    move.amount_untaxed_bs = 0.00
                    move.amount_tax_bs = 0.00
                    move.amount_total_bs = 0.00
                    move.amount_residual_bs = 0.00
            else:
                move.amount_untaxed_bs = move.amount_untaxed
                move.amount_tax_bs = move.amount_tax
                move.amount_total_bs = move.amount_total
                move.amount_residual_bs = move.amount_residual or 0.00

    def _compute_amounts_line_bs(self):
        for line in self.invoice_line_ids:
            line._compute_price_unit_bs_update(line)

    def updateRateDate(self):
        self._compute_amounts_bs()
        self._compute_amounts_line_bs()

    def calcular_totales_por_impuesto(self):
        impuestos_totales = {}
        for order in self:
            for line in order.invoice_line_ids:
                subtoal_amount_bs = Decimal(str(line.subtoal_amount_bs))
                for impuesto in line.tax_ids:
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

    def calcular_totales_por_impuesto_USD(self):
        impuestos_totales = {}
        for order in self:
            for line in order.invoice_line_ids:
                for impuesto in line.tax_ids:
                    if impuesto.amount != 0:
                        impuesto_nombre = impuesto.name
                        impuesto_valor = (line.price_subtotal * impuesto.amount) / 100
                        if impuesto_nombre in impuestos_totales:
                            impuestos_totales[impuesto_nombre] += impuesto_valor
                        else:
                            impuestos_totales[impuesto_nombre] = impuesto_valor
        return impuestos_totales

    def calcular_base_imponible_por_impuesto_USD(self):
        """Funciona para el libro de ventas y compras"""
        impuestos_totales = {}
        for order in self:
            for line in order.invoice_line_ids:
                for impuesto in line.tax_ids:
                    if impuesto.amount != 0:
                        impuesto_nombre = impuesto.name
                        impuesto_valor = line.price_subtotal
                        if impuesto_nombre in impuestos_totales:
                            impuestos_totales[impuesto_nombre] += impuesto_valor
                        else:
                            impuestos_totales[impuesto_nombre] = impuesto_valor
        return impuestos_totales


class InheritMoveLine(models.Model):
    _inherit = 'account.move.line'

    # NOTA: currency_ref_id definido una sola vez (se eliminó la definición duplicada)
    currency_ref_id = fields.Many2one(
        'res.currency',
        string='Moneda Bolivar',
        default=lambda self: self.env.ref('base.VEF')
    )

    price_unit_bs = fields.Monetary(
        string="Bs. Precio",
        currency_field='currency_ref_id',
        compute='_compute_price_unit_bs',
        digits='Product Price',
        store=True,
        readonly=False,
        required=True,
        precompute=True,
    )

    subtoal_amount_bs = fields.Monetary(
        string="Bs. Subtotal",
        currency_field='currency_ref_id',
        store=True,
        compute='_compute_amounts_bs',
        tracking=4
    )

    related_tax_day = fields.Float(
        string='Tasa del día',
        related='move_id.tax_day',
        readonly=True,
        store=True,
        precompute=True,
        digits=(16, 3)
    )

    related_currency_id = fields.Char(
        string='moneda del documento',
        related='move_id.currency_id.name',
        readonly=True,
        store=True,
        precompute=True
    )

    last_changed_field = fields.Selection(
        selection=[('precio_bs', 'Precio Bs.'), ('precio_usd', 'Precio USD'), ('primero', 'primero')],
        string='Campo Modificado',
        default='primero'
    )

    active_onchange = fields.Boolean(string='')

    @api.depends('price_unit_bs', 'quantity', 'discount', 'move_id.currency_id', 'move_id.tax_day')
    def _compute_amounts_bs(self):
        for line in self:
            if line.move_id.currency_id.name == "USD":
                price_unit_bs = Decimal(str(line.price_unit_bs))
                quantity = Decimal(str(line.quantity))
                discount_percentage = Decimal(str(line.discount)) / Decimal('100')

                if price_unit_bs and quantity:
                    subtotal_bs_bruto = price_unit_bs * quantity
                    discount_amount_bs = subtotal_bs_bruto * discount_percentage
                    subtotal_bs_con_descuento = subtotal_bs_bruto - discount_amount_bs
                    line.subtoal_amount_bs = subtotal_bs_con_descuento.quantize(
                        Decimal('1.00'), rounding=ROUND_DOWN
                    )
                else:
                    line.subtoal_amount_bs = 0.00
            else:
                line.subtoal_amount_bs = line.price_subtotal

    def _compute_price_unit_bs_update(self, line):
        price_subtotal = Decimal(str(line.price_unit))
        tax_day = Decimal(str(line.move_id.tax_day))
        if line.price_unit and line.move_id.tax_day:
            price_unit_bs = price_subtotal * tax_day
            price_unit_bs = price_unit_bs.quantize(Decimal('1.000'), rounding=ROUND_HALF_UP)
            line.price_unit_bs = float(price_unit_bs)
        elif line.product_id:
            line.price_unit_bs = line.product_id.price_bs
        else:
            line.price_unit_bs = 0.00

    @api.depends('product_id', 'price_unit')
    def _compute_price_unit_bs(self):
        for line in self:
            if line.move_id.currency_id.name == "USD":
                if line.price_unit and line.move_id.tax_day:
                    price_unit = Decimal(str(line.price_unit))
                    tax_day = Decimal(str(line.move_id.tax_day))
                    price_unit_bs = price_unit * tax_day
                    price_unit_bs = price_unit_bs.quantize(Decimal('1.000'), rounding=ROUND_HALF_UP)
                    line.price_unit_bs = price_unit_bs
                elif line.product_id:
                    line.price_unit_bs = line.product_id.price_bs
                else:
                    line.price_unit_bs = 0.000
            else:
                line.price_unit_bs = line.price_unit