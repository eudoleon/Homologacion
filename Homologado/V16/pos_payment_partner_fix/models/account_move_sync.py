import logging
from odoo import models, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.model
    def cron_sync_partner_in_pos_move_lines(self):
        aml_obj = self.env['account.move.line']
        lines_without_partner = aml_obj.sudo().search([
            ('parent_state', '=', 'posted'),
            ('partner_id', '=', False),
            ('journal_id.name', 'ilike', 'PUNTO DE VENTA'),
        ])

        moves_done = set()

        for line in lines_without_partner:
            move = line.move_id

            if move.id in moves_done or len(move.line_ids) != 2:
                continue

            try:
                line_with_partner = next((l for l in move.line_ids if l.partner_id), None)
                line_without_partner = next((l for l in move.line_ids if not l.partner_id), None)

                if line_with_partner and line_without_partner:
                    if line_without_partner.reconciled:
                        line_without_partner.remove_move_reconcile()

                    # Escribir partner_id
                    partner = line_with_partner.partner_id
                    line_without_partner.sudo().write({'partner_id': partner.id})

                    # Intentar reconciliar automáticamente
                    opposite_line = aml_obj.sudo().search([
                        ('id', '!=', line_without_partner.id),
                        ('account_id', '=', line_without_partner.account_id.id),
                        ('partner_id', '=', partner.id),
                        ('balance', '=', -line_without_partner.balance),
                        ('reconciled', '=', False),
                        ('parent_state', '=', 'posted'),
                    ], limit=1)

                    if opposite_line:
                        aml_obj.browse([line_without_partner.id, opposite_line.id]).reconcile()
                        _logger.info(
                            "Reconciliadas líneas %s y %s después de corregir partner en %s",
                            line_without_partner.id,
                            opposite_line.id,
                            move.name
                        )

                    _logger.info(
                        "Asiento %s corregido: Línea %s ahora tiene partner_id = %s (%s)",
                        move.name,
                        line_without_partner.id,
                        partner.id,
                        partner.name
                    )

                    moves_done.add(move.id)

            except Exception as e:
                _logger.warning(
                    "Error procesando asiento %s (ID: %s): %s",
                    move.name,
                    move.id,
                    str(e)
                )
                continue  # Sigue con el siguiente asiento
