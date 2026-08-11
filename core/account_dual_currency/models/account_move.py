# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, Command
from odoo.exceptions import UserError, ValidationError, AccessError, RedirectWarning
from odoo.tools import (
    date_utils,
    # email_re,
    # email_split,
    float_compare,
    # float_is_zero,
    # format_amount,
    # format_date,
    formatLang,
    # frozendict,
    # get_lang,
    # is_html_empty,
    # sql
)
import json
import logging
_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = 'account.move'

    amount_untaxed_in_currency_signed = fields.Monetary(
        string="Base imponible en moneda firmada",
        currency_field='company_currency_id',
        compute='_compute_amount_untaxed_in_currency_signed',
        store=True,
        help="Base imponible en moneda local, con signo según el tipo de documento (positivo para facturas, negativo para reembolsos/NC)."
    )

    @api.depends('amount_untaxed', 'move_type')
    def _compute_amount_untaxed_in_currency_signed(self):
        for move in self:
            sign = -1 if move.move_type in ('out_refund', 'in_refund') else 1
            move.amount_untaxed_in_currency_signed = abs(move.amount_untaxed) if move.move_type == 'entry' else -(sign * move.amount_untaxed)

    
    amount_untaxed_signed = fields.Monetary(
        string="Importe sin impuestos firmado",
        currency_field='company_currency_id',
        compute='_compute_amount_untaxed_signed',
        store=True,
        help="Base imponible en moneda local, con signo según el tipo de documento (positivo para facturas, negativo para reembolsos/NC)."
    )

    @api.depends('amount_untaxed_bs', 'move_type')
    def _compute_amount_untaxed_signed(self):
        for move in self:
            sign = -1 if move.move_type in ('out_refund', 'in_refund') else 1
            move.amount_untaxed_signed = (move.amount_untaxed_bs or 0.0) * sign


    @api.model
    def _get_default_tax_today(self):
        rate = self.env['res.currency'].get_trm_systray()
        return rate or self.env.company.currency_id_dif.inverse_rate or 1.0
        
    currency_id_dif = fields.Many2one("res.currency",
                                     string="Moneda Dual Ref.",
                                     default=lambda self: self.env['res.currency'].search([('name', '=', 'USD')],
                                                                                           limit=1), )

    acuerdo_moneda = fields.Boolean(string="Acuerdo de Factura Bs.", default=False)
    show_usd = fields.Boolean(string="Mostrar USD?", default=True,
                             help="Si está desmarcado, los valores en USD serán 0 para que no aparezcan en contabilidad ni en la deuda del cliente.")

    tax_today = fields.Float(string="Tasa", store=True,
                              default=lambda self: self._get_default_tax_today(),
                              tracking=True, digits='Dual_Currency_rate')

    tax_today_edited = fields.Boolean(string="Tasa editada", default=False)

    edit_trm = fields.Boolean(string="Editar tasa", compute='_edit_trm')

    name_rate = fields.Char(string='Tasa de Referencia Temp')
    amount_untaxed_usd = fields.Monetary(currency_field='currency_id_dif', string="Base imponible Ref.", store=True,
                                                                                 compute="_amount_all_usd", copy=False)
    amount_tax_usd = fields.Monetary(currency_field='currency_id_dif', string="Impuestos Ref.", store=True,
                                                                         readonly=True, compute="_amount_all_usd", copy=False)
    amount_total_usd = fields.Monetary(currency_field='currency_id_dif', string='Total Ref.', store=True, readonly=True,
                                       compute='_amount_all_usd',
                                                                             tracking=True)

    amount_residual_usd = fields.Monetary(currency_field='currency_id_dif', compute='_compute_amount', string='Adeudado Ref.',
                                                                                    readonly=True, store=True, copy=False)
    invoice_payments_widget_usd = fields.Binary(groups="account.group_account_invoice,account.group_account_readonly",
                                              compute='_compute_payments_widget_reconciled_info_USD')

    amount_untaxed_bs = fields.Monetary(currency_field='company_currency_id', string="Base imponible Bs.", store=True, copy=False,
                                         compute="_amount_all_usd")
    amount_tax_bs = fields.Monetary(currency_field='company_currency_id', string="Impuestos Bs.", compute="_amount_all_usd", store=True, copy=False,
                                    readonly=True)
    amount_total_bs = fields.Monetary(currency_field='company_currency_id', string='Total Bs.', store=True,
                                      readonly=True,
                                      compute='_amount_all_usd', copy=False)

    # Campos de vista en vivo para borrador (no dependen del ciclo de guardado).
    amount_untaxed_usd_live = fields.Monetary(currency_field='currency_id_dif', string="Base imponible Ref.", copy=False)
    amount_tax_usd_live = fields.Monetary(currency_field='currency_id_dif', string="Impuestos Ref.", copy=False)
    amount_total_usd_live = fields.Monetary(currency_field='currency_id_dif', string='Total Ref.', copy=False)
    amount_untaxed_bs_live = fields.Monetary(currency_field='company_currency_id', string="Base imponible Bs.", copy=False)
    amount_tax_bs_live = fields.Monetary(currency_field='company_currency_id', string="Impuestos Bs.", copy=False)
    amount_total_bs_live = fields.Monetary(currency_field='company_currency_id', string='Total Bs.', copy=False)

    amount_total_signed_usd = fields.Monetary(
        string='Total Ref.',
        compute='_compute_amount', store=True, readonly=True,
        currency_field='currency_id_dif', copy=False
    )

    invoice_payments_widget_bs = fields.Binary(groups="account.group_account_invoice", copy=False)

    same_currency = fields.Boolean(string="Mismo tipo de moneda", compute='_same_currency')

    verificar_pagos = fields.Boolean(string="Verificar pagos", compute='_verificar_pagos')

    asset_remaining_value_ref = fields.Monetary(currency_field='currency_id_dif', string='Valor depreciable Ref.', copy=False, compute='_compute_depreciation_cumulative_value_ref')
    asset_depreciated_value_ref = fields.Monetary(currency_field='currency_id_dif', string='Depreciación Acu. Ref.', copy=False, compute='_compute_depreciation_cumulative_value_ref')

    # --- ✨ CAMPOS IGTF CORREGIDOS Y MEJORADOS ---
    aplicar_igtf = fields.Boolean(string="Aplica IGTF")
    journal_igtf_id = fields.Many2one(
        'account.journal',
        string='Diario IGTF',
        check_company=True
    )
    mount_igtf = fields.Monetary(
        currency_field='company_currency_id', # <-- ESTE ES EL CAMPO CORRECTO
        string='Monto IGTF',
        readonly=True
    )
    move_igtf_id = fields.Many2one(
        'account.move',
        'Asiento IGTF',
        readonly=True,
        copy=False
    )

    depreciation_value_ref = fields.Monetary(
        string="Depreciation Ref.",
        compute="_compute_depreciation_value_ref", inverse="_inverse_depreciation_value_ref", store=True, copy=False
    )

    def _post(self, soft=True):
        # Agregamos 'skip_readonly_check' al contexto. 
        # Esto le dice a Odoo: "Soy un proceso del sistema, déjame escribir aunque esté publicado"
        ctx = {
            'skip_tax_today_onchange': True,
            'skip_readonly_check': True, # ESTA ES LA CLAVE
            'check_move_validity': False
        }
        moves_to_post = self.with_context(**ctx)

        for move in moves_to_post:
            # Ejecutamos TODO lo dual antes de que el estado cambie
            move._verificar_pagos()
            _logger.info(f"[DUAL] Pre-calculo listo para factura {move.id}")

        # Llamamos al super con el contexto de "saltar chequeo de solo lectura"
        res = super(AccountMove, moves_to_post)._post(soft=soft)
        return res

    @api.depends('asset_id', 'depreciation_value', 'asset_id.total_depreciable_value', 'asset_id.already_depreciated_amount_import')
    def _compute_depreciation_cumulative_value(self):
        super(AccountMove, self)._compute_depreciation_cumulative_value()
        for move in self:
            if move.asset_id:
                move.asset_remaining_value_ref = (move.asset_remaining_value / move.tax_today) if move.tax_today != 0 else 0
                move.asset_depreciated_value_ref = (move.asset_depreciated_value / move.tax_today) if move.tax_today != 0 else 0

    @api.depends('line_ids.balance_usd')
    def _compute_depreciation_value_ref(self):
        for move in self:
            asset = move.asset_id or move.reversed_entry_id.asset_id 
            if asset:
                account = asset.account_depreciation_expense_id if asset.asset_type != 'sale' else asset.account_depreciation_id
                asset_depreciation = sum(
                    move.line_ids.filtered(lambda l: l.account_id == account).mapped('balance_usd')
                )
                if any(
                        line.account_id == asset.account_asset_id
                        and float_compare(-line.balance_usd, asset.original_value_ref,
                                             precision_rounding=asset.currency_id.rounding) == 0
                        for line in move.line_ids
                ):
                    account = asset.account_depreciation_id
                    asset_depreciation = (
                                asset.original_value_ref
                                - asset.salvage_value_ref
                                - sum(
                            move.line_ids.filtered(lambda l: l.account_id == account).mapped(
                                'debit_usd' if asset.original_value_ref > 0 else 'credit_usd'
                            )
                        ) * (-1 if asset.original_value_ref < 0 else 1)
                    )
            else:
                asset_depreciation = 0
            move.depreciation_value_ref = asset_depreciation

    def _inverse_depreciation_value(self):
        for move in self:
            asset = move.asset_id
            amount = abs(move.depreciation_value_ref)
            account = asset.account_depreciation_expense_id if asset.asset_type != 'sale' else asset.account_depreciation_id
            move.write({'line_ids': [
                Command.update(line.id, {
                    'balance_usd': amount if line.account_id == account else -amount,
                })
                for line in move.line_ids
            ]})

    def _verificar_pagos(self):
        for rec in self:
            for line in rec.line_ids:
                if line.balance_usd == 0:
                    line._compute_balance_usd()
                line._compute_amount_residual_usd()
            rec.verificar_pagos = True

    @api.depends('invoice_date', 'company_id')
    def _compute_date(self):
        res = super(AccountMove, self)._compute_date()
        for rec in self:
            if rec.invoice_date and rec.company_id.currency_id_dif and not rec.tax_today_edited:
                new_rate_ids = self.env.company.currency_id_dif._get_rates(self.env.company, rec.invoice_date)
                if new_rate_ids:
                    new_rate = 1 / new_rate_ids[self.env.company.currency_id_dif.id]
                    rec.tax_today = round(new_rate, 6)

    def _fecha_para_tax_today(self, vals=None):
        if (vals and vals.get('move_type') == 'entry') or (not vals and self.move_type == 'entry'):
            if vals:
                return vals.get('date') or self.date
            return self.date
        if vals:
            return vals.get('invoice_date') or vals.get('date') or self.invoice_date or self.date
        return self.invoice_date or self.date

    def _compute_dual_amounts_from_lines(self):
        self.ensure_one()
        product_lines = self.invoice_line_ids.filtered(
            lambda l: l.display_type not in ('line_section', 'line_note')
        )
        amount_untaxed = sum(product_lines.mapped('price_subtotal')) if product_lines else 0.0
        amount_total = sum(product_lines.mapped('price_total')) if product_lines else 0.0
        amount_tax = amount_total - amount_untaxed
        return amount_untaxed, amount_tax, amount_total

    def _apply_dual_live_amounts(self, amount_untaxed, amount_tax, amount_total):
        self.ensure_one()
        # Definimos la precisión decimal de la moneda para la comparación
        prec = self.currency_id.decimal_places or 2
        
        # Calculamos los valores según la moneda
        if self.currency_id != self.env.company.currency_id:
            new_usd_untaxed = amount_untaxed
            new_usd_tax = amount_tax
            new_usd_total = amount_total
            new_bs_untaxed = amount_untaxed * self.tax_today
            new_bs_tax = amount_tax * self.tax_today
            new_bs_total = amount_total * self.tax_today
        else:
            new_usd_untaxed = (amount_untaxed / self.tax_today) if self.tax_today > 0 else 0.0
            new_usd_tax = (amount_tax / self.tax_today) if self.tax_today > 0 else 0.0
            new_usd_total = (amount_total / self.tax_today) if self.tax_today > 0 else 0.0
            new_bs_untaxed = amount_untaxed
            new_bs_tax = amount_tax
            new_bs_total = amount_total

        # Mapeo de campos y sus nuevos valores para procesar en bucle con validación
        vals_to_check = {
            'amount_untaxed_usd_live': new_usd_untaxed,
            'amount_tax_usd_live': new_usd_tax,
            'amount_total_usd_live': new_usd_total,
            'amount_untaxed_bs_live': new_bs_untaxed,
            'amount_tax_bs_live': new_bs_tax,
            'amount_total_bs_live': new_bs_total,
        }

        for field, value in vals_to_check.items():
            # Solo asignamos si el valor actual es distinto al nuevo valor calculado
            # Esto rompe la recursividad detectada en el shell
            if float_compare(self[field], value, precision_digits=prec) != 0:
                self[field] = value
    
    def _get_tasa_usd_by_date(self, fecha, company=None):
        if isinstance(fecha, (fields.Date.__class__,)):
            fecha_str = fields.Date.to_string(fecha)
        else:
            fecha_str = str(fecha)
        usd = self.env.ref('base.USD')
        company = company or self.env.company
        tasa = self.env['res.currency.rate'].search([
            ('currency_id', '=', usd.id),
            ('name', '=', fecha_str),
            ('company_id', '=', company.id)
        ], limit=1)
        if tasa:
            return tasa.inverse_company_rate

        # Fallback robusto para Odoo 19: usar el motor de tasas por fecha/compañía.
        try:
            fecha_rate = fields.Date.to_date(fecha) if fecha else fields.Date.context_today(self)
            rates = usd._get_rates(company, fecha_rate)
            if rates and rates.get(usd.id):
                return 1 / rates[usd.id]
        except Exception:
            pass

        return company.currency_id_dif.inverse_rate or 1.0

    @api.model_create_multi
    def create(self, vals_list):
        _logger.debug("[DUAL] Entering AccountMove.create with vals_list=%s", vals_list)
        moves = super().create(vals_list)
        for move, vals in zip(moves, vals_list):
            j = move.journal_id
            is_fx_journal = bool(getattr(j, 'is_exchange_diff_journal', False) or
                                getattr(j, 'is_fx_diff_journal', False))

            if is_fx_journal and move.move_type == 'entry':
                # Asientos de DIF CAMBIO
                if move.tax_today != 0.0:
                    move.with_context(skip_tax_today_update=True).write({'tax_today': 0.0})
                move.line_ids.with_context(skip_dual_sync=True).write({
                    'tax_today': 0.0,
                    'debit_usd': 0.0,
                    'credit_usd': 0.0,
                    'balance_usd': 0.0,
                })
                _logger.info("[DUAL] create(): move %s (FX diff) -> tasa=0 y dual=0", move.id)

            else:
                # Documentos normales (facturas/pagos)
                if move.move_type in ('out_refund', 'in_refund'):
                    continue

                # Si show_usd es False, forzar tasa=0 y valores USD=0
                if not move.show_usd:
                    if move.tax_today != 0.0:
                        move.with_context(skip_tax_today_update=True).write({'tax_today': 0.0})
                    move.line_ids.write({
                        'tax_today': 0.0,
                        'debit_usd': 0.0,
                        'credit_usd': 0.0,
                        'balance_usd': 0.0,
                        'amount_residual_usd': 0.0,
                    })
                    _logger.info("[DUAL] create(): move %s (show_usd=False) -> tasa=0 y dual=0", move.id)
                    continue

                tax_today_in_vals = vals.get('tax_today')
                if tax_today_in_vals and tax_today_in_vals not in (0.0, 1.0):
                    continue

                fecha = move._fecha_para_tax_today()
                tasa = move._get_tasa_usd_by_date(fecha, move.company_id)
                if move.tax_today != tasa:
                    _logger.info("[DUAL] create() move=%s setting tax_today %s -> %s", move.id, move.tax_today, tasa)
                    # CRITICAL: check_move_validity=False prevents _check_balanced from running
                    # here, before price_unit lines are updated and payment_term is rebalanced
                    move.with_context(skip_tax_today_update=True, check_move_validity=False).write({'tax_today': tasa})

                if move.move_type == 'out_invoice' and move.currency_id == move.company_currency_id:
                    usd = self.env.ref('base.USD', raise_if_not_found=False)
                    tax_today = float(move.tax_today or 0.0)
                    if usd and tax_today > 0:
                        lines_to_update = []
                        for line in move.invoice_line_ids:
                            if line.display_type in ('line_section', 'line_note'):
                                continue
                            usd_unit = 0.0
                            if hasattr(line, 'sale_line_ids') and line.sale_line_ids:
                                sale_line = line.sale_line_ids[0]
                                order = sale_line.order_id
                                if order and order.currency_id == usd:
                                    usd_unit = float(sale_line.price_unit or 0.0)
                                else:
                                    usd_unit = float(sale_line.ref_unit or 0.0)
                                    if not usd_unit and order and order.currency_id:
                                        order_date = order.date_order or fields.Date.context_today(order)
                                        try:
                                            from_curr = order.currency_id
                                            usd_unit = float(from_curr._convert(float(sale_line.price_unit or 0.0), usd, order.company_id, order_date) or 0.0)
                                        except Exception:
                                            pass
                            if not usd_unit and line.product_id:
                                product_usd = float(getattr(line.product_id, 'list_price_usd', 0.0) or 0.0)
                                if product_usd > 0 and abs(float(line.price_unit) - product_usd) <= 0.0001:
                                    usd_unit = product_usd
                            if usd_unit > 0:
                                new_price = move.currency_id.round(usd_unit * tax_today)
                                if float_compare(float(line.price_unit), new_price, precision_digits=2) != 0:
                                    lines_to_update.append((1, line.id, {'price_unit': new_price}))
                        if lines_to_update:
                            move.with_context(check_move_validity=False).write({'invoice_line_ids': lines_to_update})
                            if hasattr(move, '_compute_tax_totals'):
                                move._compute_tax_totals()
                            # Force flush so Odoo recomputes payment_term balance
                            # before the final _check_balanced validation runs
                            self.env.flush_all()

                # Asegurar recompute dual currency en líneas
                try:
                    _logger.debug("[DUAL] create(): move=%s preparing to recompute dual lines", move.id)
                    lines = move.line_ids
                    # CORRECCIÓN DE ERROR (AttributeError): Llamamos al método por su nombre
                    if not self.env.context.get('skip_dual_recompute'):
                        # Usamos update() o simplemente disparamos el compute de forma controlada
                        # pero SIN persistir (write) inmediatamente si es posible.
                        lines.with_context(skip_dual_recompute=True)._compute_balance_usd()

                        # Si los métodos _debit_usd y _credit_usd son decorados con @api.depends,
                        # Odoo los ejecutará solos. Si son métodos normales, llámalos así:
                        if hasattr(lines, '_debit_usd'):
                            lines._debit_usd()
                        if hasattr(lines, '_credit_usd'):
                            lines._credit_usd()

                    _logger.info("[DUAL] create(): move %s recompute dual OK", move.id)
                except Exception as e:
                    _logger.exception("[DUAL] create(): fallo recompute dual en move %s: %s", move.id, e)

        return moves


    def write(self, vals):
        # 1. Bypass rápido si ya estamos en un contexto de actualización controlada
        if self.env.context.get('skip_tax_today_update') or self.env.context.get('action_no_recompute'):
            return super().write(vals)

        # --- PROTECCIÓN PARA REGISTROS PUBLICADOS (Blindaje contra UserError) ---
        # Si detectamos que los registros ya están en 'posted', limpiamos el diccionario 'vals'
        # de campos que Odoo prohíbe modificar. Esto evita que errores de caché o de 
        # herencia inyecten campos como 'partner_id'.
        if any(m.state == 'posted' for m in self) and not self.env.context.get('skip_readonly_check'):
            # Lista de campos críticos que disparan el error en estado publicado
            fields_to_remove = ['partner_id', 'journal_id', 'date', 'move_type', 'line_ids']
            for field in fields_to_remove:
                vals.pop(field, None)
                
            # Si después de limpiar ya no hay nada que escribir, retornamos éxito
            if not vals:
                return True
        # -----------------------------------------------------------------------

        _logger.debug("[DUAL] Entering AccountMove.write on %s with vals=%s", self.ids, vals)
        
        # 2. Llamada al super original (con el diccionario vals ya limpio)
        res = super().write(vals)

        # 3. Lógica de re-cálculo de Moneda Dual
        for move in self:
            # Si la factura está publicada, NO ejecutamos re-cálculos automáticos
            # para evitar bloqueos de base de datos o recursividad infinita.
            if move.state == 'posted' and not self.env.context.get('skip_readonly_check'):
                continue

            j = move.journal_id
            is_fx_journal = bool(getattr(j, 'is_exchange_diff_journal', False) or
                                getattr(j, 'is_fx_diff_journal', False))

            if is_fx_journal and move.move_type == 'entry':
                # Limpieza para asientos de Diferencial Cambiario
                if abs(move.tax_today) > 0.000001:
                    super(AccountMove, move.with_context(skip_tax_today_update=True)).write({'tax_today': 0.0})
                
                move.line_ids.with_context(skip_dual_sync=True).write({
                    'tax_today': 0.0, 'debit_usd': 0.0, 'credit_usd': 0.0, 'balance_usd': 0.0,
                })
            else:
                # Documentos normales: Facturas y Pagos
                necesita_recalc = any(k in vals for k in ('date', 'invoice_date', 'move_type', 'company_id', 'tax_today', 'show_usd'))
                
                if not necesita_recalc or move.move_type in ('out_refund', 'in_refund'):
                    continue

                # Si show_usd es False, forzar tasa=0 y valores USD=0
                if not move.show_usd:
                    if move.tax_today != 0.0:
                        super(AccountMove, move.with_context(skip_tax_today_update=True)).write({'tax_today': 0.0})
                    move.line_ids.write({
                        'tax_today': 0.0,
                        'debit_usd': 0.0,
                        'credit_usd': 0.0,
                        'balance_usd': 0.0,
                        'amount_residual_usd': 0.0,
                    })
                    _logger.info("[DUAL] write(): move %s (show_usd=False) -> tasa=0 y dual=0", move.id)
                    continue

                fecha = move._fecha_para_tax_today(vals)
                tasa = move._get_tasa_usd_by_date(fecha, move.company_id)
                
                # Solo escribimos si la tasa realmente cambió (evita ciclos de escritura)
                if abs(move.tax_today - tasa) > 0.000001: 
                    _logger.info("[DUAL] write() move=%s actualizando tasa %s -> %s", move.id, move.tax_today, tasa)
                    move.with_context(skip_tax_today_update=True).write({'tax_today': tasa})

                # Re-cálculo de las líneas (debit_usd, credit_usd, etc.)
                try:
                    move.line_ids._debit_usd()
                    move.line_ids._credit_usd()
                    move.line_ids._compute_balance_usd()
                except Exception as e:
                    _logger.exception("[DUAL] write(): fallo recompute dual en move %s: %s", move.id, e)

        return res

    @api.depends('currency_id')
    def _same_currency(self):
        self.same_currency = self.currency_id == self.env.company.currency_id


    @api.onchange('tax_today')
    def _onchange_tax_today(self):
        """
        Bloquea la lógica de recalculo de factura si viene de SO (evita error 13.5k) 
        o está en proceso de publicación (evita cambio de IVA al postear).
        """
        _logger.debug("[DUAL] _onchange_tax_today triggered for moves=%s context_skip=%s", self.ids, {
            'skip_dual_currency_conversion': self.env.context.get('skip_dual_currency_conversion'),
            'skip_tax_today_onchange': self.env.context.get('skip_tax_today_onchange')
        })
        # BLOQUEO CRÍTICO: Si el flag está presente (creación desde SO en Bs o posteo), OMITIMOS la lógica de precios.
        if self._origin and round(self.tax_today, 6) == round(self._origin.tax_today, 6):
            return
        
        if self.env.context.get('skip_dual_currency_conversion') or self.env.context.get('skip_tax_today_onchange'):
            _logger.debug("[DUAL] _onchange_tax_today skipped because context flag present for moves=%s", self.ids)
            return 
        
        self = self.with_context(check_move_validity=False)
        for rec in self:
            rec.tax_today_edited = True
            
            if not rec.move_type == 'entry':
                # La lógica original que causó el error de Attribute y el IVA absurdo (al recalcular price_unit)
                # se elimina para facturas/recibos, obligando a Odoo a usar los valores estables.
                
                # El for de lineas y la línea que usaba price_unit_usd se eliminan aquí.

                _logger.debug("[DUAL] _onchange_tax_today running quick edit and tax totals for move=%s", rec.id)
                rec._onchange_quick_edit_total_amount()
                rec._onchange_quick_edit_line_ids()
                try:
                    rec._compute_tax_totals()
                except Exception:
                    _logger.exception("[DUAL] _onchange_tax_today: _compute_tax_totals failed for move=%s", rec.id)

                try:
                    rec.invoice_line_ids._compute_totals()
                except Exception:
                    _logger.exception("[DUAL] _onchange_tax_today: invoice_line_ids._compute_totals failed for move=%s", rec.id)
            else:
                # Lógica para asientos de diario (entry), donde SÍ se recalcula débito/crédito.
                for aml in rec.line_ids:
                    if aml.debit_usd > 0:
                        aml.with_context(check_move_validity=False).debit = aml.debit_usd * rec.tax_today
                    elif aml.debit_usd == 0 and aml.debit > 0:
                        aml.with_context(check_move_validity=False).debit_usd = (aml.debit / rec.tax_today) if rec.tax_today > 0 else 0
                    if aml.credit_usd > 0:
                        aml.with_context(check_move_validity=False).credit = aml.credit_usd * rec.tax_today
                    elif aml.credit_usd == 0 and aml.credit > 0:
                        aml.with_context(check_move_validity=False).credit_usd = (aml.credit / rec.tax_today) if rec.tax_today > 0 else 0

    @api.onchange('currency_id')
    def _onchange_currency(self):
        for rec in self:
            # 💥 CORRECCIÓN: Se eliminan referencias a l.price_unit_usd en _onchange_currency
            if rec.currency_id == self.env.company.currency_id:
                for l in rec.invoice_line_ids:
                    l.currency_id = rec.currency_id
                    # Lógica ajustada: asumiendo que el precio no debe cambiar si la moneda pasa a ser local
                    # y no tenemos price_unit_usd para recalcular.
                    l.price_unit = l.price_unit 
            else:
                for l in rec.invoice_line_ids:
                    l.currency_id = rec.currency_id
                    l.price_unit = l.price_unit # Mantener el precio actual
            
            for aml in rec.line_ids:
                aml.currency_id = rec.currency_id
                aml._compute_currency_rate()

    @api.onchange('invoice_line_ids', 'currency_id', 'tax_today')
    def _onchange_refresh_dual_amounts(self):
        """Mantiene actualizados los totales duales en la vista de factura borrador."""
        
        for rec in self:
            if rec.state != 'draft' or not rec.is_invoice(include_receipts=True):
                continue
            # En edición inline del one2many, tax_totals puede venir desfasado.
            # Para refresco inmediato tomamos siempre los valores de las líneas en memoria.
            product_lines = rec.invoice_line_ids.filtered(
                lambda l: l.display_type not in ('line_section', 'line_note')
            )
            amount_untaxed = sum(product_lines.mapped('price_subtotal')) if product_lines else 0.0
            amount_total = sum(product_lines.mapped('price_total')) if product_lines else 0.0
            amount_tax = amount_total - amount_untaxed

            rec._apply_dual_live_amounts(amount_untaxed, amount_tax, amount_total)

            if rec.currency_id != self.env.company.currency_id:
                rec.amount_untaxed_usd = amount_untaxed
                rec.amount_tax_usd = amount_tax
                rec.amount_total_usd = amount_total
                rec.amount_untaxed_bs = amount_untaxed * rec.tax_today
                rec.amount_tax_bs = amount_tax * rec.tax_today
                rec.amount_total_bs = amount_total * rec.tax_today
            else:
                rec.amount_untaxed_usd = (amount_untaxed / rec.tax_today) if rec.tax_today > 0 else 0.0
                rec.amount_tax_usd = (amount_tax / rec.tax_today) if rec.tax_today > 0 else 0.0
                rec.amount_total_usd = (amount_total / rec.tax_today) if rec.tax_today > 0 else 0.0
                rec.amount_untaxed_bs = amount_untaxed
                rec.amount_tax_bs = amount_tax
                rec.amount_total_bs = amount_total


    @api.onchange('amount_untaxed', 'amount_tax', 'amount_total', 'tax_today', 'currency_id')
    def _onchange_refresh_dual_from_move_totals(self):
        """Sincroniza dualidad usando los totales del move que la UI sí refresca al instante."""
        for rec in self:
            if rec.state != 'draft' or not rec.is_invoice(include_receipts=True):
                continue

            amount_untaxed = rec.amount_untaxed or 0.0
            amount_tax = rec.amount_tax or 0.0
            amount_total = rec.amount_total or 0.0

            rec._apply_dual_live_amounts(amount_untaxed, amount_tax, amount_total)

            if rec.currency_id != self.env.company.currency_id:
                rec.amount_untaxed_usd = amount_untaxed
                rec.amount_tax_usd = amount_tax
                rec.amount_total_usd = amount_total
                rec.amount_untaxed_bs = amount_untaxed * rec.tax_today
                rec.amount_tax_bs = amount_tax * rec.tax_today
                rec.amount_total_bs = amount_total * rec.tax_today
            else:
                rec.amount_untaxed_usd = (amount_untaxed / rec.tax_today) if rec.tax_today > 0 else 0.0
                rec.amount_tax_usd = (amount_tax / rec.tax_today) if rec.tax_today > 0 else 0.0
                rec.amount_total_usd = (amount_total / rec.tax_today) if rec.tax_today > 0 else 0.0
                rec.amount_untaxed_bs = amount_untaxed
                rec.amount_tax_bs = amount_tax
                rec.amount_total_bs = amount_total


    @api.depends('state', 'move_type')
    def _edit_trm(self):
        for rec in self:
            edit_trm = False
            if rec.move_type in ('in_invoice', 'in_refund', 'in_receipt', 'entry'):
                if rec.state == 'draft' and not rec.acuerdo_moneda:
                    edit_trm = True
                else:
                    edit_trm = False
            else:
                edit_trm = self.env.user.has_group('account_dual_currency.group_edit_trm')
                if edit_trm:
                    if rec.state == 'draft' and not rec.acuerdo_moneda:
                        edit_trm = True
                    else:
                        edit_trm = False
            # ##print(edit_trm)
            rec.edit_trm = edit_trm

    @api.depends(
        # 'line_ids.matched_debit_ids.debit_move_id.move_id.payment_id.is_matched',
        'line_ids.matched_debit_ids.debit_move_id.move_id.line_ids.amount_residual',
        'line_ids.matched_debit_ids.debit_move_id.move_id.line_ids.amount_residual_currency',
        # 'line_ids.matched_credit_ids.credit_move_id.move_id.payment_id.is_matched',
        'line_ids.matched_credit_ids.credit_move_id.move_id.line_ids.amount_residual',
        'line_ids.matched_credit_ids.credit_move_id.move_id.line_ids.amount_residual_currency',
        'line_ids.balance',
        'line_ids.currency_id',
        'line_ids.amount_currency',
        'line_ids.amount_residual',
        'line_ids.amount_residual_currency',
        'line_ids.payment_id.state',
        'line_ids.full_reconcile_id','tax_today', 'state',
        # nuevas dependencias USD
        'line_ids.balance_usd',
        'line_ids.amount_residual_usd',
        'show_usd',)
    def _compute_amount(self):
        # ODOO 19: El contexto es de solo lectura, se debe usar with_context()
        # Llamamos al super con el contexto apropiado antes del bucle
        super(AccountMove, self)._compute_amount()
        
        for move in self:
            # COMENTADO ODOO 19: No se puede asignar directamente el contexto
            # self.env.context = dict(self.env.context, tasa_factura=move.tax_today, calcular_dual_currency=True)
            total_residual = 0.0
            total = 0.0

            # Si show_usd es False, forzar valores USD a 0
            if not move.show_usd:
                move.amount_residual_usd = 0.0
                move.amount_total_signed_usd = 0.0
                continue
            for line in move.line_ids:
                if move.is_invoice(True):
                    if line.display_type == 'tax' or (line.display_type == 'rounding' and line.tax_repartition_line_id):
                        # Tax amount.
                        total += line.balance_usd
                    elif line.display_type in ('product', 'rounding'):
                        total += line.balance_usd
                    elif line.display_type == 'payment_term':
                        # Residual amount.
                        total_residual += line.amount_residual_usd
                else:
                    # === Miscellaneous journal entry ===
                    if line.debit:
                        total += line.balance
            move.amount_residual_usd = total_residual
            move.amount_total_signed_usd = abs(total) if move.move_type == 'entry' else -total
        # COMENTADO ODOO 19: No se puede asignar directamente el contexto
        # self.env.context = dict(self.env.context, tasa_factura=None, calcular_dual_currency=False)
    
    @api.depends(
        'invoice_line_ids.price_subtotal',
        'invoice_line_ids.price_total',
        'invoice_line_ids.display_type',
        'amount_untaxed',
        'amount_tax',
        'amount_total',
        'currency_id_dif',
        'currency_id',
        'tax_today')
    def _amount_all_usd(self):
        for rec in self:
            if rec.is_invoice(include_receipts=True):
                amount_untaxed = rec.amount_untaxed or 0.0
                amount_tax = rec.amount_tax or 0.0
                amount_total = rec.amount_total or 0.0

                if not amount_total and rec.invoice_line_ids:
                    product_lines = rec.invoice_line_ids.filtered(
                        lambda l: l.display_type not in ('line_section', 'line_note')
                    )
                    amount_untaxed = sum(product_lines.mapped('price_subtotal')) if product_lines else 0.0
                    amount_total = sum(product_lines.mapped('price_total')) if product_lines else 0.0
                    amount_tax = amount_total - amount_untaxed

                # En facturas posteadas, si hay desalineación entre totales UI y
                # saldos contables duales, priorizamos contabilidad para REF.
                if rec.state == 'posted' and rec.currency_id == self.env.company.currency_id and rec.tax_today > 0:
                    ledger_base_usd = 0.0
                    ledger_tax_usd = 0.0
                    for line in rec.line_ids:
                        if line.display_type == 'tax' or (line.display_type == 'rounding' and line.tax_repartition_line_id):
                            ledger_tax_usd += line.balance_usd
                        elif line.display_type in ('product', 'rounding'):
                            ledger_base_usd += line.balance_usd

                    ledger_untaxed_usd = abs(ledger_base_usd)
                    ledger_tax_abs_usd = abs(ledger_tax_usd)
                    ledger_total_usd = ledger_untaxed_usd + ledger_tax_abs_usd
                    ui_total_usd = (amount_total / rec.tax_today) if rec.tax_today else 0.0

                    if ledger_total_usd and abs(ui_total_usd - ledger_total_usd) > 0.05:
                        rec.amount_untaxed_usd = ledger_untaxed_usd
                        rec.amount_tax_usd = ledger_tax_abs_usd
                        rec.amount_total_usd = ledger_total_usd
                        rec.amount_untaxed_bs = ledger_untaxed_usd * rec.tax_today
                        rec.amount_tax_bs = ledger_tax_abs_usd * rec.tax_today
                        rec.amount_total_bs = ledger_total_usd * rec.tax_today
                        rec._apply_dual_live_amounts(rec.amount_untaxed_bs, rec.amount_tax_bs, rec.amount_total_bs)
                        continue

                if rec.currency_id != self.env.company.currency_id:
                    rec.amount_untaxed_usd = amount_untaxed
                    rec.amount_tax_usd = amount_tax
                    rec.amount_total_usd = amount_total
                    rec.amount_untaxed_bs = amount_untaxed * rec.tax_today
                    rec.amount_tax_bs = amount_tax * rec.tax_today
                    rec.amount_total_bs = amount_total * rec.tax_today
                else:
                    rec.amount_untaxed_usd = (amount_untaxed / rec.tax_today) if rec.tax_today > 0 else 0.0
                    rec.amount_tax_usd = (amount_tax / rec.tax_today) if rec.tax_today > 0 else 0.0
                    rec.amount_total_usd = (amount_total / rec.tax_today) if rec.tax_today > 0 else 0.0
                    rec.amount_untaxed_bs = amount_untaxed
                    rec.amount_tax_bs = amount_tax
                    rec.amount_total_bs = amount_total

                rec._apply_dual_live_amounts(amount_untaxed, amount_tax, amount_total)

            else:
                rec.amount_untaxed_usd = 0.0
                rec.amount_tax_usd = 0.0
                rec.amount_total_usd = 0.0
                rec.amount_untaxed_bs = 0.0
                rec.amount_tax_bs = 0.0
                rec.amount_total_bs = 0.0
                rec.amount_untaxed_usd_live = 0.0
                rec.amount_tax_usd_live = 0.0
                rec.amount_total_usd_live = 0.0
                rec.amount_untaxed_bs_live = 0.0
                rec.amount_tax_bs_live = 0.0
                rec.amount_total_bs_live = 0.0

    @api.depends('move_type', 'line_ids.amount_residual_usd')
    def _compute_payments_widget_reconciled_info_USD(self):
        for move in self:
            payments_widget_vals = {'title': _('Less Payment'), 'outstanding': False, 'content': []}
            total_pagado = 0
            if move.state == 'posted' and move.is_invoice(include_receipts=True):
                reconciled_vals = []
                reconciled_partials = move._get_all_reconciled_invoice_partials_USD()

                for reconciled_partial in reconciled_partials:
                    counterpart_line = reconciled_partial['aml']
                    if counterpart_line.move_id.ref:
                        reconciliation_ref = '%s (%s)' % (counterpart_line.move_id.name, counterpart_line.move_id.ref)
                    else:
                        reconciliation_ref = counterpart_line.move_id.name
                    if counterpart_line.amount_currency and counterpart_line.currency_id != counterpart_line.company_id.currency_id:
                        foreign_currency = counterpart_line.currency_id
                    else:
                        foreign_currency = False
                    total_pagado = total_pagado + float(reconciled_partial['amount'])
                    reconciled_vals.append({
                        'name': counterpart_line.name,
                        'journal_name': counterpart_line.journal_id.name,
                        'amount': reconciled_partial['amount'],
                        'currency_id': move.company_id.currency_id_dif.id if move.company_id.currency_id_dif else
                        move.company_id.currency_id.id,
                        'date': counterpart_line.date,
                        'partial_id': reconciled_partial['partial_id'],
                        'account_payment_id': counterpart_line.payment_id.id,
                        'payment_method_name': counterpart_line.payment_id.payment_method_line_id.name,
                        'move_id': counterpart_line.move_id.id,
                        'ref': reconciliation_ref,
                        # these are necessary for the views to change depending on the values
                        'is_exchange': reconciled_partial['is_exchange'],
                        'amount_company_currency': formatLang(self.env, abs(counterpart_line.balance_usd),
                                                              currency_obj=counterpart_line.company_id.currency_id_dif),
                        'amount_foreign_currency': foreign_currency and formatLang(self.env,
                                                                                   abs(counterpart_line.amount_currency),
                                                                                   currency_obj=foreign_currency)
                    })
                payments_widget_vals['content'] = reconciled_vals

            if payments_widget_vals['content']:
                move.invoice_payments_widget_usd = payments_widget_vals
                if total_pagado < move.amount_total_usd:
                    move.amount_residual_usd = move.amount_total_usd - total_pagado
                else:
                    move.amount_residual_usd = 0
                # if move.amount_residual_usd > 0:
                #     move.payment_state = 'partial'
                # else:
                #     move.payment_state = 'paid'
            else:
                move.amount_residual_usd = move.amount_total_usd
                move.invoice_payments_widget_usd = False

    @api.depends('move_type', 'line_ids.amount_residual_usd')
    def _compute_payments_widget_reconciled_info_bs(self):
        for move in self:
            if move.state != 'posted' or not move.is_invoice(include_receipts=True):
                move.invoice_payments_widget_bs = json.dumps(False)
                continue
            reconciled_vals = move._get_reconciled_info_JSON_values_bs()
            if reconciled_vals:
                info = {
                    'title': _('Less Payment'),
                    'outstanding': False,
                    'content': reconciled_vals,
                }
                move.invoice_payments_widget_bs = json.dumps(info, default=date_utils.json_default)
            else:
                move.invoice_payments_widget_bs = json.dumps(False)

    def _get_reconciled_info_JSON_values_bs(self):
        self.ensure_one()
        foreign_currency = self.currency_id if self.currency_id != self.company_id.currency_id else False

        reconciled_vals = []
        pay_term_line_ids = self.line_ids.filtered(lambda line: line.account_id.account_type in ('asset_receivable', 'liability_payable'))
        partials = pay_term_line_ids.mapped('matched_debit_ids') + pay_term_line_ids.mapped('matched_credit_ids')
        for partial in partials:
            counterpart_lines = partial.debit_move_id + partial.credit_move_id

            counterpart_line = counterpart_lines.filtered(lambda line: line not in self.line_ids)

            if counterpart_line.credit > 0:
                amount = counterpart_line.credit
            else:
                amount = counterpart_line.debit

            ref = counterpart_line.move_id.name
            if counterpart_line.move_id.ref:
                ref += ' (' + counterpart_line.move_id.ref + ')'

            reconciled_vals.append({
                'name': counterpart_line.name,
                'journal_name': counterpart_line.journal_id.name,
                'amount': partial.amount,
                'currency': self.currency_id_dif.symbol,
                'digits': [69, 2],
                'position': self.currency_id_dif.position,
                'date': counterpart_line.date,
                'payment_id': counterpart_line.id,
                'account_payment_id': counterpart_line.payment_id.id,
                'payment_method_name': counterpart_line.payment_id.payment_method_id.name if counterpart_line.journal_id.type == 'bank' else None,
                'move_id': counterpart_line.move_id.id,
                'ref': ref,
            })
        # ##print(reconciled_vals)
        return reconciled_vals

    def _get_all_reconciled_invoice_partials_USD(self):
        self.ensure_one()
        reconciled_lines = self.line_ids.filtered(lambda line: line.account_id.account_type in ('asset_receivable', 'liability_payable'))
        if not reconciled_lines:
            return {}

        query = '''
            SELECT
                part.id,
                part.exchange_move_id,
                part.amount_usd AS amount,
                part.credit_move_id AS counterpart_line_id
            FROM account_partial_reconcile part
            WHERE part.debit_move_id IN %s

            UNION ALL

            SELECT
                part.id,
                part.exchange_move_id,
                part.amount_usd AS amount,
                part.debit_move_id AS counterpart_line_id
            FROM account_partial_reconcile part
            WHERE part.credit_move_id IN %s
        '''
        self.env.cr.execute(query, [tuple(reconciled_lines.ids)] * 2)

        partial_values_list = []
        counterpart_line_ids = set()
        exchange_move_ids = set()
        for values in self.env.cr.dictfetchall():
            partial_values_list.append({
                'aml_id': values['counterpart_line_id'],
                'partial_id': values['id'],
                'amount': values['amount'],
                'currency': self.currency_id,
            })
            counterpart_line_ids.add(values['counterpart_line_id'])
            if values['exchange_move_id']:
                exchange_move_ids.add(values['exchange_move_id'])

        if exchange_move_ids:
            query = '''
                SELECT
                    part.id,
                    part.credit_move_id AS counterpart_line_id
                FROM account_partial_reconcile part
                JOIN account_move_line credit_line ON credit_line.id = part.credit_move_id
                WHERE credit_line.move_id IN %s AND part.debit_move_id IN %s

                UNION ALL

                SELECT
                    part.id,
                    part.debit_move_id AS counterpart_line_id
                FROM account_partial_reconcile part
                JOIN account_move_line debit_line ON debit_line.id = part.debit_move_id
                WHERE debit_line.move_id IN %s AND part.credit_move_id IN %s
            '''
            self.env.cr.execute(query, [tuple(exchange_move_ids), tuple(counterpart_line_ids)] * 2)

            for values in self.env.cr.dictfetchall():
                counterpart_line_ids.add(values['counterpart_line_id'])
                partial_values_list.append({
                    'aml_id': values['counterpart_line_id'],
                    'partial_id': values['id'],
                    'currency': self.company_id.currency_id,
                })

        counterpart_lines = {x.id: x for x in self.env['account.move.line'].browse(counterpart_line_ids)}
        for partial_values in partial_values_list:
            aml = counterpart_lines[partial_values['aml_id']]
            partial_values['aml'] = aml
            partial_values['is_exchange'] = aml.move_id.id in exchange_move_ids
            # Si es un movimiento de exchange, usamos el balance_usd del aml.
            if partial_values['is_exchange']:
                partial_values['amount'] = abs(aml.balance_usd)
            else:
                # Fallback: si en la tabla parcial no vino amount (o es 0), usamos aml.balance_usd
                # Esto evita que pagos en Bs no muestren su equivalente en USD en el widget.
                db_amount = partial_values.get('amount') or 0.0
                if not db_amount:
                    partial_values['amount'] = abs(getattr(aml, 'balance_usd', 0.0))
                else:
                    partial_values['amount'] = db_amount

        return partial_values_list

    # def js_assign_outstanding_line(self, line_id):
    #     lines = super(AccountMove, self).js_assign_outstanding_line(line_id)
    #     line_ids = self.env['account.move.line'].browse(line_id)
    #     line_ids._compute_amount_residual_usd()
    #     return lines

    # def js_assign_outstanding_line(self, line_id):
    #     ''' Called by the 'payment' widget to reconcile a suggested journal item to the present
    #     invoice.
    #
    #     :param line_id: The id of the line to reconcile with the current invoice.
    #     '''
    #     self.ensure_one()
    #     lines = self.env['account.move.line'].browse(line_id)
    #     l = self.line_ids.filtered(lambda line: line.account_id == lines[0].account_id and not line.reconciled)
    #     if abs(lines[0].amount_residual) == 0 and abs(lines[0].amount_residual_usd) > 0:
    #         if l.full_reconcile_id:
    #             l.full_reconcile_id.unlink()
    #         partial = self.env['account.partial.reconcile'].create([{
    #             'amount': 0,
    #             'amount_usd': l.move_id.amount_residual_usd if abs(
    #                 lines[0].amount_residual_usd) > l.move_id.amount_residual_usd else abs(
    #                 lines[0].amount_residual_usd),
    #             'debit_amount_currency': 0,
    #             'credit_amount_currency': 0,
    #             'debit_move_id': l.id,
    #             'credit_move_id': line_id,
    #         }])
    #         p = (lines + l).reconcile()
    #         (lines + l)._compute_amount_residual_usd()
    #         return p
    #     else:
    #         results = (lines + l).reconcile()
    #         if 'partials' in results:
    #             if results['partials'].amount_usd == 0:
    #                 monto_usd = 0
    #                 if abs(lines[0].amount_residual_usd) > 0:
    #
    #                     # ##print("1")
    #                     if abs(lines[0].amount_residual_usd) > self.amount_residual_usd:
    #                         # ##print("2")
    #                         monto_usd = self.amount_residual_usd
    #                     else:
    #                         # ##print("3")
    #                         monto_usd = abs(lines[0].amount_residual_usd)
    #                 results['partials'].write({'amount_usd': monto_usd})
    #                 lines[0]._compute_amount_residual_usd()
    #         return results

    def _compute_payments_widget_to_reconcile_info(self):
        for move in self:
            move.invoice_outstanding_credits_debits_widget = False
            move.invoice_has_outstanding = False

            if move.state != 'posted' \
                    or move.payment_state not in ('not_paid', 'partial') \
                    or not move.is_invoice(include_receipts=True):
                continue

            pay_term_lines = move.line_ids \
                .filtered(lambda line: line.account_id.account_type in ('asset_receivable', 'liability_payable'))

            domain = [
                ('account_id', 'in', pay_term_lines.account_id.ids),
                ('parent_state', '=', 'posted'),
                ('partner_id', '=', move.commercial_partner_id.id),
                ('reconciled', '=', False),
                '|','|', ('amount_residual', '!=', 0.0), ('amount_residual_usd', '!=', 0.0),('amount_residual_currency', '!=', 0.0),
            ]

            payments_widget_vals = {'outstanding': True, 'content': [], 'move_id': move.id}

            if move.is_inbound():
                domain.append(('balance', '<', 0.0))
                payments_widget_vals['title'] = _('Outstanding credits')
            else:
                domain.append(('balance', '>', 0.0))
                payments_widget_vals['title'] = _('Outstanding debits')

            for line in self.env['account.move.line'].search(domain):
                if line.debit == 0 and line.credit == 0 and not line.full_reconcile_id:
                    if abs(line.amount_residual_usd) > 0:
                        payments_widget_vals['content'].append({
                            'journal_name': line.ref or line.move_id.name,
                            'amount': 0,
                            'amount_usd': abs(line.amount_residual_usd),
                            'currency_id': move.currency_id.id,
                            'currency_id_dif': move.currency_id_dif.id,
                            'id': line.id,
                            'move_id': line.move_id.id,
                            'date': fields.Date.to_string(line.date),
                            'account_payment_id': line.payment_id.id,
                        })
                        continue
                if line.currency_id == move.currency_id:
                    # Same foreign currency.
                    amount = abs(line.amount_residual_currency)
                    amount_usd = abs(line.amount_residual_usd)
                else:
                    # Different foreign currencies.
                    amount = line.company_currency_id._convert(
                        abs(line.amount_residual),
                        move.currency_id,
                        move.company_id,
                        line.date,
                    )
                    amount_usd = abs(line.amount_residual_usd)

                if move.currency_id.is_zero(amount) and amount_usd == 0:
                    continue

                payments_widget_vals['content'].append({
                    'journal_name': line.ref or line.move_id.name,
                    'amount': amount,
                    'amount_usd': amount_usd,
                    'currency_id': move.currency_id.id,
                    'currency_id_dif': move.currency_id_dif.id,
                    'id': line.id,
                    'move_id': line.move_id.id,
                    'date': fields.Date.to_string(line.date),
                    'account_payment_id': line.payment_id.id,
                })

            if not payments_widget_vals['content']:
                continue
            ###print(payments_widget_vals)
            move.invoice_outstanding_credits_debits_widget = payments_widget_vals
            move.invoice_has_outstanding = True

    @api.model
    def _prepare_move_for_asset_depreciation(self, vals):
        move_vals = super(AccountMove, self)._prepare_move_for_asset_depreciation(vals)
        asset_id = vals.get('asset_id')
        move_vals['tax_today'] = asset_id.tax_today
        move_vals['currency_id_dif'] = asset_id.currency_id_dif.id
        #move_vals['asset_remaining_value_ref'] = move_vals['asset_remaining_value'] / asset_id.tax_today
        #move_vals['asset_depreciated_value_ref'] = move_vals['asset_depreciated_value'] / asset_id.tax_today
        return move_vals

    def js_remove_outstanding_partial(self, partial_id):
        ''' Called by the 'payment' widget to remove a reconciled entry to the present invoice.

        :param partial_id: The id of an existing partial reconciled with the current invoice.
        '''
        self.ensure_one()
        partial = self.env['account.partial.reconcile'].browse(partial_id)
        debit_move_id = partial.debit_move_id
        credit_move_id = partial.credit_move_id
        
        invoice_moves = (debit_move_id.move_id | credit_move_id.move_id).filtered(
            lambda m: m.is_invoice(include_receipts=True)
        )

        res = super(AccountMove, self).js_remove_outstanding_partial(partial_id)
        
        if debit_move_id and credit_move_id:
            debit_move_id._compute_amount_residual_usd()
            credit_move_id._compute_amount_residual_usd()
            
        return res

    def generar_retencion_igtf(self):
        for rec in self:
            return {'name': _('Aplicar Retención IGTF'),
                    'type': 'ir.actions.act_window',
                    'res_model': 'generar.igtf.wizard',
                    'view_type': 'form',
                    'view_mode': 'form',
                    'target': 'new',
                    'domain': "",
                    'context': {
                            'default_invoice_id': rec.id,
                            'default_igtf_porcentage': rec.company_id.igtf_divisa_porcentage,
                            'default_tax_today': rec.currency_id_dif.inverse_rate,
                            'default_currency_id_dif': rec.currency_id_dif.id,
                            'default_currency_id_company': rec.company_id.currency_id.id,
                            'default_amount': rec.amount_residual_usd,
                        },
                    }


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _create_invoices(self, grouped=False, final=False, date=None):
        company_currency = self.env.company.currency_id
        
        # Bloquea la conversión/recalculo si la SO está en moneda de la compañía.
        if any(order.currency_id == company_currency for order in self):
            return super(SaleOrder, self.with_context(skip_dual_currency_conversion=True))._create_invoices(grouped, final, date)
            
        return super()._create_invoices(grouped, final, date)