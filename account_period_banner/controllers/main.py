from odoo import http, fields
from odoo.http import request
from datetime import date, datetime
import calendar

class AccountBannerController(http.Controller):

    @http.route('/account/banner/status', type='json', auth='user')
    def banner_status(self):
        try:
            # Obtener la compañía activa del usuario actual
            company = request.env.company
            
            lock_date_obj = None
            # En Odoo 17+, la fecha de bloqueo general se suele llamar hard_lock_date o fiscalyear_lock_date.
            if hasattr(company, 'hard_lock_date') and company.hard_lock_date:
                lock_date_obj = company.hard_lock_date
            elif hasattr(company, 'fiscalyear_lock_date') and company.fiscalyear_lock_date:
                lock_date_obj = company.fiscalyear_lock_date
            elif hasattr(company, 'period_lock_date') and company.period_lock_date:
                lock_date_obj = company.period_lock_date

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
