from odoo import http
from odoo import _
from odoo.http import request

class BannerController(http.Controller):

    @http.route('/banner/status', type='http', auth='user', methods=['GET'])
    def banner_status(self):
        # Aquí podemos definir las condiciones bajo las cuales mostrar el banner.
        show_banner = True  # Este puede ser un parámetro de configuración, o una lógica personalizada.
        message = _("Período anterior sin cerrar")  # Mensaje del banner

        # Ejemplo de condiciones para mostrar el banner
        if show_banner:
            return request.make_json_response({
                'show_banner': True,
                'message': message,
            })
        return request.make_json_response({
            'show_banner': False
        })
