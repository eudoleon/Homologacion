# -*- coding: utf-8 -*-

from odoo import models, fields, api
import logging
import re

_logger = logging.getLogger(__name__)

class PosSession(models.Model):
    _inherit = "pos.session"

    def _pos_ui_models_to_load(self):
        result = super()._pos_ui_models_to_load()
        result += ['pos.order']
        return result

    def _loader_params_pos_order(self):
        return {
            'search_params': {
                'fields': [
                    'rate_order',
                    'canPrintNC',
                    'canPrint',
                    'ticket_fiscal',
                    'serial_fiscal',
                    'fecha_fiscal',
                    'fiscal_editable',
                ],
            }
        }

    def _get_pos_ui_pos_order(self, params):
        return self.env['pos.order'].search_read(**params['search_params'])

    def _loader_params_res_partner(self):
        res = super(PosSession, self)._loader_params_res_partner()
        fields = res.get('search_params').get('fields')
        fields.extend(["vat", "identification_id", "rif"])
        res['search_params']['fields'] = fields
        return res


class PosOrder(models.Model):
    _inherit = 'pos.order'

    ticket_fiscal = fields.Char()
    serial_fiscal = fields.Char()
    fecha_fiscal = fields.Char()

    @api.depends('ticket_fiscal', 'amount_total', 'state', 'name', 'lines.qty', 'lines.refunded_orderline_id')
    def _compute_canPrintNC(self):
        for record in self:
            record.canPrintNC = False
            record.canPrint = False

            if record.isRefund():
                # Para reembolsos: mostrar Nota de Crédito si no se ha impreso aún
                if not record.ticket_fiscal:
                    record.canPrintNC = True
                    record.canPrint = False
            else:
                # Para ventas normales: mostrar Factura Fiscal si no se ha impreso y no está en borrador/cancelado
                if not record.ticket_fiscal and record.state not in ['draft', 'cancel']:
                    record.canPrint = True
                    record.canPrintNC = False

    canPrintNC = fields.Boolean(compute=_compute_canPrintNC)
    canPrint = fields.Boolean(compute=_compute_canPrintNC)

    @api.depends('amount_total', 'amount_tax', 'amount_paid', 'name', 'lines.qty', 'lines.refunded_orderline_id')
    def _compute_is_refund_order(self):
        for record in self:
            record.is_refund_order = bool(record.isRefund())

    is_refund_order = fields.Boolean(compute=_compute_is_refund_order)

    @api.depends('ticket_fiscal', 'amount_total', 'name', 'lines.qty', 'lines.refunded_orderline_id')
    def _compute_fiscal_editable(self):
        for record in self:
            record.fiscal_editable = (not record.ticket_fiscal) and (not record.isRefund())

    fiscal_editable = fields.Boolean(compute=_compute_fiscal_editable)

    def _order_fields(self, ui_order):
        res = super(PosOrder, self)._order_fields(ui_order)
        res['ticket_fiscal'] = ui_order.get('ticket_fiscal', False)
        res['serial_fiscal'] = ui_order.get('serial_fiscal', False)
        res['fecha_fiscal'] = ui_order.get('fecha_fiscal', False)
        return res

    def setTicket(self, ids=None, data=None):
        """
        Establece el ticket fiscal sólo en el pedido correspondiente.
        Soporta varias firmas RPC:
          - setTicket([order_id], data)
          - setTicket(False, data)
          - setTicket(data)  # algunos clientes envían el dict como primer arg
        Devuelve un dict con info del pedido actualizado para depuración.
        """
        try:
            _logger.info('setTicket called with ids=%s data=%s', ids, data)
        except Exception:
            pass

        # Caso donde el cliente manda el dict como primer argumento: setTicket(data)
        if data is None and isinstance(ids, dict):
            data = ids
            ids = None

        order = None

        # 1) Si se pasan ids desde el cliente, usar el primero
        if isinstance(ids, (list, tuple)) and ids:
            try:
                order = self.browse(ids[0])
            except Exception:
                order = None

        # 2) Si no hay order y data es dict, intentar identificar por orderUID/pos_reference/name
        if not order and isinstance(data, dict):
            order_uid = data.get('orderUID') or data.get('pos_reference') or data.get('name')
            if order_uid:
                # Preferir pedidos que aún no tengan ticket_fiscal
                domain_exact = ['|', ('pos_reference', '=', order_uid), ('name', '=', order_uid)]
                order = self.env['pos.order'].search(domain_exact + [('ticket_fiscal', '=', False)], limit=1)
                if not order:
                    order = self.env['pos.order'].search(domain_exact, limit=1)
                if not order:
                    domain_ilike = ['|', ('pos_reference', 'ilike', order_uid), ('name', 'ilike', order_uid)]
                    order = self.env['pos.order'].search(domain_ilike + [('ticket_fiscal', '=', False)], limit=1)
                if not order:
                    order = self.env['pos.order'].search(domain_ilike, limit=1)

        # 3) Si se llama sobre un registro concreto (self tiene id), usarlo
        if not order and self and getattr(self, 'id', False):
            order = self

        if not order:
            _logger.warning('setTicket: no order found for ids=%s data=%s', ids, data)
            return data

        # Actualizar sólo el pedido encontrado
        if isinstance(data, dict):
            vals = {
                'ticket_fiscal': data.get('nroFiscal'),
                'serial_fiscal': data.get('serial'),
                'fecha_fiscal': data.get('fecha'),
            }
            try:
                _logger.info('setTicket: writing %s to order id=%s name=%s', vals, order.id, order.name)
                order.write(vals)
                _logger.info('setTicket: write complete for order id=%s', order.id)
            except Exception as e:
                _logger.exception('setTicket: error writing ticket for order id=%s: %s', getattr(order, 'id', None), e)

            return {
                'order_id': order.id,
                'order_name': order.name,
                'ticket_fiscal': vals.get('ticket_fiscal'),
            }

        return data

    def _prepare_invoice_vals(self):
        res = super(PosOrder, self)._prepare_invoice_vals()
        if self.igtf_amount >= 0:
            line = self._prepare_igtf_invoice_line()
            inv_lines = res.get('invoice_line_ids')
            inv_lines.append((0, None, line))
            res.update({
                'invoice_line_ids': inv_lines,
                'pos_order_id': self.id,
            })
        return res

    def print_NC(self):
        origin = self._get_origin_order()
        # Preferir datos del pedido origen (factura afectada), si está disponible,
        # caer a valores del pedido actual si falta información.
        source = origin or self
        fecha = source.fecha_fiscal or self.fecha_fiscal or False
        num_factura = source.ticket_fiscal or self.ticket_fiscal or False
        serial = source.serial_fiscal or self.serial_fiscal or False
        return {
            'name': 'Nota de Crédito',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'pos.print.notacredito',
            'view_id': self.env.ref('3mit_print_server.view_print_nc').id,
            'target': 'new',
            'context': {
                'active_id': self.id,
                'default_numFactura': num_factura,
                'default_serialImpresora': serial,
                'default_fechaFactura': fecha,
            }
        }

    def print_factura(self):
        origin = self._get_origin_order()
        source = origin or self
        fecha = source.fecha_fiscal or self.fecha_fiscal or False

        return {
            'name': 'Factura',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'pos.print.factura',
            'view_id': self.env.ref('3mit_print_server.view_print_factura').id,
            'target': 'new',
            'context': {
                'active_id': self.id,
                'default_fechaFactura': fecha,
            }
        }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('amount_total', 0) < 0:
                vals['ticket_fiscal'] = False
                vals['serial_fiscal'] = False
                vals['fecha_fiscal'] = False
        return super().create(vals_list)

    def isRefund(self):
        self.ensure_one()

        # Indicadores monetarios con signo negativo (según implementación de cada POS).
        if self.amount_total < 0:
            return True
        if getattr(self, 'amount_tax', 0) < 0:
            return True
        if getattr(self, 'amount_paid', 0) < 0:
            return True

        # Algunas implementaciones guardan explícitamente una bandera de reembolso.
        if 'is_refund' in self._fields and self.is_refund:
            return True

        # Reembolsos POS estándar: líneas vinculadas al pedido origen.
        if self.lines and 'refunded_orderline_id' in self.lines._fields:
            if any(line.refunded_orderline_id for line in self.lines):
                return True

        # Compatibilidad con variantes donde el signo va en qty, precio o subtotal.
        if any(line.qty < 0 for line in self.lines):
            return True
        if any(getattr(line, 'price_unit', 0) < 0 for line in self.lines):
            return True
        if any(getattr(line, 'price_subtotal', 0) < 0 for line in self.lines):
            return True

        name = (self.name or '').upper()
        return any(tag in name for tag in ('REEMBOLSO', 'REFUND', 'DEVOLUCION'))

    def _get_origin_order(self):
        self.ensure_one()
        order = self.env['pos.order']

        refund_lines = self.lines.filtered(lambda line: getattr(line, 'refunded_orderline_id', False))
        if refund_lines:
            order = refund_lines.mapped('refunded_orderline_id.order_id')[:1]

        if not order:
            origin_name = self.origin_name(self.name)
            if origin_name:
                order = self.env['pos.order'].search([('name', '=', origin_name)], limit=1)

        return order

    def origin_name(self, name):
        if not name:
            return name
        ret = name.strip()
        ret = re.sub(r'^(REEMBOLSO|REFUND)\s*(DE|OF)?\s*', '', ret, flags=re.IGNORECASE)
        ret = re.sub(r'\s+', ' ', ret).strip()
        return ret


    def get_rate_order(self, pos_reference):
        var = self.env['pos.order'].search([('pos_reference', '=', pos_reference)], limit=1)
        if var:
            return var.rate_order
        else:
            # Usar la tasa de cambio predeterminada cuando no hay acceso a Internet
            currency_id = self.env['res.currency'].search([('name', '=', 'VEF')])
            
            # Si no se encuentra la tasa de cambio, puedes usar un valor predeterminado
            if not currency_id:
                # Tasa predeterminada, por ejemplo 1 (esto depende de tu configuración)
                return 1
            else:
                return currency_id.inverse_rate