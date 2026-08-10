# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.tools import float_is_zero, float_repr


class ProductProduct(models.Model):
    _inherit = 'product.product'

    currency_id_dif = fields.Many2one(
        'res.currency',
        string='Moneda Diferente',
        default=lambda self: self.env.company.currency_id_dif.id
    )
    list_price_usd = fields.Monetary(
        string="Precio de venta $",
        currency_field='currency_id_dif'
    )
    standard_price_usd = fields.Float(
        string="Costo Estándar USD",
        default=0.0,
        help="Campo referencial en USD. No afecta la valoración del inventario."
    )
    value_usd_svl = fields.Float(
        compute='_compute_value_usd_svl',
        compute_sudo=True
    )

    @api.depends('stock_valuation_layer_ids')
    @api.depends_context('to_date', 'company')
    def _compute_value_usd_svl(self):
        company_id = self.env.company.id
        domain = [
            ('product_id', 'in', self.ids),
            ('company_id', '=', company_id),
        ]
        if self.env.context.get('to_date'):
            to_date = fields.Datetime.to_datetime(self.env.context['to_date'])
            domain.append(('create_date', '<=', to_date))

        groups = self.env['stock.valuation.layer'].read_group(
            domain, ['value_usd:sum'], ['product_id']
        )

        products = self.browse()
        for group in groups:
            product = self.browse(group['product_id'][0])
            product.sudo().with_company(company_id).value_usd_svl = self.env.company.currency_id_dif.round(group['value_usd'])
            products |= product

        remaining = self - products
        remaining.sudo().with_company(company_id).value_usd_svl = 0

    @api.onchange('standard_price_usd')
    def _onchange_standard_price_usd(self):
        # Este método solo mantiene sincronizado el campo en la plantilla,
        # no afecta la contabilidad ni la valoración de inventario.
        for rec in self:
            if rec.product_tmpl_id:
                rec.product_tmpl_id.standard_price_usd = rec.standard_price_usd

    def _prepare_in_svl_vals(self, quantity, unit_cost):
        self.ensure_one()
        tasa = self.env['res.currency'].sudo().search([('name', '=', 'USD')], limit=1)
        unit_cost_usd = float(unit_cost) / tasa.inverse_rate
        vals = {
            'product_id': self.id,
            'value': unit_cost * quantity,
            'unit_cost': unit_cost,
            'quantity': quantity,
        }
        if self.cost_method in ('average', 'fifo'):
            vals['remaining_qty'] = quantity
            vals['remaining_value'] = vals['value']
        return vals

    def _prepare_out_svl_vals(self, quantity, company):
        self.ensure_one()
        quantity = -1 * quantity
        tasa_tmp = 1
        if self.standard_price_usd > 0:
            tasa_tmp = round(self.standard_price / self.standard_price_usd, 4)

        vals = {
            'product_id': self.id,
            'value': quantity * self.standard_price,
            'value_usd': quantity * self.standard_price_usd,
            'unit_cost': self.standard_price,
            'tasa': tasa_tmp,
            'unit_cost_usd': self.standard_price_usd,
            'quantity': quantity,
        }

        if self.cost_method in ('average', 'fifo'):
            fifo_vals = self._run_fifo(abs(quantity), company)
            vals['remaining_qty'] = fifo_vals.get('remaining_qty')

            if self.cost_method == 'average':
                currency = self.env.company.currency_id
                rounding_error = currency.round(self.standard_price * self.quantity_svl - self.value_svl)
                if rounding_error and abs(rounding_error) <= (abs(quantity) * currency.rounding) / 2:
                    vals['value'] += rounding_error
                    vals['rounding_adjustment'] = '\nRounding Adjustment: %s%s %s' % (
                        '+' if rounding_error > 0 else '',
                        float_repr(rounding_error, precision_digits=currency.decimal_places),
                        currency.symbol
                    )

            if self.cost_method == 'fifo':
                vals.update(fifo_vals)

        return vals

    def _run_fifo(self, quantity, company):
        self.ensure_one()
        qty_to_take_on_candidates = quantity
        candidates = self.env['stock.valuation.layer'].sudo().search([
            ('product_id', '=', self.id),
            ('remaining_qty', '>', 0),
            ('company_id', '=', company.id),
        ])
        new_standard_price = 0
        new_standard_price_usd = 0
        tmp_value = 0
        tmp_value_usd = 0

        for candidate in candidates:
            qty_taken_on_candidate = min(qty_to_take_on_candidates, candidate.remaining_qty)
            candidate_unit_cost = candidate.remaining_value / candidate.remaining_qty
            candidate_unit_cost_usd = candidate.remaining_value_usd / candidate.remaining_qty

            new_standard_price = candidate_unit_cost
            new_standard_price_usd = candidate_unit_cost_usd

            value_taken = qty_taken_on_candidate * candidate_unit_cost
            value_taken_usd = qty_taken_on_candidate * candidate_unit_cost_usd
            value_taken = candidate.currency_id.round(value_taken)

            new_remaining_value = candidate.remaining_value - value_taken
            new_remaining_value_usd = candidate.remaining_value_usd - value_taken_usd

            candidate.write({
                'remaining_qty': candidate.remaining_qty - qty_taken_on_candidate,
                'remaining_value': new_remaining_value,
                'remaining_value_usd': new_remaining_value_usd,
            })

            qty_to_take_on_candidates -= qty_taken_on_candidate
            tmp_value += value_taken
            tmp_value_usd += value_taken_usd

            if float_is_zero(qty_to_take_on_candidates, precision_rounding=self.uom_id.rounding):
                if float_is_zero(candidate.remaining_qty, precision_rounding=self.uom_id.rounding):
                    next_candidates = candidates.filtered(lambda svl: svl.remaining_qty > 0)
                    new_standard_price = next_candidates and next_candidates[0].unit_cost or new_standard_price
                    new_standard_price_usd = next_candidates and next_candidates[0].unit_cost_usd or new_standard_price_usd
                break

        if new_standard_price and self.cost_method == 'fifo':
            self.sudo().with_company(company.id).with_context(disable_auto_svl=True).standard_price = new_standard_price

        vals = {}
        if float_is_zero(qty_to_take_on_candidates, precision_rounding=self.uom_id.rounding):
            tasa_tmp = round(tmp_value_usd / tmp_value, 4) if tmp_value else 1
            vals = {
                'value': -tmp_value,
                'value_usd': -tmp_value_usd,
                'unit_cost': tmp_value / quantity,
                'tasa': tasa_tmp,
                'unit_cost_usd': tmp_value_usd / quantity,
            }
        else:
            last_fifo_price = new_standard_price or self.standard_price
            last_fifo_price_usd = new_standard_price_usd or self.standard_price_usd
            negative_value = last_fifo_price * -qty_to_take_on_candidates
            negative_value_usd = last_fifo_price_usd * -qty_to_take_on_candidates
            tmp_value += abs(negative_value)
            tmp_value_usd += abs(negative_value_usd)
            vals = {
                'remaining_qty': -qty_to_take_on_candidates,
                'value': -tmp_value,
                'unit_cost': last_fifo_price,
                'value_usd': -tmp_value_usd,
                'unit_cost_usd': last_fifo_price_usd,
            }

        return vals

    def price_compute(self, price_type, uom=False, currency=False, company=None, date=False):
        company = company or self.env.company
        date = date or fields.Date.context_today(self)

        self = self.with_company(company)
        if price_type == 'standard_price':
            self = self.sudo()

        prices = dict.fromkeys(self.ids, 0.0)
        for product in self:
            prices[product.id] = product[price_type] or 0.0

            if price_type == 'list_price':
                prices[product.id] += product.price_extra
                if self._context.get('no_variant_attributes_price_extra'):
                    prices[product.id] += sum(self._context.get('no_variant_attributes_price_extra'))

            if uom:
                prices[product.id] = product.uom_id._compute_price(prices[product.id], uom)

        return prices

    def write(self, vals):
        if 'list_price_usd' in vals and vals.get('list_price_usd'):
            tasa = self.env.company.currency_id_dif
            if tasa and vals.get('list_price_usd') > 0:
                vals['list_price'] = vals['list_price_usd'] * tasa.inverse_rate
        return super().write(vals)

    @api.model
    def create(self, vals):
        if 'list_price_usd' in vals and vals.get('list_price_usd'):
            tasa = self.env.company.currency_id_dif
            if tasa and vals.get('list_price_usd') > 0:
                vals['list_price'] = vals['list_price_usd'] * tasa.inverse_rate
        return super().create(vals)
