from odoo import models, fields, api
from odoo.exceptions import UserError

class AccountWhMunicipal(models.Model):
    _name = "account.wh.municipal"
    _description = "Retención Municipal"

    # Campos principales
    name = fields.Char(string="Retención Municipal", required=True, copy=False, readonly=True, default="Nuevo")
    municipal_number_asignado = fields.Char(string="Número de Retención Municipal", readonly=True, copy=False)
    move_id = fields.Many2one('account.move', string="Factura", required=True, ondelete="cascade")
    partner_id = fields.Many2one('res.partner', related="move_id.partner_id", string="Proveedor", store=True)
    journal_id = fields.Many2one('account.journal', string="Diario", compute="_compute_journal", store=True, help="Entrada de diario")
    date = fields.Date(string="Fecha de Retención", required=True, default=fields.Date.context_today)
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('confirmed', 'Confirmado'),
        ('done', 'Publicado'),
        ('cancel', 'Cancelado'),
    ], string="Estado", default="draft")
    amount = fields.Monetary(string="Monto Retenido", currency_field="company_currency_id", readonly=True)
    company_currency_id = fields.Many2one('res.currency', related='move_id.company_currency_id', readonly=True)
    move_type = fields.Selection(
        related='move_id.move_type',
        store=True,
        string='Tipo de factura',
    )

    @api.depends("move_id")
    def _compute_journal(self):
        """Computa el diario automáticamente cuando se asigna una factura."""
        for record in self:
            record.journal_id = record._get_journal()

    @api.model
    def create(self, vals):
        if vals.get('name', 'Nuevo') == 'Nuevo':
            vals['name'] = self.env['ir.sequence'].next_by_code('account.wh.municipal.doc') or 'Nuevo'
        return super(AccountWhMunicipal, self).create(vals)

    def write(self, vals):
        """Recalcula el diario al modificar la factura"""
        res = super(AccountWhMunicipal, self).write(vals)
        if 'move_id' in vals:
            for record in self:
                record.journal_id = record._get_journal()
        return res

    def _get_journal(self):
        """Obtiene el diario de retención municipal desde el partner"""
        self.ensure_one()
        if not self.move_id:
            return False

        partner = self.move_id.partner_id
        move_type = self.move_id.move_type

        if move_type in ('out_invoice', 'out_refund'):
            return partner.sale_municipal_journal_id.id if partner.sale_municipal_journal_id else False
        elif move_type in ('in_invoice', 'in_refund'):
            return partner.purchase_municipal_journal_id.id if partner.purchase_municipal_journal_id else False
        return False

    def confirm_check(self):
        """Confirma la retención, genera el asiento contable y la registra en la factura, conciliando automáticamente"""
        for record in self:
            if record.state != 'draft':
                continue  # Evita procesar si ya ha sido confirmada

            invoice = record.move_id
            partner = invoice.partner_id

            if not invoice:
                raise UserError("No hay una factura asociada a la retención municipal.")

            # Obtener el diario de retención municipal
            withholding_journal = record._get_journal()
            if not withholding_journal:
                raise UserError(f"No se ha configurado un diario de retención municipal para {partner.name}.")

            withholding_journal = self.env['account.journal'].browse(withholding_journal)

            # Obtener la cuenta contable del diario
            retention_account = withholding_journal.default_municipal_account
            if not retention_account:
                raise UserError(f"El diario {withholding_journal.name} no tiene una cuenta de retención municipal configurada.")

            # Determinar si es factura normal o rectificativa
            is_refund = invoice.move_type in ('out_refund', 'in_refund')

            if invoice.move_type in ('out_invoice', 'out_refund'):
                counterparty_account = partner.property_account_receivable_id  # Cuenta por cobrar
            elif invoice.move_type in ('in_invoice', 'in_refund'):
                counterparty_account = partner.property_account_payable_id  # Cuenta por pagar
            else:
                raise UserError("El tipo de factura no es válido para retención municipal.")

            if not counterparty_account:
                raise UserError(f"El proveedor {partner.name} no tiene configurada la cuenta adecuada.")

            # Cambiar estado a 'confirmed'
            record.state = 'confirmed'

            # Generar número de retención municipal solo si es proveedor
            if invoice.move_type in ('in_invoice', 'in_refund'):
                sequence = self.env['ir.sequence'].next_by_code('account.wh.municipal.number') or '/'
            else:
                if not record.municipal_number_asignado:
                    raise UserError("Debe ingresar manualmente el número de comprobante municipal para facturas de cliente.")
                sequence = record.municipal_number_asignado


            # Factor para manejar notas de crédito (rectificativas)
            factor = -1 if is_refund else 1
            debit_amount = factor * record.amount
            credit_amount = factor * record.amount

            # Determinar si es cliente
            is_customer = invoice.move_type in ('out_invoice', 'out_refund')

            # Crear asiento contable para la retención
            move_vals = {
                'journal_id': withholding_journal.id,
                'date': record.date,
                'ref': f'Retención Municipal {sequence}',
                'line_ids': [
                    # Línea de retención municipal
                    (0, 0, {
                        'account_id': retention_account.id,
                        'partner_id': partner.id,
                        'debit': debit_amount if is_customer else 0.0,
                        'credit': 0.0 if is_customer else credit_amount,
                        'name': f'Retención Municipal {sequence}',
                    }),
                    # Línea de cuenta por cobrar/pagar
                    (0, 0, {
                        'account_id': counterparty_account.id,
                        'partner_id': partner.id,
                        'credit': credit_amount if is_customer else 0.0,
                        'debit': 0.0 if is_customer else debit_amount,
                        'name': f'Retención Municipal {sequence}',
                    }),
                ]
            }

            move = self.env['account.move'].create(move_vals)

            # --- Copiar la tasa de la factura al asiento de retención ---
            if move and move.exists():
                tax_to_copy = None
                if invoice.tax_today and invoice.tax_today != 1.0:
                    tax_to_copy = invoice.tax_today
                else:
                    # fallback: calcular según la fecha de la factura (invoice_date > date)
                    fecha = invoice.invoice_date or invoice.date
                    tax_to_copy = invoice._get_tasa_usd_by_date(fecha, invoice.company_id)
                if tax_to_copy and tax_to_copy != 1.0:
                    move.with_context(skip_tax_today_update=True).write({'tax_today': tax_to_copy})
            # ------------------------------------------------------------------
            move.action_post()  # Confirmar el asiento contable

            # **Conciliar automáticamente el asiento con la factura**
            invoice_lines = invoice.line_ids.filtered(lambda l: l.account_id == counterparty_account and not l.reconciled)
            move_lines = move.line_ids.filtered(lambda l: l.account_id == counterparty_account)

            if invoice_lines and move_lines:
                (invoice_lines + move_lines).reconcile()

            # Registrar la referencia del asiento en la retención
            record.write({
                'municipal_number_asignado': sequence,
                'state': 'done',
            })

            invoice.write({
                'wh_municipal_id': record.id,
                'municipal_number_asignado': sequence,
            })

            
    def action_cancel(self):
        """Cancela la retención anulando el asiento contable generado sin crear reversión."""
        for record in self:
            if record.state != 'done':
                record.state = 'cancel'
                continue  # Si no está en 'done', solo cambia el estado y sigue

            invoice = record.move_id
            partner = invoice.partner_id

            # Buscar el asiento contable de la retención
            move = self.env['account.move'].search([
                ('ref', '=', f'Retención Municipal {record.municipal_number_asignado}'),
                ('journal_id', '=', record.journal_id.id),
            ], limit=1)

            if move:
                # **1. Desconciliar el asiento original**
                for line in move.line_ids:
                    reconciled_lines = line.matched_debit_ids + line.matched_credit_ids
                    if reconciled_lines:
                        reconciled_lines.unlink()

                # **2. Cancelar el asiento contable original**
                if move.state == 'posted':
                    move.button_draft()
                    move.button_cancel()

            # **3. Marcar la retención como cancelada**
            record.state = 'cancel'

    def print_report_account_wh_municipal(self):
        return self.env.ref('l10n_ve_full.action_report_account_wh_municipal').report_action(self)