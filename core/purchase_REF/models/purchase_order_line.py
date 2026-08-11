# -*- coding: utf-8 -*-
# Adaptado para Odoo 19
from odoo import api, fields, models
from odoo.exceptions import ValidationError
from lxml import etree
import logging

_logger = logging.getLogger(__name__)

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    currency_id = fields.Many2one(
        'res.currency', 
        string='Currency',
        required=True, 
        readonly=True
    )

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    ref = fields.Float(
        string='REF Subtotal',
        compute='_compute_ref',
        store=True,
        readonly=True,
        digits=(16, 4)
    )
    
    order_currency_ref_id = fields.Many2one(
        'res.currency',
        string="Moneda REF",
        compute='_compute_ref_currency',
        store=True,
    )

    ref_unit = fields.Float(
        string='REF Unit',
        compute='_compute_ref_unit',
        inverse='_inverse_ref_unit',  # MANTENEMOS el inverse
        store=True,
        digits=(16, 4)
    )

    # ⚠️ ELIMINAMOS la redefinición de price_unit ⚠️
    # Dejamos que Odoo use su campo nativo

    @api.depends('order_id.currency_id', 'order_id.company_id.currency_id')
    def _compute_ref_currency(self):
        usd = self.env.ref('base.USD')
        for line in self:
            order_cur = line.order_id.currency_id
            comp_cur = line.order_id.company_id.currency_id
            if order_cur == usd:
                line.order_currency_ref_id = comp_cur
            elif order_cur == comp_cur:
                line.order_currency_ref_id = usd
            else:
                line.order_currency_ref_id = usd

    def _get_rate_usd_to_vef(self):
        return self.env['res.currency'].search([('name', '=', 'USD')], limit=1).rate

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for line in records:
            tax_field = getattr(line, 'tax_ids', getattr(line, 'taxes_id', getattr(line, 'tax_id', False)))
            if (not line.display_type or line.display_type == 'product') and not tax_field:
                raise ValidationError("Las líneas de compras deben tener al menos un impuesto configurado. Producto/Descripción: %s" % (line.product_id.name or line.name))
        return records

    def write(self, vals):
        res = super().write(vals)
        for line in self:
            tax_field = getattr(line, 'tax_ids', getattr(line, 'taxes_id', getattr(line, 'tax_id', False)))
            if (not line.display_type or line.display_type == 'product') and not tax_field:
                raise ValidationError("Las líneas de compras deben tener al menos un impuesto configurado. Producto/Descripción: %s" % (line.product_id.name or line.name))
        return res

    @api.depends('price_subtotal', 'order_id.currency_id', 'order_id.company_id.currency_id', 'order_id.date_order')
    def _compute_ref(self):
        """Cálculo de REF Subtotal - Adaptado para Odoo 19"""
        usd_currency = self.env.ref('base.USD')
        for line in self:
            line.ref = 0.0
            if not line.price_subtotal:
                continue

            order = line.order_id
            order_currency = order.currency_id
            company_currency = order.company_id.currency_id
            date_order = order.date_order or fields.Date.today()

            # === Odoo 19: Usamos _convert en lugar de _get_conversion_rate ===
            target_currency = line.order_currency_ref_id
            if not target_currency:
                continue
            
            try:
                ref_value = order_currency._convert(
                    line.price_subtotal,
                    target_currency,
                    order.company_id,
                    date_order,
                    round=False
                )
            except Exception:
                ref_value = 0.0
            
            # === Código comentado de Odoo 17 (usa _get_conversion_rate) ===
            # rate_usd_to_vef = usd_currency._get_conversion_rate(
            #     usd_currency,
            #     company_currency,
            #     order.company_id,
            #     date_order
            # )
            # if not rate_usd_to_vef:
            #     continue
            # 
            # if order_currency == usd_currency:
            #     ref_value = line.price_subtotal * rate_usd_to_vef
            # elif order_currency == company_currency:
            #     ref_value = line.price_subtotal / rate_usd_to_vef
            # else:
            #     ref_value = 0.0

            line.ref = line.order_currency_ref_id.round(ref_value)

    @api.depends('price_unit', 'order_id.currency_id', 'order_id.company_id.currency_id', 'order_id.date_order')
    def _compute_ref_unit(self):
        """Cálculo de REF Unit - Adaptado para Odoo 19"""
        usd_currency = self.env.ref('base.USD')
        for line in self:
            line.ref_unit = 0.0
            if not line.price_unit:
                continue

            order = line.order_id
            order_currency = order.currency_id
            company_currency = order.company_id.currency_id
            date_order = order.date_order or fields.Date.today()

            # === Odoo 19: Usamos _convert en lugar de _get_conversion_rate ===
            target_currency = line.order_currency_ref_id
            if not target_currency:
                continue
            
            try:
                refu = order_currency._convert(
                    line.price_unit,
                    target_currency,
                    order.company_id,
                    date_order,
                    round=False
                )
            except Exception:
                refu = 0.0

            # === Código comentado de Odoo 17 (usa _get_conversion_rate) ===
            # rate_usd_to_vef = usd_currency._get_conversion_rate(
            #     usd_currency,
            #     company_currency,
            #     order.company_id,
            #     date_order
            # )
            # if not rate_usd_to_vef:
            #     continue
            # 
            # if order_currency == usd_currency:
            #     refu = line.price_unit * rate_usd_to_vef
            # elif order_currency == company_currency:
            #     refu = line.price_unit / rate_usd_to_vef
            # else:
            #     refu = 0.0

            line.ref_unit = refu

    def _inverse_ref_unit(self):
        """Inverso que se ejecuta solo cuando se edita manualmente ref_unit - Adaptado para Odoo 19"""
        # Verificamos si estamos en un contexto que podría causar problemas
        if self.env.context.get('default_move_type') in ['in_invoice', 'in_refund']:
            _logger.warning("Evitando inverse durante creación de factura")
            return
            
        usd_currency = self.env.ref('base.USD')
        for line in self:
            if not line.ref_unit:
                continue

            order = line.order_id
            order_currency = order.currency_id
            company_currency = order.company_id.currency_id
            date_order = order.date_order or fields.Date.today()

            # === Odoo 19: Usamos _convert en lugar de _get_conversion_rate ===
            target_currency = line.order_currency_ref_id
            if not target_currency:
                continue
            
            try:
                price_unit = target_currency._convert(
                    line.ref_unit,
                    order_currency,
                    order.company_id,
                    date_order,
                    round=False
                )
                new_price_unit = order_currency.round(price_unit)
                if abs(line.price_unit - new_price_unit) > 0.01:
                    line.price_unit = new_price_unit
            except Exception:
                continue

            # === Código comentado de Odoo 17 (usa _get_conversion_rate) ===
            # rate_usd_to_vef = usd_currency._get_conversion_rate(
            #     usd_currency,
            #     company_currency,
            #     order.company_id,
            #     date_order
            # )
            # if not rate_usd_to_vef:
            #     continue
            # 
            # if order_currency == usd_currency:
            #     line.price_unit = line.ref_unit / rate_usd_to_vef
            # elif order_currency == company_currency:
            #     line.price_unit = line.ref_unit * rate_usd_to_vef

    def _prepare_account_move_line(self, move=False):
        """Ajusta price_unit en la factura para mantener USD constantes cuando el PO está en VEF.
        price_unit (en factura VEF) = ref_unit (USD) * tax_today (VEF/USD de la factura)
        Adaptado para Odoo 19
        """
        self.ensure_one()
        vals = super()._prepare_account_move_line(move=move)

        order = self.order_id
        company = order.company_id
        company_currency = company.currency_id  # VEF en tu caso
        usd = self.env.ref('base.USD')

        # Moneda de la factura (si move viene), si no, asumimos moneda del PO
        move_currency = move.currency_id if move else order.currency_id

        # Solo aplicamos cuando PO y factura están en VEF (moneda de la compañía)
        if order.currency_id == company_currency and move_currency == company_currency:
            # 1) Tomar la tasa de la factura: tax_today (preferido)
            #    Si no está, derivar tasa USD->VEF por fecha de la factura
            if getattr(move, 'tax_today', False):
                invoice_rate = move.tax_today
            else:
                inv_date = (move.invoice_date or move.date) if move else fields.Date.context_today(self)
                
                # === Odoo 19: Usamos _convert en lugar de _get_conversion_rate ===
                try:
                    amount_converted = usd._convert(1.0, company_currency, company, inv_date)
                    invoice_rate = amount_converted
                except Exception:
                    invoice_rate = 0.0
                
                # === Código comentado de Odoo 17 (usa _get_conversion_rate) ===
                # invoice_rate = usd._get_conversion_rate(
                #     usd, company_currency, company, inv_date
                # )

            # 2) ref_unit aquí representa el precio en USD (porque PO está en VEF)
            ref_unit_usd = self.ref_unit or 0.0
            if ref_unit_usd and invoice_rate:
                # Redondeamos con la moneda de la factura
                vals['price_unit'] = move_currency.round(ref_unit_usd * invoice_rate)

        # Si la factura está en USD o el PO está en USD, no tocamos (se respetan los USD "tal cual")
        return vals