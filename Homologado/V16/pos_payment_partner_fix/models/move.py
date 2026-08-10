from odoo import models, fields, api
import logging
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    usd_recalculado = fields.Boolean(string="USD recalculado", default=False)

    @api.model
    def cron_recalculate_usd_fields(self):
        lines = self.sudo().search([
            ('move_id.state', '=', 'posted'),
            ('move_id.journal_id.type', 'in', ['bank', 'cash']),
            #('move_id.journal_id.name', 'ilike', 'OPERACIONES VARIAS'),
            #('move_id.journal_id.name', 'ilike', 'PUNTO DE VENTA'),
            #('move_id.journal_id.name', 'ilike', 'INVENTARIO'),
            ('usd_recalculado', '=', False),
        ])

        for line in lines:
            try:
                line._compute_balance_usd()
                line._credit_usd()
                line._debit_usd()
                line.usd_recalculado = True
                _logger.info(
                    "Recalculado balance_usd, debit_usd y credit_usd para línea %s del asiento %s",
                    line.id, line.move_id.name
                )
            except ValidationError as ve:
                _logger.warning(
                    "Validación fallida en línea %s (Asiento %s): %s",
                    line.id, line.move_id.name, str(ve)
                )
            except Exception as e:
                _logger.warning(
                    "Error inesperado en línea %s (Asiento %s): %s",
                    line.id, line.move_id.name, str(e)
                )