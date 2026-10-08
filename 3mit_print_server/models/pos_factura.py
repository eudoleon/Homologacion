from odoo import models, fields, api
import json

class pos_nota_credito(models.TransientModel):
    _name = 'pos.print.factura'
    _description = 'POS Print Factura'

    def _default_config(self):
        active_id = self.env.context.get('active_id')
        if active_id:
            return self.env['pos.order'].browse(active_id).session_id.config_id
        return False

    config_id = fields.Many2one('pos.config', string='Point of Sale Configuration', default=_default_config)

    printer_host = fields.Char('printer host')

    @api.model
    def getTicket(self, *args):
        order_id = args[0] if args else self.env.context.get('active_id', False)
        order = self.env['pos.order'].browse(order_id)

        ticket = dict()
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
            
        ticket['razonSocial'] = client_name
        ticket['idFiscal'] = idFiscalVal

        ticket['direccion'] = order.partner_id.street or order.partner_id.city or "S/D"
        ticket['telefono'] = order.partner_id.phone or ""

        items = []
        for line in order.lines:
            item = dict()
            item['referencia_interna'] = line.product_id.default_code
            item['nombre'] = line.display_name
            item['cantidad'] = abs(line.qty)
            item['precio'] = abs(line.price_unit)
            if not line.tax_ids:
                item['impuesto'] = 0
            else:
                item['impuesto'] = abs(line.tax_ids[0].amount)

            item['descuento'] = abs(line.discount)
            item['comentario'] = line.customer_note or ""  # Añadir comentario aquí
            items.append(item)

        ticket['items'] = items
        payments = []
        for line in order.payment_ids:
            payment_method = line.payment_method_id
            item = {}
            item['codigo'] = payment_method.fiscal_print_code or '01'
            item['nombre'] = payment_method.fiscal_print_name or payment_method.name
            item['monto'] = line.amount 
            payments.append(item)

        ticket['pagos'] = payments

        ticket['comentarios'] = getattr(order, 'note', '')  # Añadir comentarios generales del pedido

        return {
            'printer_host': order.session_id.config_id.printer_host,
            'ticket': json.dumps(ticket)
        }