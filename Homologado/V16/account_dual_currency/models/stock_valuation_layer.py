# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, tools
import datetime

class StockValuationLayer(models.Model):
    _inherit = 'stock.valuation.layer'

    currency_id_dif = fields.Many2one("res.currency",
                                     string="Divisa de Referencia",
                                     default=lambda self: self.env.company.currency_id_dif )
    unit_cost_usd = fields.Monetary('Valor unitario $', readonly=True, default=0,currency_field='currency_id_dif')
    value_usd = fields.Monetary('Valor Total $', readonly=True, default=0,currency_field='currency_id_dif')

    remaining_value_usd = fields.Monetary('Valor Restante $', readonly=True, default=0,currency_field='currency_id_dif')

    tasa = fields.Float('Tasa de Referencia', readonly=True, force_save=True, digits='Dual_Currency_rate')


    def write(self, vals):
        company = self.env.company
        if not 'unit_cost_usd' in vals and not 'value_usd' in vals:
            if not 'quantity' in vals and self.stock_move_id:
                new_rate = self.env.company.currency_id_dif.inverse_rate
                for rec in self:
                    if rec.stock_move_id:
                        picking_id = rec.stock_move_id.picking_id
                        date = datetime.date.today()
                        if picking_id:
                            date = picking_id.date_of_transfer or picking_id.create_date
                        new_rate_ids = self.env.company.currency_id_dif._get_rates(self.env.company, date)
                        if new_rate_ids:
                            new_rate = 1 / new_rate_ids[self.env.company.currency_id_dif.id]
                if 'unit_cost' in vals:
                    standard_price_usd = float(vals['unit_cost']) / new_rate
                    vals['unit_cost_usd'] = standard_price_usd
                if 'value' in vals:
                    value_usd = float(vals['value']) / new_rate
                    vals['value_usd'] = value_usd

        if 'account_move_id' in vals:
            new_rate = self.env.company.currency_id_dif.inverse_rate
            for rec in self:
                if rec.stock_move_id:
                    picking_id = rec.stock_move_id.picking_id
                    date = datetime.date.today()
                    if picking_id:
                        date = picking_id.date_of_transfer or picking_id.create_date
                    new_rate_ids = self.env.company.currency_id_dif._get_rates(self.env.company, date)
                    if new_rate_ids:
                        new_rate = 1 / new_rate_ids[self.env.company.currency_id_dif.id]
                move_id = self.env['account.move'].sudo().with_context(check_move_validity=False).search(
                    [('id', '=', vals['account_move_id'])])
                if move_id:
                    move_id.button_draft()
                    if move_id.line_ids[0].currency_id != self.currency_id:
                        for l in move_id.line_ids:
                            l.currency_id = self.currency_id
                            l.amount_currency = self.value * (-1 if l.amount_currency < 0 else 1)
                    if rec.stock_move_id.location_id.usage == 'supplier':
                        move_id.tax_today = new_rate
                    else:
                        move_id.tax_today = rec.tasa

        return super(StockValuationLayer, self).write(vals)
    
    def create(self, vals):
        company = self.env.company

        if isinstance(vals, list):
            for val in vals:
                if not val.get('unit_cost_usd') and not val.get('value_usd'):
                    if val.get('quantity') and float(val['quantity']) != 0:
                        product_id = self.env['product.product'].browse(val['product_id'])
                        new_rate = self.env.company.currency_id_dif.inverse_rate

                        if 'stock_move_id' in val:
                            stock_move = self.env['stock.move'].browse(val['stock_move_id'])
                            date = stock_move.picking_id.date_of_transfer or stock_move.picking_id.create_date or fields.Date.today()
                            rate_data = self.env.company.currency_id_dif._get_rates(self.env.company, date)
                            if rate_data:
                                new_rate = 1 / rate_data[self.env.company.currency_id_dif.id]

                            if 'unit_cost' in val:
                                val['unit_cost_usd'] = float(val['unit_cost']) / new_rate
                                val['value_usd'] = float(val['unit_cost']) * float(val['quantity']) / new_rate
                            val['tasa'] = new_rate

                            if product_id.cost_method in ('average', 'fifo') and stock_move.location_id.usage == 'supplier':
                                val['remaining_value_usd'] = float(val['quantity']) * val['unit_cost_usd']
                    else:
                        product_id = self.env['product.product'].browse(val['product_id'])
                        val['value_usd'] = product_id.qty_available * product_id.standard_price_usd
        else:
            if not vals.get('unit_cost_usd') and not vals.get('value_usd'):
                if vals.get('quantity') and float(vals['quantity']) != 0:
                    product_id = self.env['product.product'].browse(vals['product_id'])
                    new_rate = self.env.company.currency_id_dif.inverse_rate

                    if 'stock_move_id' in vals:
                        stock_move = self.env['stock.move'].browse(vals['stock_move_id'])
                        date = stock_move.picking_id.date_of_transfer or stock_move.picking_id.create_date or fields.Date.today()
                        rate_data = self.env.company.currency_id_dif._get_rates(self.env.company, date)
                        if rate_data:
                            new_rate = 1 / rate_data[self.env.company.currency_id_dif.id]

                        if 'unit_cost' in vals:
                            vals['unit_cost_usd'] = float(vals['unit_cost']) / new_rate
                            vals['value_usd'] = float(vals['unit_cost']) * float(vals['quantity']) / new_rate
                        vals['tasa'] = new_rate

                        if product_id.cost_method in ('average', 'fifo') and stock_move.location_id.usage == 'supplier':
                            vals['remaining_value_usd'] = float(vals['quantity']) * vals['unit_cost_usd']
                else:
                    product_id = self.env['product.product'].browse(vals['product_id'])
                    vals['value_usd'] = product_id.qty_available * product_id.standard_price_usd

        res = super(StockValuationLayer, self).create(vals)
        return res

