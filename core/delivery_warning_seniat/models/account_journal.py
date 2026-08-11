from odoo import api, fields, models
from odoo.exceptions import UserError

class AccountChangeLockDate(models.TransientModel):
    _inherit = 'account.change.lock.date'

    warning_message = fields.Char(compute='_compute_warning_message')

    @api.depends('fiscalyear_lock_date')
    def _compute_warning_message(self):
        for record in self:
            warning, _orders_details = record._check_delivery_orders(record.fiscalyear_lock_date)
            record.warning_message = warning if warning else False

    @api.onchange('fiscalyear_lock_date')
    def _onchange_fiscalyear_lock_date_warning(self):
        if not self.fiscalyear_lock_date:
            return
        warning_msg, _orders_details = self._check_delivery_orders(self.fiscalyear_lock_date)
        if warning_msg:
            return {
                'warning': {
                    'title': 'ADVERTENCIA IMPORTANTE - SENIAT',
                    'message': warning_msg,
                }
            }

    def change_lock_date(self):
        # Send the notification when the user confirms the wizard action.
        for wizard in self:
            if wizard.fiscalyear_lock_date:
                wizard.send_email_if_pending_orders(wizard.fiscalyear_lock_date)
        return super().change_lock_date()

    @api.model
    def check_delivery_orders(self, fiscalyear_lock_date):
        warning_msg, orders_details = self._check_delivery_orders(fiscalyear_lock_date)
        return {
            'warning': warning_msg,
            'orders_details': [
                {
                    'name': name,
                    'date': fields.Date.to_string(fields.Date.to_date(scheduled_date)),
                }
                for name, scheduled_date in orders_details.items()
            ],
        }

    def send_email_if_pending_orders(self, date_str):
        date = fields.Date.to_date(date_str)
        if not date:
            return

        warning_msg, orders_details = self._check_delivery_orders(date)
        if warning_msg:
            self._send_email_to_seniat(date, orders_details)

    def _check_delivery_orders(self, date_str):
        date = fields.Date.to_date(date_str)
        if not date:
            return False, {}

        delivery_orders = self.env['stock.picking'].search([
            ('scheduled_date', '<=', date),
            ('picking_type_id.code', '=', 'outgoing'),
            ('sale_id', '!=', False),
        ])

        filtered_orders = []
        for picking in delivery_orders:
            if picking.state == 'done' and picking.sale_id.invoice_status != 'invoiced':
                filtered_orders.append(picking)
            elif picking.state != 'done' and picking.sale_id.invoice_status != 'invoiced':
                filtered_orders.append(picking)

        if filtered_orders:
            warning_msg = (
                "🔔Advertencia Importante:🔔 \n\n"
                "Antes de cerrar el mes, verifique que todas las Órdenes de Entrega hayan sido facturadas.\n\n"
                "Según el Art. 20 de la Providencia SNAT/2011/0071, deben facturarse en el mismo período. "
                "El incumplimiento podría generar sanciones.\n\n"
                f"⚠️ Existen {len(filtered_orders)} órdenes de entrega pendientes por entregar o sin facturar "
                f"en o antes del {date.strftime('%Y-%m-%d')}. "
                "Dicha acción será notificada al SENIAT ⚠️"
            )
            return warning_msg, {order.name: order.scheduled_date for order in filtered_orders}
        return False, {}

    def _send_email_to_seniat(self, date, orders_details):
        mail_template = self.env.ref('delivery_warning_seniat.mail_template_notify_seniat', raise_if_not_found=False)
        if not mail_template:
            raise UserError('Email template not found.')
        
        formatted_date = date.strftime("%Y-%m-%d")

        orders_details_list = [
            {
                'name': name,
                'date': fields.Date.to_string(fields.Date.to_date(scheduled_date)),
            }
            for name, scheduled_date in orders_details.items()
        ]
        
        ctx = {
            'date': formatted_date,
            'orders_details': orders_details_list
        }
        subject = f"Órdenes de Entrega Pendientes - {formatted_date} - {self.env.company.name}"
        mail_template.with_context(ctx).send_mail(self.id, force_send=True, email_values={
            'email_from': 'ing.andresecas@gmail.com',
            'email_to': 'andresecas150801@gmail.com',
            'subject': subject,
        })