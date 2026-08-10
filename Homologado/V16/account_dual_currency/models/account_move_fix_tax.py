import logging
from odoo import models, api, fields

_logger = logging.getLogger(__name__)

class AccountMoveFixTaxLines(models.Model):
    _inherit = 'account.move'

    @api.model
    def update_tax_and_recompute_usd_below_two(self):
        usd_currency = self.env.ref('base.USD')
        vef_currency = self.env.ref('base.VEF')

        # Buscar asientos publicados con tasa menor a 2
        moves = self.search([
            ('state', '=', 'posted'),
            ('tax_today', '<', 2.0),
        ])
        count_moves = 0
        count_lines = 0

        for move in moves:
            move_date = move.invoice_date or move.date
            if not move_date:
                _logger.warning("Asiento %s sin fecha válida, se salta", move.id)
                continue

            rate_dict = usd_currency.with_context(company_id=move.company_id.id)._get_rates(vef_currency, move_date)
            rate_value = list(rate_dict.values())[0] if rate_dict else None
            if not rate_value or rate_value < 0.01:
                _logger.warning("Asiento %s con tasa inválida para fecha %s: %s", move.id, move_date, rate_value)
                continue

            # Actualiza tax_today en el asiento
            move.tax_today = rate_value

            # Recalcula los campos USD en las líneas
            for line in move.line_ids:
                debit_usd = line.debit / rate_value if line.debit else 0.0
                credit_usd = line.credit / rate_value if line.credit else 0.0
                balance_usd = (line.debit - line.credit) / rate_value if (line.debit or line.credit) else 0.0

                line.write({
                    'debit_usd': debit_usd,
                    'credit_usd': credit_usd,
                    'balance_usd': balance_usd,
                })
                count_lines += 1

            count_moves += 1

        _logger.info("Actualizados %s asientos y %s líneas con tasa < 2 y valores USD recalculados.", count_moves, count_lines)
        return count_moves, count_lines

    @api.model
    def cron_delete_odoobot_moves(self):
        """
        Ubica todos los asientos donde alguna línea contable (account_move_line.name)
        contiene la cadena 'odoobot', los cambia a borrador (si no lo están) y los elimina.
        Registra en el log cada movimiento procesado.
        """
        # 1) Seleccionar todos los IDs de account_move cuyos lines.name contenga 'odoobot'
        self.env.cr.execute("""
            SELECT DISTINCT am.id
            FROM account_move am
            JOIN account_move_line aml ON aml.move_id = am.id
            WHERE aml.name ILIKE '%%odoobot%%'
        """)
        result = self.env.cr.fetchall()  # [(move_id1,), (move_id2,), ...]

        total = 0
        for (move_id,) in result:
            # 2) Cargar el record por ORM
            move = self.browse(move_id)
            try:
                # 3) Si no está en borrador, cambiar a borrador
                if move.state != 'draft':
                    move.button_draft()
                    _logger.info(
                        "🔄 Asiento ID %s: cambiado a borrador (antes '%s')",
                        move_id, move.state
                    )
                # 4) Eliminar el asiento
                move.unlink()
                total += 1
                _logger.info(
                    "❌ Asiento ID %s eliminado (contiene 'odoobot')",
                    move_id
                )
            except Exception as e:
                _logger.error(
                    "⚠️ Error al procesar asiento ID %s: %s", move_id, e
                )
                # Continuar con el siguiente aunque falle este

        _logger.info(
            "✅ Proceso completado: %s asientos con 'odoobot' eliminados.", total
        )
        return total

    @api.model
    def action_fix_all_inventory_lines_with_wrong_tax(self, force_all=False, date_from=None, date_to=None, journal_code='STJ', journal_name_hint='VALOR'):
        """
        Reasigna la tasa (tax_today) y recalcula montos en USD de todos los asientos de
        "VALORACIÓN DE INVENTARIO" publicados, utilizando SIEMPRE la fecha contable (am.date).

        Criterio por defecto (force_all=False):
          - Corrige asientos donde el tax_today del asiento o de alguna línea ∈ {NULL, 0, 1}
            (indicio de tasa errónea) o cuando los montos USD ≈ montos Bs.

        Parámetros opcionales:
          - force_all: si True, recalcula todas las líneas de los asientos del diario objetivo.
          - date_from / date_to (string 'YYYY-MM-DD' o date): acota por fecha contable (am.date).
          - journal_code / journal_name_hint: ayuda a ubicar el diario (por defecto código 'STJ' o nombre que contenga 'VALOR').
        """
        Company = self.env.company
        CurrencyUSD = Company.currency_id_dif
        _logger.info("🔍 Inicio corrección inventario | force_all=%s | date_from=%s | date_to=%s | code=%s | name_hint=%s", force_all, date_from, date_to, journal_code, journal_name_hint)

        # 0) Ubicar diario(s) objetivo(s)
        journal_domain = [('company_id', '=', Company.id)]
        if journal_code:
            journal_domain = ['|', ('code', '=', journal_code)] + journal_domain
        if journal_name_hint:
            journal_domain = ['|', ('name', 'ilike', journal_name_hint)] + journal_domain

        journals = self.env['account.journal'].search(journal_domain)
        if not journals:
            _logger.warning("⚠️ No se localizaron diarios con code=%s o name ILIKE %s en la compañía %s.", journal_code, journal_name_hint, Company.name)
        else:
            _logger.info("🧭 Diarios objetivo: %s", ", ".join([f"{j.code}/{j.name}" for j in journals]))

        # 1) Construir SQL dinámico para seleccionar candidatos
        params = []
        where_parts = ["am.state = 'posted'"]
        if journals:
            where_parts.append("am.journal_id = ANY(%s)")
            params.append(journals.ids)
        else:
            # Si no se encontró diario, intentar por nombre del asiento (prefijo del código)
            if journal_code:
                where_parts.append("am.name ILIKE %s")
                params.append(journal_code + '/%')

        # Rango de fechas opcional
        if date_from:
            where_parts.append("am.date >= %s")
            params.append(fields.Date.to_date(date_from))
        if date_to:
            where_parts.append("am.date <= %s")
            params.append(fields.Date.to_date(date_to))

        # Criterio de candidatos
        if not force_all:
            where_parts.append("(am.tax_today IS NULL OR am.tax_today IN (0,1) OR EXISTS (SELECT 1 FROM account_move_line aml WHERE aml.move_id = am.id AND (aml.tax_today IS NULL OR aml.tax_today IN (0,1) OR (ABS(COALESCE(aml.debit,0)-COALESCE(aml.debit_usd,0)) < 0.01 AND COALESCE(aml.debit,0) > 0) OR (ABS(COALESCE(aml.credit,0)-COALESCE(aml.credit_usd,0)) < 0.01 AND COALESCE(aml.credit,0) > 0))))")

        sql = f"""
            SELECT DISTINCT am.id, am.date
            FROM account_move am
            WHERE {' AND '.join(where_parts)}
        """
        self.env.cr.execute(sql, tuple(params))
        results = self.env.cr.fetchall()
        _logger.info("➡️ Asientos candidatos encontrados: %s", len(results))
        if results:
            _logger.info("🧾 Primeros IDs candidatos: %s", [r[0] for r in results[:10]])

        processed_moves = 0
        processed_lines = 0

        for move_id, move_date in results:
            if not move_date:
                _logger.warning("⚠️ Asiento ID %s sin fecha válida, se omite.", move_id)
                continue

            # Obtener tasa correcta para esa fecha
            rate_dict = CurrencyUSD._get_rates(Company, move_date)
            rate_value = rate_dict.get(CurrencyUSD.id)

            if not rate_value or rate_value in [0.0, 1.0]:
                _logger.warning("⚠️ Asiento ID %s: tasa inválida para fecha %s → %s", move_id, move_date, rate_value)
                continue

            new_rate = 1 / rate_value  # Confirmado: tasa técnica

            # 1. Actualizar tax_today en account_move
            self.env.cr.execute(
                "UPDATE account_move SET tax_today = %s WHERE id = %s",
                (new_rate, move_id)
            )

            # 2. Obtener líneas contables a corregir
            if force_all:
                self.env.cr.execute("""
                    SELECT id, debit, credit FROM account_move_line 
                    WHERE move_id = %s
                """, (move_id,))
            else:
                self.env.cr.execute("""
                    SELECT id, debit, credit FROM account_move_line 
                    WHERE move_id = %s AND (
                        tax_today IS NULL OR tax_today IN (0,1)
                        OR (ABS(COALESCE(debit,0) - COALESCE(debit_usd,0)) < 0.01 AND COALESCE(debit,0) > 0)
                        OR (ABS(COALESCE(credit,0) - COALESCE(credit_usd,0)) < 0.01 AND COALESCE(credit,0) > 0)
                    )
                """, (move_id,))
            lines = self.env.cr.fetchall()

            # 3. Recalcular y actualizar cada línea
            for line_id, debit, credit in lines:
                debit_usd = (debit / new_rate) if debit else 0.0
                credit_usd = (credit / new_rate) if credit else 0.0
                balance_usd = debit_usd - credit_usd

                line_obj = self.env['account.move.line'].browse(line_id)
                amount_residual_usd = 0.0
                reconciled = False

                if line_obj.account_id.reconcile or line_obj.account_id.account_type in ('asset_cash', 'liability_credit_card'):
                    matched_credit = sum(line_obj.matched_credit_ids.mapped('amount_usd'))
                    matched_debit = sum(line_obj.matched_debit_ids.mapped('amount_usd'))
                    amount_residual_usd = (debit_usd - credit_usd) - (matched_credit - matched_debit)
                    reconciled = abs(amount_residual_usd) < (line_obj.currency_id_dif.rounding or 0.01)

                self.env.cr.execute("""
                    UPDATE account_move_line 
                    SET 
                        tax_today = %s,
                        debit_usd = %s, 
                        credit_usd = %s,
                        balance_usd = %s,
                        amount_residual_usd = %s,
                        reconciled = %s
                    WHERE id = %s
                """, (
                    new_rate, debit_usd, credit_usd, balance_usd, amount_residual_usd, reconciled, line_id
                ))
                processed_lines += 1

            _logger.info("✔️ Asiento %s corregido. Tasa recalculada=%s Fecha=%s Líneas_afectadas=%s", move_id, new_rate, move_date, len(lines))
            processed_moves += 1

        # 4. Actualizar tax_today en líneas contables rezagadas
        self.env.cr.execute("""
            UPDATE account_move_line aml
            SET tax_today = am.tax_today
            FROM account_move am
            WHERE aml.move_id = am.id
            AND am.state = 'posted'
        """)

        self.env.cr.commit()

        # 5. Limpiar caché de reportes contables
        if 'account.report' in self.env:
            self.env['account.report'].clear_caches()
            _logger.info("🧼 Caché de reportes contables limpiado.")

        _logger.info("✅ Proceso finalizado. Asientos corregidos: %s | Líneas actualizadas: %s", processed_moves, processed_lines)


    @api.model
    def action_sync_credit_note_tax_from_reversed(self):
        Company = self.env.company
        # Rango de fechas: 1 de julio a 15 de julio de 2025 (inclusive)
        start_date = fields.Date.from_string('2025-07-01')
        end_date = fields.Date.from_string('2025-07-15')

        # Buscar notas de crédito (cliente y proveedor) con reversed_entry_id en el rango de fecha
        self.env.cr.execute("""
            SELECT am.id, COALESCE(am.invoice_date, am.date) AS effective_date, am.reversed_entry_id
            FROM account_move am
            WHERE am.state = 'posted'
            AND am.move_type IN ('out_refund', 'in_refund')
            AND COALESCE(am.invoice_date, am.date) BETWEEN %s AND %s
            AND am.reversed_entry_id IS NOT NULL
        """, (start_date, end_date))
        credit_notes = self.env.cr.fetchall()

        for credit_id, effective_date, reversed_id in credit_notes:
            credit = self.env['account.move'].browse(credit_id)
            original = self.env['account.move'].browse(reversed_id)

            if not original.exists():
                _logger.warning("⚠️ Nota de crédito %s tiene reversed_entry_id %s inexistente.", credit_id, reversed_id)
                continue

            source_tax_today = original.tax_today
            if source_tax_today in (None, 0.0):
                _logger.warning("⚠️ Nota de crédito %s: el asiento original %s tiene tax_today inválido (%s). Se omite.", credit_id, reversed_id, source_tax_today)
                continue

            # 1. Actualizar tax_today de la nota de crédito
            credit.write({'tax_today': source_tax_today})

            # 2. Actualizar tax_today en sus líneas
            line_domain = [('move_id', '=', credit_id)]
            lines = self.env['account.move.line'].search(line_domain)
            for line in lines:
                # Si tienes lógica adicional (ej. recálculo de campos en USD), se puede extender aquí.
                line.tax_today = source_tax_today

            _logger.info("✔️ Nota de crédito %s sincronizada con tax_today %s desde %s.", credit_id, source_tax_today, reversed_id)

        # 3. (Opcional) Limpiar caché de reportes si aplica
        if 'account.report' in self.env:
            self.env['account.report'].clear_caches()
            _logger.info("🧼 Caché de reportes contables limpiado.")

        # No se hace commit explícito si estás en flujo estándar; si es script fuera de transacción normal, podrías:
        # self.env.cr.commit()

    @api.model
    def action_correct_usd_credit_notes_to_vef(self):
        # Paso 1: Buscar NCs en USD del mes de Julio
        credit_notes = self.search([
            ('move_type', '=', 'out_refund'),
            ('state', '=', 'posted'),
            ('currency_id.name', '=', 'USD'),
            ('date', '>=', '2025-07-01'),
            ('date', '<=', '2025-07-31'),
        ])

        _logger.info("Total NC encontradas en USD para Julio: %s", len(credit_notes))

        for move in credit_notes:
            _logger.info("Procesando NC: %s", move.name)

            # Paso 2: Guardar tasa manualmente
            original_tax_rate = move.tax_today

            # Paso 3: Calcular nuevos precios en VEF
            new_lines_vals = []
            for line in move.invoice_line_ids:
                price_unit_vef = line.price_unit * original_tax_rate
                new_lines_vals.append((1, line.id, {
                    'price_unit': price_unit_vef,
                }))

            # Paso 4: Pasar a borrador
            move.button_draft()

            # Paso 5: Cambiar moneda y reasignar precios + tasa original
            currency_vef = self.env.ref('base.VEF')  # Cambia por el XML ID correcto si no es este
            move.write({
                'currency_id': currency_vef.id,
                'invoice_line_ids': new_lines_vals,
                'tax_today': original_tax_rate,
            })

            # Paso 6: Volver a publicar
            move.action_post()

            _logger.info("NC %s actualizada correctamente.", move.name)
        
    @api.model
    def action_reconcile_corrected_credit_notes(self):
        # Paso 1: Buscar NC corregidas (con reversed_entry_id y publicadas)
        credit_notes = self.search([
            ('move_type', '=', 'out_refund'),
            ('state', '=', 'posted'),
            ('currency_id.name', '=', 'VEF'),  # Ahora ya en VEF
            ('reversed_entry_id', '!=', False),
            ('date', '>=', '2025-07-01'),
            ('date', '<=', '2025-07-31'),
        ])

        _logger.info("Total NC corregidas para reconciliar: %s", len(credit_notes))

        for nc in credit_notes:
            original_invoice = nc.reversed_entry_id
            _logger.info("Procesando NC %s para conciliar con %s", nc.name, original_invoice.name)

            # Paso 2: Obtener líneas conciliables (misma cuenta, no conciliadas)
            nc_lines = nc.line_ids.filtered(lambda l: l.account_id.reconcile and not l.reconciled)
            inv_lines = original_invoice.line_ids.filtered(lambda l: l.account_id.reconcile and not l.reconciled)

            # Paso 3: Emparejar por cuenta y conciliar
            for account in set(nc_lines.mapped('account_id')):
                lines_to_reconcile = nc_lines.filtered(lambda l: l.account_id == account) | \
                                    inv_lines.filtered(lambda l: l.account_id == account)
                if len(lines_to_reconcile) >= 2:
                    lines_to_reconcile.reconcile()
                    _logger.info("Conciliadas líneas de cuenta %s en NC %s", account.code, nc.name)

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    @api.model
    def fix_balance_and_residual_usd(self):
        """
        Recalcula únicamente:
        - balance_usd
        - amount_residual_usd
        Para todos los apuntes de asientos en estado 'posted'.
        """
        apuntes = self.search([
            ('move_id.state', '=', 'posted'),
        ])

        total = len(apuntes)
        actualizados = 0

        for line in apuntes:
            try:
                # Recalcular balance_usd
                line.balance_usd = (line.debit_usd or 0.0) - (line.credit_usd or 0.0)

                # Recalcular residual con conciliaciones parciales
                reconciled_usd = sum(line.matched_credit_ids.mapped('amount_usd')) - \
                                 sum(line.matched_debit_ids.mapped('amount_usd'))

                line.amount_residual_usd = line.balance_usd - reconciled_usd

                actualizados += 1

            except Exception as e:
                _logger.warning(f"[FIX] Error en apunte ID {line.id} ({line.move_id.name}): {e}")

        _logger.info(f"[FIX] Se actualizaron {actualizados} de {total} apuntes recalculando solo balance_usd y amount_residual_usd.")
        return True

class AccountMoveFixTaxWrapper(models.Model):
    _inherit = 'account.move'

    @api.model
    def action_fix_all_inventory_lines_with_wrong_tax_force_all(self):
        """Wrapper para ejecutar la corrección forzada (todas las líneas) desde cron o botón."""
        _logger.info("🚀 Ejecutando corrección forzada (force_all=True) de inventario…")
        return self.action_fix_all_inventory_lines_with_wrong_tax(force_all=True)