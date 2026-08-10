# -*- coding: utf-8 -*-
import logging
import psycopg2
from odoo import models, fields

_logger = logging.getLogger(__name__)
LOCK_NOT_AVAILABLE = "55P03"  # código PG para "lock not available"

class PosSession(models.Model):
    _inherit = 'pos.session'

    contabilidad_generada = fields.Boolean(
        string="Contabilidad ya generada",
        default=False,
        help="Se marca cuando ya se ha generado la contabilidad para evitar duplicación."
    )

    # --- helpers ---
    def _lock_row_nowait(self, sid):
        """Bloqueo de fila para serializar el cierre de una sesión."""
        self.env.cr.execute(
            "SELECT id FROM pos_session WHERE id=%s FOR UPDATE NOWAIT",
            (sid,)
        )

    def _already_processed(self, session):
        """Idempotencia: evita repetir si ya está cerrada o marcada."""
        session.invalidate_recordset()
        return session.contabilidad_generada or session.state == 'closed'

    # --- parche principal ---
    def action_pos_session_close(self, balancing_account=False, amount_to_balance=0, bank_payment_method_diffs=None):
        result = None
        for session in self:
            # Fast check
            if self._already_processed(session):
                _logger.info("[POS-GUARD] %s ya estaba procesada. Salto.", session.name)
                continue

            # Lock NOWAIT: si otro worker la está cerrando, no repito
            try:
                self._lock_row_nowait(session.id)
            except Exception as e:
                if isinstance(e, psycopg2.OperationalError) or getattr(e, "pgcode", None) == LOCK_NOT_AVAILABLE:
                    _logger.warning("[POS-GUARD] Cierre concurrente detectado en %s. Me bajo.", session.name)
                    continue
                raise  # otras excepciones sí deben propagarse

            # Rechequeo tras tomar el lock (por si cambió el estado mientras tanto)
            if self._already_processed(session):
                _logger.info("[POS-GUARD] %s quedó procesada durante el lock. Nada que hacer.", session.name)
                continue

            # Camino feliz: cerrar y marcar
            res = super(PosSession, session).action_pos_session_close(
                balancing_account=balancing_account,
                amount_to_balance=amount_to_balance,
                bank_payment_method_diffs=bank_payment_method_diffs,
            )
            session.write({'contabilidad_generada': True})
            _logger.info("[POS-GUARD] Contabilidad marcada como generada para sesión POS: %s", session.name)
            result = res  # conserva el último resultado (comportamiento típico en Odoo)
        return result

    # Opcional: blindaje extra si alguien llama validate en lugar de close
    def action_pos_session_validate(self):
        """Redirige a close con el mismo guard."""
        return self.action_pos_session_close()
