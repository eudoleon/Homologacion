from odoo import http
import json
import logging

_logger = logging.getLogger(__name__)

@http.route('/pos/get_payment_method_data', type='json', auth='public') 
def get_payment_method_data(self, name):
    method = self.env['pos.payment.method'].search([('name', '=', name)], limit=1)
    return {
        'dolar_active': method.dolar_active, 
        'fiscal_print_code': method.fiscal_print_code
    }

@http.route('/api/imprimir/reporte_x', type='http', auth='none', methods=['GET'], csrf=False)
def reporte_x(self, **kwargs):
        try:
            # Aquí va la lógica para enviar el reporte X a la impresora.
            # Por ejemplo, podrías hacer una llamada a un servicio externo o procesar el reporte.
            result = {"status": "ok", "message": "Reporte X impreso correctamente"}
            return http.Response(json.dumps(result), status=200, mimetype='application/json')
        except Exception as e:
            _logger.exception("Error al imprimir reporte X")
            # Capturamos el error y devolvemos un JSON con el mensaje, pero con status 200.
            result = {"status": "error", "message": "Error al imprimir reporte X: " + str(e)}
            return http.Response(json.dumps(result), status=200, mimetype='application/json')
