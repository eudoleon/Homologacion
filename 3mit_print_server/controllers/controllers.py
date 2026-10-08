from odoo import http
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)


class PrintServerController(http.Controller):

    @http.route('/pos/get_payment_method_data', type='jsonrpc', auth='user')
    def get_payment_method_data(self, name):
        method = request.env['pos.payment.method'].sudo().search([('name', '=', name)], limit=1)
        return {
            'dolar_active': method.dolar_active,
            'fiscal_print_code': method.fiscal_print_code,
        }

    @http.route('/api/imprimir/reporte_x', type='http', auth='public', methods=['GET'], csrf=False)
    def reporte_x(self, **kwargs):
        try:
            result = {"status": "ok", "message": "Reporte X impreso correctamente"}
            return http.Response(json.dumps(result), status=200, mimetype='application/json')
        except Exception as e:
            _logger.exception("Error al imprimir reporte X")
            result = {"status": "error", "message": "Error al imprimir reporte X: " + str(e)}
            return http.Response(json.dumps(result), status=200, mimetype='application/json')
