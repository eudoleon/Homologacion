# -*- coding: utf-8 -*-
from collections import defaultdict
from contextlib import contextmanager
from datetime import date, timedelta
from functools import lru_cache

from odoo import api, fields, models, Command, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import frozendict, formatLang, format_date, float_compare, Query
from lxml import etree
import logging
_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.model
    def get_view(self, view_id=None, view_type='form', **kwargs):
        res = super().get_view(view_id=view_id, view_type=view_type, **kwargs)
        if view_type == 'form':
            doc = etree.XML(res['arch'])
            for node in doc.xpath("//field[@name='tax_ids']"):
                node.set('readonly', '1')
                node.set('force_save', '1')
            res['arch'] = etree.tostring(doc, encoding='unicode')
        return res


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def _extract_first_rel_id_from_commands(self, commands):
        """Extract first linked id from x2many commands list."""
        if not commands:
            return False
        for command in commands:
            if not isinstance(command, (list, tuple)) or not command:
                continue
            op = command[0]
            if op in (1, 4) and len(command) > 1 and command[1]:
                return command[1]
            if op == 6 and len(command) > 2 and command[2]:
                ids = command[2]
                return ids[0] if ids else False
        return False

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for line in records:
            if line.move_id.move_type in ['out_invoice', 'out_refund', 'in_invoice', 'in_refund'] and line.display_type == 'product' and not line.tax_ids:
                raise ValidationError("Las líneas de facturas deben tener al menos un impuesto configurado. Producto/Descripción: %s" % (line.product_id.name or line.name))
        return records

    def write(self, vals):
        res = super().write(vals)
        for line in self:
            if line.move_id.move_type in ['out_invoice', 'out_refund', 'in_invoice', 'in_refund'] and line.display_type == 'product' and not line.tax_ids:
                raise ValidationError("Las líneas de facturas deben tener al menos un impuesto configurado. Producto/Descripción: %s" % (line.product_id.name or line.name))
        return res

    debit_usd = fields.Monetary(currency_field='currency_id_dif', string='Débito Ref', store=True, compute="_debit_usd",
                                 readonly=False, )
    credit_usd = fields.Monetary(currency_field='currency_id_dif', string='Crédito Ref', store=True,
                                 compute="_credit_usd", readonly=False)
    tax_today = fields.Float(related="move_id.tax_today", store=True, digits='Dual_Currency_rate')
    currency_id_dif = fields.Many2one("res.currency", related="move_id.currency_id_dif", store=True)
    
    # CAMPOS ELIMINADOS: price_unit_usd y price_subtotal_usd
    
    # Campos de referencia para precio unitario y subtotal
    ref_unit = fields.Float(
        string='Precio Unit. Ref.', 
        store=True,
        digits=(16, 4),  # 4 decimales
        help="Precio unitario en moneda de referencia"
    )
    
    subtotal_ref = fields.Float(
        string='Subtotal Ref.', 
        store=True,
        digits=(16, 2),  # 2 decimales
        help="Subtotal en moneda de referencia (ref_unit * quantity)"
    )
    
    amount_residual_usd = fields.Monetary(string='Residual Amount USD', compute='_compute_amount_residual_usd', store=True,
                                        help="The residual amount on a journal item expressed in the company currency.")
    balance_usd = fields.Monetary(string='Balance Ref.',
                                  currency_field='currency_id_dif', store=True, readonly=False,
                                  compute='_compute_balance_usd',
                                  default=lambda self: self._compute_balance_usd(),
                                  help="Technical field holding the debit_usd - credit_usd in order to open meaningful graph views from reports")

    @api.depends('currency_id', 'company_id', 'move_id.date','move_id.tax_today')
    def _compute_currency_rate(self):

        @lru_cache()
        def get_rate(from_currency, to_currency, company, date):
            rate = self.env['res.currency']._get_conversion_rate(
                from_currency=from_currency,
                to_currency=to_currency,
                company=company,
                date=date,
            )
            return rate

        for line in self:
            if line.currency_id and line.company_id and line.currency_id == line.company_id.currency_id:
                line.currency_rate = 1.0
            else:
                line.currency_rate = 1 / line.move_id.tax_today if (line.move_id and line.move_id.tax_today > 0) else 1.0
            _logger.debug("[DUAL LINE] _compute_currency_rate line=%s move=%s tax_today=%s currency_rate=%s", line.id, line.move_id and line.move_id.id or None, line.move_id.tax_today if line.move_id else 0, line.currency_rate)

    @api.onchange('amount_currency')
    def _onchange_amount_currency(self):
        _logger.debug("[DUAL LINE] _onchange_amount_currency triggered for lines=%s", self.ids)
        self._debit_usd()
        self._credit_usd()

    @api.onchange('product_id', 'price_unit', 'quantity', 'tax_ids', 'display_type')
    def _onchange_refresh_dual_invoice_totals(self):
        """Refresca totales duales del documento al editar líneas de factura."""
        for line in self:
            move = line.move_id
            if not move or not move.is_invoice(include_receipts=True):
                continue
            _logger.debug("[DUAL LINE] _onchange_refresh_dual_invoice_totals line=%s move=%s", line.id, move.id)
            # Asegura que subtotal/total de líneas esté al día antes de refrescar la dualidad.
            try:
                move.invoice_line_ids._compute_totals()
                move._compute_tax_totals()
            except Exception:
                _logger.exception("[DUAL LINE] error calling _compute_totals/_compute_tax_totals for move=%s", move.id)

            # En edición inline, la línea actual puede no estar consolidada aún
            # en move.invoice_line_ids; la incluimos explícitamente para el cálculo.
            lines_for_total = (move.invoice_line_ids | line).filtered(
                lambda l: l.display_type not in ('line_section', 'line_note')
            )
            amount_untaxed = sum(lines_for_total.mapped('price_subtotal')) if lines_for_total else 0.0
            amount_total = sum(lines_for_total.mapped('price_total')) if lines_for_total else 0.0
            amount_tax = amount_total - amount_untaxed

            move._apply_dual_live_amounts(amount_untaxed, amount_tax, amount_total)

            if move.currency_id == move.company_currency_id:
                untaxed_usd = (amount_untaxed / move.tax_today) if move.tax_today > 0 else 0.0
                tax_usd = (amount_tax / move.tax_today) if move.tax_today > 0 else 0.0
                total_usd = (amount_total / move.tax_today) if move.tax_today > 0 else 0.0
                untaxed_bs = amount_untaxed
                tax_bs = amount_tax
                total_bs = amount_total
            else:
                untaxed_usd = amount_untaxed
                tax_usd = amount_tax
                total_usd = amount_total
                untaxed_bs = amount_untaxed * move.tax_today
                tax_bs = amount_tax * move.tax_today
                total_bs = amount_total * move.tax_today

            move.amount_untaxed_usd = untaxed_usd
            move.amount_tax_usd = tax_usd
            move.amount_total_usd = total_usd
            move.amount_untaxed_bs = untaxed_bs
            move.amount_tax_bs = tax_bs
            move.amount_total_bs = total_bs

    def write(self, vals):
        """Override write para sincronizar price_unit y ref_unit al guardar (2 decimales)"""
        _logger.debug("[DUAL LINE] AccountMoveLine.write called on %s with vals=%s", self.ids, vals)

        # Protección contra reentrada: si venimos con el flag, no ejecutar la sincronización
        if self.env.context.get('skip_dual_sync'):
            return super(AccountMoveLine, self).write(vals)

        # Ejecutar la escritura principal
        result = super(AccountMoveLine, self).write(vals)

        # Después de guardar, recalcular los campos según lo que se modificó
        for line in self:
            if line.display_type in ('line_section', 'line_note'):
                continue

            tax_today = line.move_id.tax_today if line.move_id.tax_today else 0.0
            values_to_update = {}

            # Si se modificó price_unit, recalcular ref_unit
            if 'price_unit' in vals:
                if tax_today > 0:
                    ref_unit_calculated = round(line.price_unit / tax_today, 4)
                    values_to_update['ref_unit'] = ref_unit_calculated
                else:
                    values_to_update['ref_unit'] = 0.0

            # Si se modificó ref_unit, recalcular price_unit
            elif 'ref_unit' in vals:
                if tax_today > 0:
                    price_unit_calculated = round(line.ref_unit * tax_today, 4)
                    values_to_update['price_unit'] = price_unit_calculated
                else:
                    values_to_update['price_unit'] = 0.0

            # Siempre recalcular subtotal_ref si cambió ref_unit o quantity o price_unit
            if 'ref_unit' in vals or 'quantity' in vals or 'price_unit' in vals:
                subtotal_ref_calculated = round((values_to_update.get('ref_unit', line.ref_unit) or 0.0) * line.quantity, 2)
                values_to_update['subtotal_ref'] = subtotal_ref_calculated

            # Si hay cambios, escribirlos usando contexto protector para evitar reentrada
            if values_to_update:
                _logger.debug("[DUAL LINE] writing back computed values for line=%s: %s", line.id, values_to_update)
                super(AccountMoveLine, line.with_context(skip_dual_sync=True)).write(values_to_update)

        return result

    @api.model_create_multi
    def create(self, vals_list):
        """Override create para sincronizar price_unit y ref_unit al crear (2 decimales)"""
        _logger.debug("[DUAL LINE] AccountMoveLine.create called with vals_list=%s", vals_list)
        for vals in vals_list:
            # En Odoo v19 este campo es requerido y para línea normal debe ser 'product'.
            # FIX: No forzar 'product' si no viene en los vals, dejar que Odoo lo maneje,
            # o si es estrictamente necesario, evitarlo en diarios de banco para no romper la conciliación.
            if 'display_type' not in vals or vals['display_type'] is None:
                move_id = vals.get('move_id')
                is_bank_or_entry = False
                if move_id:
                    move = self.env['account.move'].browse(move_id)
                    if move.journal_id.type in ('bank', 'cash'):
                        is_bank_or_entry = True
                
                # Solo forzamos 'product' si no es banco/efectivo, para no romper _sync_dynamic_lines
                if not is_bank_or_entry:
                    vals['display_type'] = 'product'
            
            # Obtener la tasa del move_id si existe
            move_id = vals.get('move_id')
            if move_id:
                move = self.env['account.move'].browse(move_id)
                tax_today = move.tax_today if move.tax_today else 0.0
                
                # Si se proporciona price_unit pero no ref_unit, calcular ref_unit con 4 decimales
                if 'price_unit' in vals and 'ref_unit' not in vals:
                    if tax_today > 0:
                        vals['ref_unit'] = round(vals['price_unit'] / tax_today, 4)
                    else:
                        vals['ref_unit'] = 0.0
                
                # Si se proporciona ref_unit pero no price_unit, calcular price_unit con 4 decimales
                elif 'ref_unit' in vals and 'price_unit' not in vals:
                    if tax_today > 0:
                        vals['price_unit'] = round(vals['ref_unit'] * tax_today, 4)
                    else:
                        vals['price_unit'] = 0.0
                
                # Calcular subtotal_ref con 2 decimales
                quantity = vals.get('quantity', 1.0)
                ref_unit = vals.get('ref_unit', 0.0)
                vals['subtotal_ref'] = round(ref_unit * quantity, 2)
                _logger.debug("[DUAL LINE] create computed for vals move_id=%s product=%s price_unit=%s ref_unit=%s subtotal_ref=%s", vals.get('move_id'), vals.get('product_id'), vals.get('price_unit'), vals.get('ref_unit'), vals.get('subtotal_ref'))
        
        return super(AccountMoveLine, self).create(vals_list)

    # MÉTODOS ELIMINADOS: _onchange_price_unit_usd, _onchange_product_id, _price_unit_usd, _price_subtotal_usd

    @api.depends('debit_usd', 'credit_usd')
    def _compute_balance_usd(self):
        for line in self:
            line.balance_usd = line.debit_usd - line.credit_usd

    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        if 'tax_today' not in fields:
            return super(AccountMoveLine, self).read_group(domain, fields, groupby, offset=offset, limit=limit,
                                                             orderby=orderby, lazy=lazy)
        res = super(AccountMoveLine, self).read_group(domain, fields, groupby, offset=offset, limit=limit,
                                                      orderby=orderby, lazy=lazy)
        for group in res:
            if group.get('__domain'):
                records = self.search(group['__domain'])
                group['tax_today'] = 0
        return res

    @api.depends('amount_currency', 'tax_today','debit')
    def _debit_usd(self):
        for rec in self:
            if not rec.debit == 0:
                if rec.move_id.currency_id == self.env.company.currency_id:
                    amount_currency = (rec.amount_currency if rec.amount_currency > 0 else (rec.amount_currency * -1))
                    rec.debit_usd = (amount_currency / rec.tax_today) if rec.tax_today > 0 else 0
                else:
                    rec.debit_usd = (rec.amount_currency if rec.amount_currency > 0 else (rec.amount_currency * -1))
            else:
                rec.debit_usd = 0

    @api.depends('amount_currency', 'tax_today','credit')
    def _credit_usd(self):
        for rec in self:
            if not rec.credit == 0:
                if rec.move_id.currency_id == self.env.company.currency_id:
                    amount_currency = (rec.amount_currency if rec.amount_currency > 0 else (rec.amount_currency * -1))
                    rec.credit_usd = (amount_currency / rec.tax_today) if rec.tax_today > 0 else 0
                else:
                    rec.credit_usd = (rec.amount_currency if rec.amount_currency > 0 else (rec.amount_currency * -1))
            else:
                rec.credit_usd = 0

    @api.depends('debit','credit','debit_usd', 'credit_usd', 'amount_currency', 'account_id', 'currency_id', 'move_id.state',
                  'company_id',
                  'matched_debit_ids', 'matched_credit_ids', 'move_id.show_usd')
    def _compute_amount_residual_usd(self):
        for line in self:
            # Si el move tiene show_usd=False, forzar amount_residual_usd a 0
            if line.move_id and not line.move_id.show_usd:
                line.amount_residual_usd = 0.0
                continue

            if line.id and (line.account_id.reconcile or line.account_id.account_type in ('asset_cash', 'liability_credit_card')):
                reconciled_balance = sum(line.matched_credit_ids.mapped('amount_usd')) \
                                   - sum(line.matched_debit_ids.mapped('amount_usd'))

                line.amount_residual_usd = (line.debit_usd - line.credit_usd) - reconciled_balance
            else:
                line.amount_residual_usd = 0.0
