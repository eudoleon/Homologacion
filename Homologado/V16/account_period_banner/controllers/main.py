from odoo import http, fields
from odoo.http import request
from datetime import date, datetime
import calendar

class AccountBannerController(http.Controller):

    @http.route('/account/banner/status', type='json', auth='user')
    def banner_status(self):
        try:
            # Buscar el último registro de bloqueo fiscal (más reciente)
            lock_date_record = request.env['account.change.lock.date'].sudo().search([], limit=1, order='id desc')
            lock_date_obj = None
            if lock_date_record and lock_date_record.fiscalyear_lock_date:
                # Si fiscalyear_lock_date viene como string, convertirlo a objeto date
                if isinstance(lock_date_record.fiscalyear_lock_date, str):
                    lock_date_obj = fields.Date.from_string(lock_date_record.fiscalyear_lock_date)
                # Si es un datetime, convertirlo a date
                elif isinstance(lock_date_record.fiscalyear_lock_date, datetime):
                    lock_date_obj = lock_date_record.fiscalyear_lock_date.date()
                else:
                    lock_date_obj = lock_date_record.fiscalyear_lock_date

            # Obtener la fecha actual utilizando context_today
            today = fields.Date.context_today(request.env.user)
            if isinstance(today, str):
                today = fields.Date.from_string(today)

            # Calcular la fecha esperada de cierre fiscal: se espera el último día del mes anterior al mes actual.
            if today.month == 1:
                expected_year = today.year - 1
                expected_month = 12
            else:
                expected_year = today.year
                expected_month = today.month - 1

            last_day = calendar.monthrange(expected_year, expected_month)[1]
            expected_lock_date = date(expected_year, expected_month, last_day)

            # Mensaje de depuración (ver en el log del servidor)
            debug_message = f"lock_date_obj: {lock_date_obj}, expected_lock_date: {expected_lock_date}, today: {today}"
            print(debug_message)

            # Si la fecha registrada no coincide con la esperada, se muestra el banner.
            if lock_date_obj != expected_lock_date:
                return {
                    'show_banner': True,
                    'message': f'La fecha de cierre fiscal registrada ({lock_date_obj.strftime("%d/%m/%Y") if lock_date_obj else "No definida"}) no coincide con la fecha esperada ({expected_lock_date.strftime("%d/%m/%Y")}).'
                }
            
            # Si coinciden, no se muestra el banner.
            return {
                'show_banner': False,
                'lock_date': lock_date_obj.strftime('%d/%m/%Y')
            }

        except Exception as e:
            return {
                'show_banner': False,
                'error': str(e)
            }
