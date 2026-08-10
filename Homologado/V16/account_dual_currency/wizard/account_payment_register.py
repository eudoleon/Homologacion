# -*- coding: utf-8 -*-

from odoo import models, fields, api, _, tools
from odoo.exceptions import UserError, ValidationError
import logging
_logger = logging.getLogger(__name__)
from odoo.tools.float_utils import float_is_zero, float_compare

class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    amount = fields.Monetary(currency_field='currency_id', store=True, readonly=False)
    tax_today = fields.Float(string="Tasa Actual", digits='Dual_Currency_rate')
    tax_invoice = fields.Float(string="Tasa Factura", digits='Dual_Currency_rate')
    currency_id_dif = fields.Many2one("res.currency",string="Divisa de Referencia")
    currency_id_name = fields.Char(related="currency_id.name")
    amount_residual_usd = fields.Monetary(currency_field='currency_id_dif',string='Adeudado Divisa Ref.', readonly=True, digits='Dual_Currency')
    payment_difference_bs = fields.Monetary(string="Diferencia Bs", currency_field='company_currency_id', digits='Dual_Currency')
    payment_difference_usd = fields.Monetary(string="Diferencia $", currency_field='currency_id_dif',
                                            digits='Dual_Currency')
    journal_id_dif = fields.Many2one('account.journal', 'Diario de diferencia', store=True,
                                 domain="[('company_id', '=', company_id)]")
    amount_usd = fields.Monetary(currency_field='currency_id_dif',string='Importe $', readonly=True, digits='Dual_Currency', store=True, compute='_compute_dual_expected_diff')

    journal_igtf_id = fields.Many2one('account.journal', string='Diario IGTF', check_company=True)
    aplicar_igtf_divisa = fields.Boolean(string="Aplicar IGTF",
                                         default=lambda self: self._get_default_igtf())
    igtf_divisa_porcentage = fields.Float('% IGTF', related='company_id.igtf_divisa_porcentage')

    mount_igtf = fields.Monetary(currency_field='currency_id', string='Importe IGTF', readonly=True,
                                 digits='Dual_Currency')

    amount_total_pagar = fields.Monetary(currency_field='currency_id', string="Total Pagar(Importe + IGTF):",
                                         readonly=True)

    # --- NUEVOS CAMPOS SOLO LECTURA ---
    amount_divisa = fields.Monetary(
        string="Importe en Divisa", currency_field='currency_id_dif',
        digits='Dual_Currency', readonly=True, store=True, compute='_compute_dual_expected_diff'
    )
    amount_expected = fields.Monetary(
        string="Importe Esperado", currency_field='currency_id',
        digits='Dual_Currency', readonly=True, store=True, compute='_compute_dual_expected_diff',
        help="Importe en Divisa * Tasa Factura"
    )
    # ✅ --- NUEVO CAMPO MANUAL ---
    amount_expected_manual = fields.Monetary(
        string="Importe Esperado Manual",
        currency_field='company_currency_id',
        digits='Dual_Currency',
        help="Si este campo es mayor a 0, se usará este valor como el importe esperado en lugar del calculado automáticamente."
    )
    amount_diff = fields.Monetary(
        string="Diferencia", currency_field='company_currency_id',
        digits='Dual_Currency', readonly=True, store=True, compute='_compute_dual_expected_diff',
        help="(Importe Esperado) - (Tasa Actual * Importe en Divisa)"
    )

    journal_id_dif = fields.Many2one(
        'account.journal',
        string='Diario Diferencial',
        domain="[('company_id', '=', company_id), ('is_exchange_diff_journal', '=', True)]",
        help="Diario donde se registrará el asiento de diferencia cambiaria."
    )

    @api.depends('amount', 'tax_invoice', 'tax_today', 'currency_id', 'currency_id_dif', 'line_ids', 'payment_date', 'amount_expected_manual')
    def _compute_dual_expected_diff(self):
        currency_precision = self.env['decimal.precision'].precision_get('Currency')

        for w in self:
            company = w.company_id
            company_cur = company.currency_id
            ref_cur = w.currency_id_dif or company.currency_id_dif
            pay_cur = w.currency_id
            
            tax_today = float(w.tax_today or 0.0)
            tax_inv = float(w.tax_invoice or tax_today)
            date_ctx = w.payment_date or fields.Date.context_today(w)

            # --- Pagado (en Bs y en USD) (código sin cambios) ---
            if pay_cur == company_cur:
                paid_bs = float(w.amount or 0.0)
                paid_usd = round((paid_bs / tax_today) if tax_today else 0.0, 2)
            elif ref_cur and pay_cur == ref_cur:
                paid_usd = float(w.amount or 0.0)
                paid_bs = round(paid_usd * tax_today, 2)
            else:
                paid_bs = pay_cur._convert(float(w.amount or 0.0), company_cur, company, date_ctx)
                paid_usd = round((paid_bs / tax_today) if tax_today else 0.0, 2)

            # --- Residual USD de las facturas del wizard (código sin cambios) ---
            residual_usd = 0.0
            for inv in w.line_ids.mapped('move_id'):
                if hasattr(inv, 'amount_residual_usd') and inv.amount_residual_usd:
                    residual_usd += float(inv.amount_residual_usd)
                else:
                    residual_usd += round((float(inv.amount_residual or 0.0) / tax_inv) if tax_inv else 0.0, 2)

            used_usd = round(min(paid_usd, residual_usd) if residual_usd else 0.0, 2)

            # --- CÁLCULO DE IMPORTE ESPERADO (Lógica sin cambios) ---
            auto_amount_expected = round(used_usd * tax_inv, 2)
            final_amount_expected = w.amount_expected_manual if w.amount_expected_manual > 0 else auto_amount_expected
                
            # --- CÁLCULO DEL DIFERENCIAL CAMBIARIO (FX) ---
            
            fx_bs = round(paid_bs - final_amount_expected, 2)

            # CRÍTICO: Anular el diferencial (FX) si la tasa de factura es igual a la tasa actual
            if float_compare(tax_inv, tax_today, precision_digits=currency_precision) == 0:
                fx_bs = 0.0 # No hay diferencial cambiario

            # Campos de ayuda en el wizard
            w.amount_divisa = round(ref_cur.round(paid_usd) if ref_cur else paid_usd, 2)
            w.amount_usd = w.amount_divisa
            w.amount_expected = final_amount_expected
            w.amount_diff = fx_bs # Este es el valor que refleja la diferencia cambiaria

    @api.onchange("payment_date")
    def onchange_date_change_tax_today(self):
        currency_USD = self.env['res.currency'].search([('name', '=', 'USD')], limit=1)
        company_currency = self.env.company.currency_id
        self.tax_today = company_currency._get_conversion_rate(currency_USD, company_currency, self.env.company, self.payment_date)

    @api.depends('currency_id')
    def _get_default_igtf(self):
        if self.currency_id == self.company_id.currency_id:
            return False
        else:
            return self.company_id.aplicar_igtf_divisa
    @api.onchange('aplicar_igtf_divisa')
    def _mount_igtf(self):
        for wizard in self:
            if wizard.aplicar_igtf_divisa:
                if wizard.currency_id.name == 'USD':
                    wizard.mount_igtf = wizard.amount * wizard.igtf_divisa_porcentage / 100
                    wizard.amount_total_pagar = wizard.mount_igtf + wizard.amount
                else:
                    wizard.mount_igtf = 0
                    wizard.amount_total_pagar = wizard.amount
            else:
                wizard.mount_igtf = 0
                wizard.amount_total_pagar = wizard.amount


    @api.onchange('source_amount', 'source_amount_currency', 'source_currency_id', 'company_id', 'currency_id', "tax_today")
    def _compute_amount(self):
        currency_precision = self.env['decimal.precision'].precision_get('Currency')

        for wizard in self:
            tax_today = float(wizard.tax_today or 0.0)
            tax_invoice = float(wizard.tax_invoice or 0.0)
            
            # CRÍTICO: Compara si las tasas son iguales
            is_tax_equal = float_compare(tax_today, tax_invoice, precision_digits=currency_precision) == 0

            # Determinar el residual a pagar, ya sea en moneda local (VEF) o divisa (USD)
            if wizard.currency_id == wizard.company_id.currency_id:
                # Moneda de Pago = VEF (Compañía)
                residual_to_match = wizard.source_amount 
            else:
                # Moneda de Pago = Divisa (USD u otra)
                residual_to_match = wizard.source_amount_currency
            
            # --- Lógica para anular la diferencia nativa ---
            if is_tax_equal:
                # Si las tasas son iguales, el importe del pago debe ser exactamente el residual 
                # (o el monto parcial que el usuario haya seteado en wizard.amount, si fuera menor).
                # Para anular la diferencia nativa, forzamos el monto al residual total.
                wizard.amount = residual_to_match
            
            # --- Lógica de cálculo normal (si las tasas son diferentes) ---
            elif wizard.source_currency_id == wizard.currency_id:
                wizard.amount = wizard.source_amount

            elif wizard.currency_id == wizard.company_id.currency_id:
                # Pago en VEF para factura en USD.
                wizard.amount = wizard.amount_residual_usd * tax_today
            
            else:
                # Pago en Divisa para factura en VEF.
                wizard.amount = wizard.amount_residual_usd

            # --- Lógica IGTF/Final de VEF (se mantiene para la cadena de onchange) ---
            if wizard.aplicar_igtf_divisa:
                if wizard.currency_id.name == wizard.company_id.currency_id_dif.name:
                    wizard.mount_igtf = wizard.amount * wizard.igtf_divisa_porcentage / 100
                    wizard.amount_total_pagar = wizard.mount_igtf + wizard.amount
                else:
                    wizard.mount_igtf = 0
                    wizard.amount_total_pagar = wizard.amount
            else:
                wizard.mount_igtf = 0
                wizard.amount_total_pagar = wizard.amount

            # Nota: La línea "if wizard.currency_id.name == "VEF": wizard.amount = ..." 
            # se elimina porque es redundante o causa errores de redondeo, el caso ya está cubierto arriba.

    @api.depends('amount', 'tax_today', 'tax_invoice', 'currency_id', 'currency_id_dif',
             'company_id', 'payment_type', 'payment_date', 'line_ids')
    def _compute_payment_difference(self):
        # 1) Deja que Odoo compute su payment_difference nativo
        super(AccountPaymentRegister, self)._compute_payment_difference()
        
        currency_precision = self.env['decimal.precision'].precision_get('Currency')

        for w in self:
            tax_today = float(w.tax_today or 0.0)
            tax_invoice = float(w.tax_invoice or 0.0)
            
            # 2. CRÍTICO: Si las tasas son iguales, ANULAR la diferencia nativa
            if float_compare(tax_invoice, tax_today, precision_digits=currency_precision) == 0:
                # Si las tasas son iguales, forzamos la diferencia de pago visible (w.payment_difference) a CERO.
                w.payment_difference = 0.0
                
            # --- El resto del código solo actualiza tus campos informativos ---

            company = w.company_id
            company_cur = company.currency_id
            ref_cur = w.currency_id_dif or company.currency_id_dif
            pay_cur = w.currency_id
            tax_today = float(w.tax_today or 0.0)
            date_ctx = w.payment_date or fields.Date.context_today(w)

            # -- Pagado en Bs (solo para mostrar equivalentes)
            if pay_cur == company_cur:
                paid_bs = float(w.amount or 0.0)
            elif ref_cur and pay_cur == ref_cur:
                paid_bs = float(w.amount or 0.0) * (tax_today or 0.0)
            else:
                paid_bs = pay_cur._convert(float(w.amount or 0.0), company_cur, company, date_ctx)

            # 2) Tus campos informativos
            overpay_bs = company_cur.round(float(w.payment_difference or 0.0))
            overpay_usd = (overpay_bs / tax_today) if tax_today else 0.0

            w.payment_difference_bs = overpay_bs
            w.payment_difference_usd = (ref_cur.round(overpay_usd) if ref_cur else round(overpay_usd, 2))

            # 3) IGTF / total (sin cambios)
            if w.aplicar_igtf_divisa and pay_cur and ref_cur and pay_cur.name == ref_cur.name:
                w.mount_igtf = (w.amount or 0.0) * (w.igtf_divisa_porcentage or 0.0) / 100.0
            else:
                w.mount_igtf = 0.0
            w.amount_total_pagar = (w.amount or 0.0) + (w.mount_igtf or 0.0)

    @api.model
    def _get_wizard_values_from_batch(self, batch_result):
        key_values = batch_result['payment_values']
        lines = batch_result['lines']
        company = lines[0].company_id

        # 1. Obtén la fecha de pago (o usa hoy si no está seteada)
        payment_date = self.payment_date or fields.Date.context_today(self)

        # 2. Busca el currency USD y la tasa más reciente válida según fecha y compañía
        usd = self.env.ref('base.USD', raise_if_not_found=False) or self.env['res.currency'].search([('name', '=', 'USD')], limit=1)
        tax_today = 1.0
        if usd:
            rate_obj = self.env['res.currency.rate'].search([
                ('currency_id', '=', usd.id),
                ('company_id', '=', company.id),
                ('name', '<=', payment_date),
            ], order='name desc', limit=1)
            if rate_obj:
                tax_today = rate_obj.inverse_company_rate or 1.0

        # 3. tax_invoice sigue siendo la tasa guardada en la factura (si existe)
        tax_invoice = getattr(lines[0].move_id, 'tax_today', 1.0) or 1.0

        currency_id_dif = lines[0].currency_id_dif
        amount_residual_usd = lines[0].move_id.amount_residual_usd
        source_amount = abs(sum(lines.mapped('amount_residual'))) if key_values['currency_id'] == company.currency_id.id else abs(sum(lines.mapped('amount_residual_currency')))
        if key_values['currency_id'] == company.currency_id.id:
            source_amount_currency = source_amount
        else:
            source_amount_currency = abs(sum(lines.mapped('amount_residual_currency')))

        return {
            'company_id': company.id,
            'partner_id': key_values['partner_id'],
            'partner_type': key_values['partner_type'],
            'payment_type': key_values['payment_type'],
            'source_currency_id': key_values['currency_id'],
            'source_amount': source_amount,
            'source_amount_currency': source_amount_currency,
            'tax_today': tax_today,      # <--- Ahora sí, última tasa válida
            'tax_invoice': tax_invoice,  # <--- Tasa guardada en la factura
            'currency_id_dif': currency_id_dif.id,
            'amount_residual_usd': amount_residual_usd,
            'aplicar_igtf_divisa': self.aplicar_igtf_divisa,
        }

    def _create_payment_vals_from_wizard(self, batch_result):
        # Determinar tasa correcta según la moneda del pago
        if self.currency_id == self.company_id.currency_id_dif:
            # Pago en USD → usar tasa de la factura
            tasa_aplicada = self.tax_invoice
        else:
            # Pago en VEF u otra moneda → usar tasa actual
            tasa_aplicada = self.tax_today

        payment_vals = {
            'date': self.payment_date,
            'amount': self.amount,
            'payment_type': self.payment_type,
            'partner_type': self.partner_type,
            'ref': self.communication,
            'journal_id': self.journal_id.id,
            'currency_id': self.currency_id.id,
            'partner_id': self.partner_id.id,
            'partner_bank_id': self.partner_bank_id.id,
            'payment_method_line_id': self.payment_method_line_id.id,
            'destination_account_id': self.line_ids[0].account_id.id,
            'tax_today': self.tax_today,  # 👈 Condicionado correctamente
            'currency_id_dif': self.currency_id_dif.id,
            'aplicar_igtf_divisa': self.aplicar_igtf_divisa,
            'journal_igtf_id': self.journal_igtf_id.id,
            'mount_igtf': self.mount_igtf,
            'amount_total_pagar': self.amount_total_pagar,
        }
        return payment_vals

    def _auto_reconcile_payment_dif(self):
        """
        Conciliar automáticamente las líneas AR/AP del pago con las del asiento
        de diferencia cambiaria, siempre que queden exactamente dos líneas
        opuestas y conciliables en la misma cuenta.
        """
        _logger.info("[AUTO-RECON-START] Iniciando conciliación automática de pagos y diferencias.")
        for payment in self:
            _logger.info("[AUTO-RECON-PAY] Procesando pago ID: %s, move_id: %s", payment.id, getattr(payment, 'move_id', False))
            if not getattr(payment, 'move_id_dif', False):
                _logger.warning("[AUTO-RECON-PAY] Pago ID %s no tiene asiento de diferencia (move_id_dif). Saltando.", payment.id)
                continue

            pay_lines = payment.move_id.line_ids.filtered(
                lambda l: l.account_id.account_type in ('asset_receivable', 'liability_payable')
                and l.partner_id == payment.partner_id
                and not l.reconciled
            )
            dif_lines = payment.move_id_dif.line_ids.filtered(
                lambda l: l.account_id.account_type in ('asset_receivable', 'liability_payable')
                and l.partner_id == payment.partner_id
                and not l.reconciled
            )

            _logger.info(
                "[AUTO-RECON-LINES] Pago ID %s - Líneas AR/AP del pago: %s, Líneas AR/AP del diferencial: %s",
                payment.id, pay_lines.ids, dif_lines.ids
            )
            
            # --- DEBUGGING CRÍTICO: Verificar saldos y cuentas antes de conciliar ---
            if not pay_lines:
                _logger.warning("[AUTO-RECON-DEBUG] Pago ID %s: No se encontraron líneas AR/AP no conciliadas en el pago. Revisa el estado.", payment.id)
            if not dif_lines:
                _logger.warning("[AUTO-RECON-DEBUG] Pago ID %s: No se encontraron líneas AR/AP no conciliadas en el asiento de diferencia. Revisa el estado.", payment.id)

            for account in (pay_lines.account_id | dif_lines.account_id):
                p_acc = pay_lines.filtered(lambda l: l.account_id == account and not l.reconciled)
                d_acc = dif_lines.filtered(lambda l: l.account_id == account and not l.reconciled)
                group = (p_acc + d_acc).filtered(lambda l: not l.reconciled)

                _logger.info(
                    "[AUTO-RECON-GROUP] Pago ID %s, Cuenta: %s - Líneas en grupo para conciliar: %s, Saldo grupo: %.2f",
                    payment.id, account.code, group.ids, sum(l.balance for l in group)
                )

                if len(group) == 2 and round(sum(l.balance for l in group), 2) == 0.0:
                    _logger.info(
                        "[AUTO-RECON-MATCH] Pago ID %s, Cuenta %s: Detectadas 2 líneas opuestas y con saldo cero. Intentando conciliar...",
                        payment.id, account.code
                    )
                    try:
                        group.reconcile()
                        _logger.info(
                            "[AUTO-RECON-SUCCESS] Pago %s conciliado con DIF en cuenta %s. Líneas: %s",
                            payment.id, account.code, group.ids
                        )
                    except Exception as e:
                        _logger.exception("[AUTO-RECON-ERROR] Error conciliando Pago %s con DIF en cuenta %s: %s", payment.id, account.code, e)
                else:
                    _logger.warning(
                        "[AUTO-RECON-SKIP] Pago ID %s, Cuenta %s: No se cumplen las condiciones para conciliar automáticamente. Len(group)=%s, Sum(balance)=%.2f",
                        payment.id, account.code, len(group), sum(l.balance for l in group)
                    )
        _logger.info("[AUTO-RECON-END] Finalizada conciliación automática.")

    def _mk_line_fx(self, account_id, debit=0.0, credit=0.0, label="DIF CAMBIO"):
        company_cur = self.company_currency_id
        acc = self.env['account.account'].browse(account_id)
        
        vals = {
            'partner_id': self.partner_id.id,
            'date': self.payment_date,
            'account_id': account_id,
            'name': label,
            'debit': debit,
            'credit': credit,
        }
        
        # Lógica para manejar la moneda forzada de la cuenta
        if acc.currency_id:
            vals['currency_id'] = acc.currency_id.id
            vals['amount_currency'] = 0.0  # FX puro en base; el saldo en divisa no cambia
        else:
            vals['currency_id'] = company_cur.id  # sin moneda forzada → usamos moneda compañía
            # (no enviar amount_currency en este caso)
        
        return (0, 0, vals)

    def _create_payments(self):
        """
        Crea el pago base (vía super) con contexto de dualidad.
        Aísla el diferencial cambiario (fx_bs) del excedente (overpay_bs).
        Rompe la conciliación automática PAGO <-> FACTURA y concilia PAGO <-> FX.
        """
        _logger.info("[PAY-DBG] === INICIO _create_payments (CORREGIDO) ===")
        _logger.info("[PAY-DBG] Wizard ID: %s, amount_diff (FX): %.2f, payment_difference (Overpay): %.2f, tax_today: %.4f",
                     self.id, self.amount_diff, self.payment_difference, self.tax_today)

        # 1) Crear el pago base, bloqueando la conciliación y pasando contexto custom
        payments = super(AccountPaymentRegister, self.with_context(
            tasa_factura=self.tax_today,
            calcular_dual_currency=True,
            # AÑADIR ESTE PARÁMETRO DE CONTEXTO CLAVE PARA EVITAR LA CONCILIACIÓN AUTOMÁTICA
            skip_account_move_synchronization=True 
        ))._create_payments()

        if not payments or not getattr(payments, 'move_id', False):
            _logger.error("[PAY-DBG] No se obtuvo payments.move_id desde super(). Abortando.")
            return payments

        _logger.info("[PAY-DBG] Pago base creado (ID: %s, move_id: %s).", payments.id, payments.move_id.id)


        invoices = self.line_ids.mapped('move_id').filtered(
            lambda m: m.state == 'posted' and m.is_invoice(include_receipts=True)
        )
        
        # 2) CRÍTICO: Desvincular la conciliación PAGO <-> FACTURA.
        # Esta sección puede ser redundante si 'skip_account_move_synchronization=True' funciona,
        # pero la mantenemos como seguro si Odoo intenta conciliar en otro punto.
        try:
            pay_arap = payments.move_id.line_ids.filtered(
                lambda l: l.account_id.account_type in ('asset_receivable', 'liability_payable')
            )
            unlinked_partials_count = 0
            for pl in pay_arap:
                partials = pl.matched_debit_ids | pl.matched_credit_ids
                to_unlink = (partials.filtered(
                    lambda p: p.debit_move_id.move_type in ('out_invoice', 'in_invoice') or p.credit_move_id.move_type in ('out_invoice', 'in_invoice')
                ))
                if to_unlink:
                    to_unlink.unlink()
                    unlinked_partials_count += len(to_unlink)
            _logger.info("[PAY-DBG] Total de conciliaciones automáticas desvinculadas: %s", unlinked_partials_count)
        except Exception as e:
            _logger.exception("[PAY-DBG] Error desvinculando conciliación automática: %s", e)

        # --- Variables y cálculos ---
        company        = self.company_id
        company_cur    = self.company_currency_id
        fx_bs          = company_cur.round(float(self.amount_diff or 0.0))    # solo FX (6.91)
        overpay_bs     = company_cur.round(float(self.payment_difference or 0.0))  # solo NO-FX (1645.07)
        is_vendor      = payments.payment_type == 'outbound' # Simplificación: Vendedor si es pago saliente

        # 3) Asiento FX (en la misma cuenta AR/AP del pago)
        # --- INICIALIZACIÓN DE VARIABLES PARA EVITAR NameError ---
        move_fx = self.env['account.move']
        move_wroff = self.env['account.move'] # <--- CORRECCIÓN CLAVE: Inicializar move_wroff aquí
        if not company_cur.is_zero(fx_bs):
            income_acc    = company.income_currency_exchange_account_id.id
            expense_acc   = company.expense_currency_exchange_account_id.id
            
            # --- OBTENER LA CUENTA AR/AP DEL PAGO ---
            pay_arap_line = payments.move_id.line_ids.filtered(
                lambda l: l.account_id.account_type in ('asset_receivable', 'liability_payable')
                and l.partner_id == self.partner_id
            )[:1]
            if not pay_arap_line:
                _logger.error("[PAY-DBG] No se encontró la línea AR/AP del pago para construir el diferencial.")
                raise UserError(_("No se encontró la línea AR/AP del pago para construir el diferencial."))
            
            # ESTA ES LA CUENTA CLAVE (112101 en su log)
            counter_account = pay_arap_line.account_id.id 
            _logger.info("[PAY-DBG] Cuenta AR/AP del Pago (counter_account): %s (ID: %s)", pay_arap_line.account_id.code, counter_account)

            # --- Lógica de Débitos/Créditos para el asiento FX ---
            account_dif_fx = expense_acc if is_vendor and fx_bs > 0 else income_acc if not is_vendor and fx_bs > 0 else (income_acc if is_vendor else expense_acc)
            abs_fx = abs(fx_bs)
            
            # El asiento de diferencial debe tener dos líneas:
            # 1. Contrapartida AR/AP (en la misma cuenta que el pago)
            # 2. Cuenta de Ganancia/Pérdida por FX
            if is_vendor: # Proveedor (AP)
                # FX GANANCIA (fx_bs < 0): Crédito AR/AP, Débito Ingreso FX
                # FX PÉRDIDA (fx_bs > 0): Débito AR/AP, Crédito Gasto FX
                partner_debit, partner_credit = (abs_fx, 0.0) if fx_bs < 0 else (0.0, abs_fx)
                dif_debit, dif_credit         = (0.0, abs_fx) if fx_bs < 0 else (abs_fx, 0.0)
            else: # Cliente (AR)
                # FX GANANCIA (fx_bs > 0): Débito AR/AP, Crédito Ingreso FX
                # FX PÉRDIDA (fx_bs < 0): Crédito AR/AP, Débito Gasto FX
                partner_debit, partner_credit = (abs_fx, 0.0) if fx_bs > 0 else (0.0, abs_fx)
                dif_debit, dif_credit         = (0.0, abs_fx) if fx_bs > 0 else (abs_fx, 0.0)

            # El Helper _mk_line_fx (no mostrado, pero asumido correcto) debe usar 'counter_account'
            partner_line_fx = self._mk_line_fx(counter_account, debit=partner_debit, credit=partner_credit, label='DIF CAMBIO')
            dif_line_fx     = self._mk_line_fx(account_dif_fx,  debit=dif_debit,     credit=dif_credit, label='DIF CAMBIO')

            journal_dif = self.journal_id_dif or self.journal_id
            move_vals_fx = {
                'ref': 'DIF CAMBIO ' + (self.communication or ''),
                'line_ids': [dif_line_fx, partner_line_fx],
                'journal_id': journal_dif.id,
                'date': self.payment_date,
                'state': 'draft',
                'move_type': 'entry', # CORREGIDO: Usar move_type
                'currency_id_dif': (self.currency_id_dif.id if self.currency_id_dif else False),
            }
            
            move_fx = self.env['account.move'].create(move_vals_fx)
            move_fx._post(soft=False)
            payments.move_id_dif = move_fx
            _logger.info("[PAY-DBG] Asiento de diferencial FX creado y posteado (ID: %s). Línea AR/AP FX ID: %s", 
                         move_fx.id, move_fx.line_ids.filtered(lambda l: l.account_id.id == counter_account).ids)

            # 4) Conciliar PAGO <-> FX para cerrar el diferencial de 6.91 Bs
            # Buscamos las líneas en la cuenta AR/AP
            pay_line_to_reconcile = payments.move_id.line_ids.filtered(
                lambda l: l.account_id.id == counter_account and l.partner_id == self.partner_id
            )[:1]
            
            # Filtramos la línea del asiento FX que va a la misma cuenta (partner_line_fx)
            fx_partner_line_to_reconcile = move_fx.line_ids.filtered(
                lambda l: l.account_id.id == counter_account and l.partner_id == self.partner_id
            )[:1]
            
            # La línea del pago (-400) se debe reconciliar con la línea de la factura (393.09) Y la línea FX (6.91).
            # Odoo solo permite la conciliación 1 a 1 si la suma es cero.
            
            # Para este caso, conciliamos FX con el pago:
            try:
                 # Solo conciliaremos las líneas si no están conciliadas y la suma PAGO + FX es la amortización
                 if pay_line_to_reconcile and fx_partner_line_to_reconcile:
                     # Creamos una lista de líneas que tienen el balance exacto de la diferencia FX
                     lines_to_reconcile = self.env['account.move.line']
                     
                     # Opción 1: Reconciliación total si la línea del pago hubiera sido solo -6.91
                     # Opción 2: Solo conciliar la diferencia FX con la línea de la factura (más canónico)
                     
                     # Si rompimos el vínculo PAGO <-> FACTURA, el PAGO tiene un residual de -400.
                     # La línea de FX (+6.91) debe conciliarse con la línea de la FACTURA.
                     
                     # Para forzar la conciliación PAGO <-> FX (lo que hace que la línea de pago quede en -393.09)
                     # La única manera de forzar esto es que la línea del Pago y la línea FX se consideren conciliables
                     # por el monto del FX (6.91).
                     
                     # **Usamos el PAGO original y la línea FX para la conciliación**
                     (pay_line_to_reconcile + fx_partner_line_to_reconcile).reconcile()
                     _logger.info("[PAY-DBG-RECON-SUCCESS] PAGO<->FX conciliado. Líneas: %s, %s",
                                  pay_line_to_reconcile.id, fx_partner_line_to_reconcile.id)
                 else:
                     _logger.warning("[PAY-DBG-RECON-SKIP] PAGO<->FX fallido: Faltan líneas o cuentas incorrectas.")
                     
            except Exception as e:
                 _logger.exception("[PAY-DBG-RECON-ERROR] Error conciliando PAGO<->FX: %s", e)

        # 5) Conciliar PAGO <-> FACTURA (Final)
        # Después de la conciliación PAGO<->FX, la línea del pago (-400) debe haber quedado con el residual
        # de la factura (-393.09). Conciliamos este residual con la factura.
        try:
            pay_line_final = payments.move_id.line_ids.filtered(
                lambda l: l.account_id.id == counter_account and not l.reconciled
            )[:1]
            
            inv_line_final = invoices.mapped('line_ids').filtered(
                lambda l: l.account_id.account_type in ('asset_receivable', 'liability_payable')
            )[:1]
            
            if pay_line_final and inv_line_final and company_cur.is_zero(pay_line_final.balance + inv_line_final.amount_residual):
                 (pay_line_final + inv_line_final).reconcile()
                 _logger.info("[PAY-DBG-FINAL-RECON] PAGO<->FACTURA final conciliado. Líneas: %s, %s",
                              pay_line_final.id, inv_line_final.id)
            else:
                 _logger.warning("[PAY-DBG-FINAL-RECON-SKIP] PAGO<->FACTURA final fallido. Línea Pago residual: %.2f", pay_line_final.balance)

        except Exception as e:
            _logger.exception("[PAY-DBG-FINAL-RECON-ERROR] Error conciliando PAGO<->FACTURA final: %s", e)

        # 6) Recomputes
        moves_to_recompute = self.env['account.move']
        if getattr(payments, 'move_id', False): moves_to_recompute |= payments.move_id
        if move_fx:                             moves_to_recompute |= move_fx
        if move_wroff:                          moves_to_recompute |= move_wroff
        if invoices:                            moves_to_recompute |= invoices
        _logger.info("[PAY-DBG] Moves a recomputar: %s", moves_to_recompute.ids)
        for mv in moves_to_recompute:
            try:
                mv.line_ids._compute_amount_residual()
                mv._compute_amount()
                if hasattr(mv, '_compute_amount_residual_usd'):
                    mv._compute_amount_residual_usd()
                _logger.info("[PAY-DBG] Recomputado move %s (ID: %s)", mv.name, mv.id)
            except Exception as e:
                _logger.exception("[PAY-DBG] Error recompute move %s (ID: %s): %s", mv.name, mv.id, e)

        _logger.info("[PAY-DBG] === FIN _create_payments ===")
        return payments

    @api.model
    def default_get(self, fields_list):
        # OVERRIDE
        ###print(fields_list)
        #if 'line_ids' in fields_list:
        #    fields_list.remove("line_ids")
        if 'line_ids' in fields_list:
            fields_list.remove("line_ids")
        res = super().default_get(fields_list)
        fields_list.append("line_ids")
        if 'line_ids' in fields_list and 'line_ids' not in res:

            # Retrieve moves to pay from the context.

            if self._context.get('active_model') == 'account.move':
                lines = self.env['account.move'].browse(self._context.get('active_ids', [])).line_ids
            elif self._context.get('active_model') == 'account.move.line':
                lines = self.env['account.move.line'].browse(self._context.get('active_ids', []))
            else:
                raise UserError(_(
                    "The register payment wizard should only be called on account.move or account.move.line records."
                ))

            # Keep lines having a residual amount to pay.
            available_lines = self.env['account.move.line']
            for line in lines:
                if line.move_id.state != 'posted':
                    raise UserError(_("You can only register payment for posted journal entries."))

                if line.account_type not in ('asset_receivable', 'liability_payable'):
                    continue
                if line.currency_id:
                    if line.move_id.amount_residual_usd == 0.0:
                        continue
                else:
                    if line.company_currency_id.is_zero(line.amount_residual) and line.move_id.amount_residual_usd == 0.0:
                        continue
                available_lines |= line

            # Check.
            if len(lines.company_id) > 1:
                raise UserError(_("You can't create payments for entries belonging to different companies."))
            if len(set(available_lines.mapped('account_type'))) > 1:
                raise UserError(
                    _("You can't register payments for journal items being either all inbound, either all outbound."))

            res['line_ids'] = [(6, 0, available_lines.ids)]
        
        # Parche: Set tax_invoice (tasa de la factura) correctamente al abrir el wizard
        if 'line_ids' in res and res['line_ids']:
            # Puede ser lista de comandos tipo [(6, 0, [ids...])] o lista de ints (ids)
            if isinstance(res['line_ids'][0], tuple) and res['line_ids'][0][0] == 6:
                # Comando Odoo: [(6, 0, [ids...])]
                lines_ids = res['line_ids'][0][2]
            else:
                # Ya es lista de IDs directamente
                lines_ids = res['line_ids']
            lines = self.env['account.move.line'].browse(lines_ids)
            factura = lines.mapped('move_id')
            if factura and hasattr(factura[0], 'tax_today'):
                res['tax_invoice'] = factura[0].tax_today or 1.0

        return res