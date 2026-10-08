# -*- coding: utf-8 -*-

from odoo import models, fields, api
import json


class pos_nota_credito(models.TransientModel):
    _name = 'pos.print.notacredito'
    _description = 'POS Print Nota de Credito'

    #
    numFactura = fields.Char('Número de Factura', default='', required=True)
    fechaFactura = fields.Char('Fecha de la Factura', required=True)

    def _default_serial(self):
        active_id = self.env.context.get('active_id')
        if active_id:
            return self.env['pos.order'].browse(active_id).session_id.config_id.printer_serial
        return False

    def _default_config(self):
        active_id = self.env.context.get('active_id')
        if active_id:
            return self.env['pos.order'].browse(active_id).session_id.config_id
        return False

    config_id = fields.Many2one(
        'pos.config', string='Point of Sale Configuration', required=True, default=_default_config)

    serialImpresora = fields.Char(
        'Serial de Impresora', required=True, default=_default_serial)
    printer_host = fields.Char('printer host')

    @api.model
    def getTicket(self, *args):
        order = self.env['pos.order'].browse(
            self.env.context.get('active_id', False))

        ticket = dict()
        # ticket['fechaFactura']=order.create_date.strftime('%Y-%m-%d %H:%s')
        ticket['fechaFactura'] = args[0].get('fechaFactura')
        ticket['nroFactura'] = args[0].get('numFactura')
        ticket['serial'] = args[0].get('serialImpresora')
        ticket['backendRef'] = order.name
        client_name = order.partner_id.display_name or ''
        idFiscalVal = ""
        
        id_fiscal = order.partner_id.vat
        if not id_fiscal and order.partner_id._fields.get('rif') and order.partner_id.rif:
            id_fiscal = order.partner_id.rif
        if not id_fiscal and order.partner_id._fields.get('identification_id') and order.partner_id.identification_id:
            id_fiscal = order.partner_id.identification_id
            
        if id_fiscal:
            clean_id = str(id_fiscal).strip()
            if '-' not in clean_id and clean_id.isdigit():
                nat = getattr(order.partner_id, 'nationality', 'V')
                clean_id = f"{nat}-{clean_id}"
            idFiscalVal = clean_id
            
        razon_ext = client_name

        ticket['razonSocial'] = razon_ext[:120]
        ticket['idFiscal'] = idFiscalVal

        ticket['direccion'] = order.partner_id.street or order.partner_id.city or "S/D"
        ticket['telefono'] = order.partner_id.phone or ""

        items = []
        for line in order.lines:
            item = dict()
            item['referencia_interna'] = line.product_id.default_code
            item['nombre'] = line.display_name
            item['cantidad'] = abs(line.qty)
            item['precio'] = line.price_unit
            if not line.tax_ids:
                item['impuesto'] = 0
            else:
                item['impuesto'] = abs(line.tax_ids[0].amount)

            item['descuento'] = abs(line.discount)
            item['comentario'] = line.customer_note or ""  # Añadir comentario aquí
            items.append(item)
        ticket['items'] = items

        pagos = []
        for payment in order.payment_ids:
            r = payment.payment_method_id
            pagos.append({
                "codigo": r.fiscal_print_code if r.fiscal_print_code else ("20" if r.dolar_active else "01"),
                "nombre": r.fiscal_print_name if r.fiscal_print_name else r.name,
                "monto": abs(payment.amount)
            })
        ticket["pagos"] = pagos

        comentarios = []
        note = getattr(order, 'note', '')
        if note:
            comentarios.append(note)
        ticket['comentarios'] = comentarios

        return {
            'printer_host': order.session_id.config_id.printer_host,
            'ticket': json.dumps(ticket)
        }
