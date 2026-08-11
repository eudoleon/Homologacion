# -*- coding: utf-8 -*-
# Adaptado para Odoo 19
from odoo import api, fields, models
from odoo.exceptions import ValidationError
from lxml import etree

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.model
    def get_view(self, view_id=None, view_type='form', **kwargs):
        res = super().get_view(view_id=view_id, view_type=view_type, **kwargs)
        if view_type == 'form':
            doc = etree.XML(res['arch'])
            for node in doc.xpath("//field[@name='tax_ids']"):
                node.set('readonly', '1')
                node.set('force_save', '1')
            for node in doc.xpath("//field[@name='tax_id']"):
                node.set('readonly', '1')
                node.set('force_save', '1')
            res['arch'] = etree.tostring(doc, encoding='unicode')
        return res

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # Campo existente que ya definimos para ref sobre price_subtotal:
    ref = fields.Float(
        string='REF Subtotal',
        compute='_compute_ref',
        store=True,
        readonly=True,
        digits=(16, 4)
     )
    # Campo auxiliar que indica en qué moneda formatear "ref" y "ref_unit"
    order_currency_ref_id = fields.Many2one(
        'res.currency',
        string="Moneda REF",
        compute='_compute_ref_currency',
        store=True,
    )

    # Nuevo campo que hace referencia al precio unitario convertido:
    ref_unit = fields.Float(
        string='REF Unit',
        compute='_compute_ref_unit',
        inverse='_inverse_ref_unit',
        store=True,
        digits=(16, 4)
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for line in records:
            tax_field = getattr(line, 'tax_ids', getattr(line, 'tax_id', False))
            if (not line.display_type or line.display_type == 'product') and not tax_field:
                raise ValidationError("Las líneas de ventas deben tener al menos un impuesto configurado. Producto/Descripción: %s" % (line.product_id.name or line.name))
        records._check_price_not_below_cost()
        return records

    def write(self, vals):
        res = super().write(vals)
        for line in self:
            tax_field = getattr(line, 'tax_ids', getattr(line, 'tax_id', False))
            if (not line.display_type or line.display_type == 'product') and not tax_field:
                raise ValidationError("Las líneas de ventas deben tener al menos un impuesto configurado. Producto/Descripción: %s" % (line.product_id.name or line.name))
        self._check_price_not_below_cost()
        return res

    def _check_price_not_below_cost(self):
        usd = self.env.ref('base.USD', raise_if_not_found=False)
        for line in self:
            if not line.product_id or line.price_unit <= 0.0 or line.display_type in ('line_section', 'line_note'):
                continue
            
            currency = line.order_id.currency_id
            company_currency = line.order_id.company_id.currency_id
            
            final_price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            
            if currency == company_currency:
                cost = line.product_id.standard_price
            elif usd and currency == usd:
                cost = getattr(line.product_id, 'standard_price_usd', 0.0)
            else:
                cost = line.product_id.standard_price
            
            if cost > 0.0 and final_price < (cost - 0.001):
                raise ValidationError("No puede vender el producto '%s' por un precio por debajo de su costo.\nCosto: %s\nPrecio final con descuento: %s" % (
                    line.product_id.display_name, round(cost, 2), round(final_price, 2)
                ))

    @api.depends('order_id.currency_id', 'order_id.company_id.currency_id')
    def _compute_ref_currency(self):
        """
        Definimos que 'order_currency_ref_id' sea la moneda CONTRARIA a la de la orden:
        - Si la orden está en USD → queremos mostrar REF en VEF (moneda de compañía).
        - Si la orden está en VEF → queremos mostrar REF en USD.
        - Para cualquier otra moneda → mantendremos USD por defecto.
        """
        usd = self.env.ref('base.USD', raise_if_not_found=False)
        for line in self:
            order = line.order_id
            if not order:
                line.order_currency_ref_id = False
                continue

            order_cur = order.currency_id         # moneda de la orden
            comp_cur = order.company_id.currency_id  # moneda de la compañía

            if usd and order_cur == usd:
                # Orden en USD → REF en VEF
                line.order_currency_ref_id = comp_cur
            elif comp_cur and order_cur == comp_cur and usd:
                # Orden en VEF → REF en USD
                line.order_currency_ref_id = usd
            else:
                # Cualquier otro caso, usamos la moneda de compañía o la de la orden
                line.order_currency_ref_id = comp_cur or order_cur

    @api.depends('price_subtotal', 'order_id.currency_id', 'order_id.company_id.currency_id', 'order_id.date_order')
    def _compute_ref(self):
        """
        Cálculo de REF Subtotal ($):

        - Si la orden está en USD, price_subtotal viene en USD;
        REF = USD * tasa_USD→VEF
        - Si la orden está en VEF, price_subtotal viene en VEF;
        REF = VEF / tasa_USD→VEF
        - Otros casos → REF = 0.0
        """
        for line in self:
            # valor por defecto
            line.ref = 0.0
            order = line.order_id
            target_currency = line.order_currency_ref_id
            if not order or not target_currency:
                continue

            price = line.price_subtotal or 0.0
            if not price:
                continue

            order_currency = order.currency_id
            company = order.company_id
            date_order = order.date_order or fields.Date.context_today(order)

            try:
                ref_value = order_currency._convert(
                    price,
                    target_currency,
                    company,
                    date_order,
                    round=False
                )
            except Exception:
                ref_value = 0.0

            line.ref = target_currency.round(ref_value) if target_currency else ref_value

    @api.depends('price_unit', 'order_id.currency_id', 'order_id.company_id.currency_id', 'order_id.date_order')
    def _compute_ref_unit(self):
        """
        Cálculo de REF Unit ($):

        Lógica idéntica a _compute_ref, pero aplicada a price_unit:
        - Si la orden está en USD, price_unit viene en USD;
          REF Unit = USD * tasa_USD→VEF
        - Si la orden está en VEF, price_unit viene en VEF;
          REF Unit = VEF / tasa_USD→VEF
        - Otros casos → REF Unit = 0.0
        """
        for line in self:
            line.ref_unit = 0.0
            order = line.order_id
            target_currency = line.order_currency_ref_id
            if not order or not target_currency:
                continue

            price_u = line.price_unit
            if not price_u:
                continue

            order_currency = order.currency_id
            company = order.company_id
            date_order = order.date_order or fields.Date.context_today(order)

            try:
                refu = order_currency._convert(
                    price_u,
                    target_currency,
                    company,
                    date_order,
                    round=False
                )
            except Exception:
                refu = 0.0

            line.ref_unit = refu

    def _inverse_ref_unit(self):
        for line in self:
            order = line.order_id
            target_currency = line.order_currency_ref_id
            if not order or not target_currency:
                continue

            ref_unit = line.ref_unit
            if ref_unit in (False, None):
                continue

            order_currency = order.currency_id
            company = order.company_id
            date_order = order.date_order or fields.Date.context_today(order)

            try:
                price_unit = target_currency._convert(
                    ref_unit,
                    order_currency,
                    company,
                    date_order,
                    round=False
                )
            except Exception:
                continue

            new_price_unit = order_currency.round(price_unit) if order_currency else price_unit
            if abs(line.price_unit - new_price_unit) > 0.01:
                line.price_unit = new_price_unit


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def _get_company_currency_invoice_rate(self, move, usd):
        """Return VEF/USD rate for customer invoices in company currency."""
        if not move or not move.company_id or not move.currency_id:
            return 0.0

        rate = float(getattr(move, 'tax_today', 0.0) or 0.0)
        if rate > 0:
            return rate

        if not usd:
            return 0.0

        inv_date = move.invoice_date or move.date or fields.Date.context_today(move)
        try:
            return float(usd._convert(1.0, move.currency_id, move.company_id, inv_date) or 0.0)
        except Exception:
            return 0.0

    def _normalize_invoice_price_from_sale_reference(self):
        """Normaliza price_unit en facturas cliente en moneda compañía.

        Cubre escenarios donde la línea se crea con precio en USD (p.ej. 5)
        pero la factura está en Bs y debe guardarse en Bs (USD * tax_today).
        """
        if self.env.context.get('skip_ref_invoice_sync'):
            return

        usd = self.env.ref('base.USD', raise_if_not_found=False)
        for line in self:
            move = line.move_id
            if not move or move.move_type != 'out_invoice':
                continue
            if line.display_type in ('line_section', 'line_note'):
                continue

            company = move.company_id
            company_currency = company.currency_id
            if move.currency_id != company_currency:
                continue

            tax_today = self._get_company_currency_invoice_rate(move, usd)
            if tax_today <= 0:
                continue

            usd_unit = 0.0
            sale_line = line.sale_line_ids[:1] if line.sale_line_ids else False
            if sale_line:
                order = sale_line.order_id
                if usd and order and order.currency_id == usd:
                    usd_unit = float(sale_line.price_unit or 0.0)
                else:
                    usd_unit = float(sale_line.ref_unit or 0.0)
                    if not usd_unit and usd and order and order.currency_id == company_currency:
                        order_date = order.date_order or fields.Date.context_today(order)
                        try:
                            usd_unit = float(order.currency_id._convert(
                                float(sale_line.price_unit or 0.0),
                                usd,
                                order.company_id,
                                order_date,
                            ) or 0.0)
                        except Exception:
                            usd_unit = 0.0

            # Fallback para líneas sin enlace de venta al momento del create:
            # si price_unit coincide con list_price_usd, asumimos que está en USD.
            if not usd_unit:
                product_usd = float(getattr(line.product_id, 'list_price_usd', 0.0) or 0.0)
                current_price = float(line.price_unit or 0.0)
                if product_usd > 0 and abs(current_price - product_usd) <= 0.0001:
                    usd_unit = product_usd

            if not usd_unit:
                continue

            expected_price_bs = move.currency_id.round(usd_unit * tax_today)
            vals_to_write = {}
            if abs(float(line.price_unit or 0.0) - expected_price_bs) > 0.01:
                vals_to_write['price_unit'] = expected_price_bs
            if line.currency_id != move.currency_id:
                vals_to_write['currency_id'] = move.currency_id.id
                
            if vals_to_write:
                line.with_context(skip_ref_invoice_sync=True, check_move_validity=False).write(vals_to_write)

    @api.model_create_multi
    def create(self, vals_list):
        """Creación de líneas de factura - Adaptado para Odoo 19"""
        lines = super().create(vals_list)

        usd = self.env.ref('base.USD', raise_if_not_found=False)
        for line in lines:
            move = line.move_id
            if not move or move.move_type != 'out_invoice':
                continue

            company = move.company_id
            company_currency = company.currency_id
            if move.currency_id != company_currency:
                continue

            sale_line = False
            if line.sale_line_ids:
                sale_line = line.sale_line_ids[:1]
            elif getattr(line, 'sale_line_id', False):
                sale_line = line.sale_line_id

            if not sale_line:
                continue

            order = sale_line.order_id
            order_currency = order.currency_id if order else False

            # Determinar la fuente USD real según la moneda de la orden.
            # - SO en USD: el price_unit de la SO ya está en USD.
            # - SO en moneda compañía: usar ref_unit (USD equivalente).
            # - Fallback seguro: si price_unit local coincide con list_price_usd del producto,
            #   interpretamos que se ingresó el precio en USD sin convertir y usamos list_price_usd.
            ref_unit_usd = 0.0
            if usd and order_currency == usd:
                ref_unit_usd = sale_line.price_unit or 0.0
            else:
                ref_unit_usd = sale_line.ref_unit or 0.0
                product_usd = float(getattr(sale_line.product_id, 'list_price_usd', 0.0) or 0.0)
                sale_price = float(sale_line.price_unit or 0.0)
                if product_usd > 0 and abs(sale_price - product_usd) <= 0.0001:
                    ref_unit_usd = product_usd

            if not ref_unit_usd and usd and order and order_currency == company_currency:
                order_date = order.date_order or fields.Date.context_today(order)
                try:
                    ref_unit_usd = float(order_currency._convert(
                        float(sale_line.price_unit or 0.0),
                        usd,
                        company,
                        order_date,
                    ) or 0.0)
                except Exception:
                    ref_unit_usd = 0.0

            if not ref_unit_usd:
                continue

            rate = line._get_company_currency_invoice_rate(move, usd)

            if not rate:
                continue

            new_price_unit = move.currency_id.round(ref_unit_usd * rate)
            vals_to_write = {}
            if abs(float(line.price_unit or 0.0) - new_price_unit) > 0.01:
                vals_to_write['price_unit'] = new_price_unit
            if line.currency_id != move.currency_id:
                vals_to_write['currency_id'] = move.currency_id.id
            if vals_to_write:
                line.with_context(check_move_validity=False).write(vals_to_write)

        # Segunda pasada robusta: cubre casos donde sale_line_ids se enlaza
        # luego del create inicial o donde no hay enlace pero sí patrón USD.
        lines._normalize_invoice_price_from_sale_reference()

        return lines

    def write(self, vals):
        res = super().write(vals)
        # Si cambian enlaces/valores clave, reintentar normalización.
        if any(k in vals for k in ('sale_line_ids', 'price_unit', 'product_id', 'quantity')):
            self._normalize_invoice_price_from_sale_reference()
        return res


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _normalize_out_invoice_line_prices_from_sale(self):
        for move in self:
            if move.move_type != 'out_invoice':
                continue
            if move.currency_id != move.company_id.currency_id:
                continue
            move.invoice_line_ids._normalize_invoice_price_from_sale_reference()

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        moves._normalize_out_invoice_line_prices_from_sale()
        return moves

    def write(self, vals):
        res = super().write(vals)
        tracked_keys = {'tax_today', 'invoice_date', 'date', 'currency_id', 'invoice_line_ids'}
        if tracked_keys.intersection(vals.keys()):
            self._normalize_out_invoice_line_prices_from_sale()
        return res