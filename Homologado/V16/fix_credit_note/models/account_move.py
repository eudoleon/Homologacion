from odoo import models, api, _, fields
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = 'account.move'

    def action_add_credit_note(self):
        self.ensure_one()

        # Solo mostrar advertencia si no viene del wizard
        if not self.env.context.get('skip_motivo_check'):
            credit_notes = self.env['account.move'].search([
                ('reversed_entry_id', '=', self.id),
                ('move_type', 'in', ['out_refund', 'in_refund']),
                ('state', '!=', 'cancel'),
            ])
            motivos = ', '.join(filter(None, credit_notes.mapped('x_studio_motivo_de_devolucin')))
            # Construir lista de NC asociadas y motivos
            credit_notes_info = []
            for nc in credit_notes:
                motivo = nc.x_studio_motivo_de_devolucin or ''
                if nc.state == 'draft':
                    nc_label = "PENDIENTE POR APROBACIÓN"
                else:
                    nc_label = nc.name
                credit_notes_info.append(f"{nc_label}: {motivo}")
            credit_notes_str = '\n'.join(credit_notes_info)
            if motivos:
                return {
                    'name': _('Advertencia de Motivos de NC'),
                    'type': 'ir.actions.act_window',
                    'res_model': 'credit.note.motivo.confirm',
                    'view_mode': 'form',
                    'target': 'new',
                    'context': {
                        'default_motivo_list': motivos,
                        'default_move_id': self.id,
                        'default_credit_notes': credit_notes_str,  # <-- aquí pasas la lista
                    }
                }

        if self.state != 'posted':
            raise UserError("Solo se pueden crear notas de crédito desde facturas publicadas")

        _logger.info("🧾 Generando nota de crédito desde factura %s", self.name)

        is_customer_invoice = self.move_type == 'out_invoice'
        is_vendor_invoice = self.move_type == 'in_invoice'

        if not (is_customer_invoice or is_vendor_invoice):
            raise UserError("Este tipo de documento no permite crear notas de crédito.")

        # Determinar tipo de nota de crédito y diario
        move_type_refund = 'out_refund' if is_customer_invoice else 'in_refund'
        journal_type = 'sale' if is_customer_invoice else 'purchase'
        journal_code_filter = 'NC' if is_customer_invoice else 'NCPRO'
        journal_name_filter = 'NOTAS DE CRÉDITO DE CLIENTE' if is_customer_invoice else 'NOTAS DE CRÉDITO DE PROVEEDOR'

        credit_note_journal = self.env['account.journal'].search([
            ('type', '=', journal_type),
            '|',
            ('code', 'ilike', journal_code_filter),
            ('name', 'ilike', journal_name_filter),
        ], limit=1)

        if not credit_note_journal:
            credit_note_journal = self.journal_id  # fallback al diario original

        today = fields.Date.context_today(self)
        tasa_original = self.tax_today

        _logger.info("📆 Fecha asignada a la nota de crédito: %s", today)
        _logger.info("💱 Tasa (tax_today) de la factura original: %s", tasa_original)

        # Crear valores base
        credit_note_vals = {
            'move_type': move_type_refund,
            'partner_id': self.partner_id.id,
            'invoice_user_id': self.invoice_user_id.id,
            'reversed_entry_id': self.id,
            'journal_id': credit_note_journal.id,
            'currency_id': self.currency_id.id,
            'date': today,
            'invoice_line_ids': [],
            'tax_today': tasa_original,
        }

        # Construir líneas copiadas
        lines = []
        for line in self.invoice_line_ids:
            lines.append((0, 0, {
                'product_id': line.product_id.id,
                'name': line.name,
                'quantity': line.quantity,
                'price_unit': line.price_unit,
                'tax_ids': [(6, 0, line.tax_ids.ids)],
                'account_id': line.account_id.id,
            }))
        credit_note_vals['invoice_line_ids'] = lines

        # Crear nota de crédito con contexto para evitar recalcular tasa
        credit_note = self.env['account.move'].with_context(
            skip_tax_today_update=True,
            credit_note_from_invoice=True,
            credit_note_tax_today=tasa_original,
            credit_note_date=today,
        ).create(credit_note_vals)

        # Forzar escritura de tasa y fecha sin disparar recálculo
        credit_note.with_context(skip_tax_today_update=True).write({
            'tax_today': tasa_original,
            'date': today,
        })

        _logger.info("✅ Tasa y fecha escritas en la nota de crédito (post-write): tax_today=%s, date=%s", credit_note.tax_today, credit_note.date)

        # Mensaje en el chatter
        credit_note.message_post(body=_(
            'Esta Nota de Crédito se generó a partir de la factura '
            '<a href="#" data-oe-model="account.move" data-oe-id="%s">%s</a>'
        ) % (self.id, self.name))

        return {
            'name': "Nota de Crédito creada",
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': credit_note.id,
            'target': 'current',
        }


    def action_post(self):
        _logger.info("action_post llamado para %s, contexto: %s", self.ids, self.env.context)
        for move in self:
            if self.env.context.get('skip_tax_today_update'):
                _logger.info("skip_tax_today_update detectado, no cambio tasa para move %s", move.id)
                continue

            if move.move_type in ('out_refund', 'in_refund'):
                _logger.info("No cambio tasa en nota de crédito %s", move.id)
                continue

            if not move.tax_today or move.tax_today == 1.0:
                fecha = move.invoice_date or move.date or fields.Date.context_today(self)
                move.tax_today = self._get_tasa_usd_by_date(fecha)
                _logger.info("Tasa actualizada a %s para move %s", move.tax_today, move.id)

        return super().action_post()


    @api.model
    def default_get(self, fields_list):
        defaults = super().default_get(fields_list)
        if self.env.context.get('credit_note_from_invoice'):
            if 'tax_today' in self._fields:
                defaults['tax_today'] = self.env.context.get('credit_note_tax_today')
            if 'date' in self._fields:
                defaults['date'] = self.env.context.get('credit_note_date')
        return defaults
