from datetime import timedelta
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class AccountFiscalLockChecker(models.Model):
    _name = "account.fiscal.lock.checker"
    _description = "Verificador de Bloqueo Fiscal"

    def _get_fiscal_lock_date(self):
        # Prefer fiscal lock date and fallback to tax lock date if needed.
        company = self.env.company
        return company.fiscalyear_lock_date or company.tax_lock_date

    def _notify_account_managers(self, title, message):
        group = self.env.ref("account.group_account_manager", raise_if_not_found=False)
        if not group or not group.users:
            return
        group.users.notify_danger(message=message, title=title, sticky=True)

    @api.model
    def check_fiscal_lock_cron(self):
        fiscal_lock_date = self._get_fiscal_lock_date()
        today = fields.Date.context_today(self)
        last_day_prev_month = today.replace(day=1) - timedelta(days=1)

        if not fiscal_lock_date or fiscal_lock_date < last_day_prev_month:
            message = _(
                """
                - Fecha de bloqueo fiscal: %s
                - Ultimo dia del mes anterior: %s
                - Antes de iniciar un nuevo periodo, debe cerrarse correctamente el periodo anterior.
                - Por favor, revise y complete el cierre correspondiente para evitar inconsistencias en los registros.
                """
            ) % (
                fiscal_lock_date.strftime("%d/%m/%Y") if fiscal_lock_date else _("No establecida"),
                last_day_prev_month.strftime("%d/%m/%Y"),
            )
            self._notify_account_managers(
                _("ADVERTENCIA: PERIODO ANTERIOR SIN CERRAR"),
                message,
            )
            _logger.warning(
                "Notificacion de bloqueo fiscal enviada a los gerentes contables."
            )
