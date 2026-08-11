# -*- coding: utf-8 -*-
# ODOO 19: Módulo adaptado de Odoo 17 a Odoo 19
from odoo import api, fields, models, _, Command # type: ignore
from odoo.exceptions import UserError, ValidationError, AccessError # type: ignore

# ODOO 17: Importaciones no utilizadas - Comentadas en migración a Odoo 19
# Algunas de estas utilidades fueron movidas o eliminadas en Odoo 19
# from odoo.tools import ( # type: ignore
#     date_utils,
#     email_re,
#     email_split,
#     float_compare,
#     float_is_zero,
#     format_amount,
#     format_date,
#     formatLang,
#     frozendict,
#     get_lang,
#     is_html_empty,
#     sql
# )

import json
import requests


def _get_effective_tax_rate(taxes):
    """Get effective percent rate, expanding group taxes if needed."""
    stack = list(taxes)
    visited_ids = set()
    rate = 0.0

    while stack:
        tax = stack.pop()
        if tax.id in visited_ids:
            continue
        visited_ids.add(tax.id)

        if tax.amount_type == 'group':
            stack.extend(tax.children_tax_ids)
        elif tax.amount_type == 'percent' and tax.amount > 0:
            rate += tax.amount

    return round(rate, 2)


class AccountMove(models.Model):
    _inherit = 'account.move'
    
    factura_enviada  = fields.Boolean(default=False, store=True, readonly=True, copy=False)
    statusfactura = fields.Char(string='Status Factura', default="No Enviada", store=True, readonly=True, copy=False)
    fnoenviada = fields.Char(string='Status Factura', default="No Enviada", store=True, readonly=True, copy=False)
    fenviada = fields.Char(string='Status Factura', default="Enviada", store=True, readonly=True, copy=False)
    fanulada = fields.Char(string='Status Factura', default="Anulada", store=True, readonly=True, copy=False)
    aplicar_fdigital = fields.Boolean(string='Activar Facturacion Digital', help='Cuando sea Verdadero, la facturacion digital estará disponible', related="journal_id.facturaciond", readonly=True, store=True)
    correo_adicional = fields.Char(string='Correo Adicional', store=True, readonly=False, copy=False)
    urlfactura = fields.Char(string='URL Factura', store=True, readonly=True, copy=False)

    def button_cancel(self):
        super().button_cancel()
        if self.journal_id.facturaciond == True and self.factura_enviada == True:
            self.anulacion_facturacion_digital()
            self.factura_enviada = False
        
        # self.write({'auto_post': 'no', 'state': 'cancel'})

    # ODOO 17: Método duplicado - Comentado en migración a Odoo 19
    # def button_cancel(self):
    #     super().button_cancel()
    #     if self.factura_enviada == True:
    #         self.anulacion_facturacion_digital()

    def get_facturacion_digital(self):
         
        #condicion para determinar si es company , person 
        if self.partner_id.company_type == 'company':
            idtipocedulacliente = 3
        else:
            if self.partner_id.company_type == 'person' and  self.partner_id.nationality == 'P':
                idtipocedulacliente = 2
            else:
                idtipocedulacliente = 1
        
        #condicion para determinar si es factura , nota de debito o nota de credito 
        if self.move_type == 'out_invoice' and self.ref == False:
            idtipodocumento = 1
        elif self.move_type == 'out_invoice' and self.ref != False:
            idtipodocumento = 2
        elif self.move_type == 'out_refound':
            idtipodocumento = 3
            pass
        
        
        #move_type = 'out_refound  Nota de credito
        #move_type = 'out_invoice  factura
        #move_type = 'out_refound  Nota de credito
        
        ivag = False
        baseg = 0
        ivar = False
        baser = 0
        basea = 0
        ivaa = False
        exento = 0
        
        sequence =  self.env['ir.sequence'].search([('name', '=', 'Control Interno de Facturacion Digital')])
        nro_interno = str(sequence.number_next).zfill(8)

        
        for i in self.line_ids:
            if i.display_type == 'product':
                line_rate = _get_effective_tax_rate(i.tax_ids)
                #condicion para determinar los diferentes IVA
                if line_rate == 16:
                    ivag = 16
                    baseg = abs(i.price_subtotal) + baseg
                elif line_rate == 8:
                    ivar = 8
                    baser = abs(i.price_subtotal) + baser
                elif line_rate == 31:
                    ivaa = 31
                    basea = abs(i.price_subtotal) + basea
                elif line_rate == 0:
                    exento = i.price_subtotal + exento

        #determinar si el cliente tiene email o no
        if self.partner_id.email == False:
            sendmail = 0
        else:
            sendmail = 1

        # Determina el tipo de moneda
        if self.currency_id.name == 'VEF' or self.currency_id.name == 'VES':
            tipomoneda = 1
        elif self.currency_id.name == 'USD' or self.currency_id.name == '$':
            tipomoneda = 2
        elif self.currency_id.name == 'EURO' or self.currency_id.name == 'EUR' or self.currency_id.name == '€':
            tipomoneda = 3
        
        # Arreglos para el cuerpo de la factur y la forma de pago
        cuerpofactura = []
        formaspago = []
    
        
        for j in self.line_ids:
            
            if j.display_type == 'product':
                line_rate = _get_effective_tax_rate(j.tax_ids)
            
                cuerpofactura.append({
                    "codigo": j.ref if j.ref != False else j.id,
                    "descripcion": j.product_id.display_name,
                    "comentario": "",
                    "precio": j.price_unit,
                    "cantidad": j.quantity,
                    "tasa": line_rate,
                    "impuesto": ((j.quantity * j.price_unit) * (line_rate / 100)),
                    "descuento": 0.00,
                    "exento": "true" if line_rate == 0 else "false",
                    "monto": j.quantity * j.price_unit
                    
                    })
        
        # ODOO 17: invoice_payments_widget deprecado - Adaptado para Odoo 19
        # Acceso a pagos reconciliados mediante payment_state y reconciled payment moves
        if self.payment_state in ['in_payment', 'paid', 'partial']:
            # Obtener pagos reconciliados
            reconciled_payments = self.mapped('line_ids.matched_credit_ids.credit_move_id.move_id').filtered(
                lambda m: m.payment_id
            ) | self.mapped('line_ids.matched_debit_ids.debit_move_id.move_id').filtered(
                lambda m: m.payment_id
            )
            
            for payment in reconciled_payments:
                if payment.payment_id:
                    formaspago.append({
                        "forma": payment.payment_id.journal_id.name,
                        "valor": payment.payment_id.amount,
                    })
        
        # ODOO 17: Código original comentado - mantenido por referencia
        # if self.invoice_payments_widget != False:
        #     for pago in self.invoice_payments_widget['content']:
        #         formaspago.append({
        #             "forma": pago['journal_name'],
        #             "valor": pago['amount'],
        #         })

        url = self.company_id.url_fdigital + 'facturacion'
        token = {
            'Authorization': 'Bearer ' + self.company_id.token_fdigital.replace(' ', ''),
            'Content-Type': 'application/json'
        }
        DATA = {
            "rif": self.env.company.vat,
            "trackingid": "",
            "nombrecliente": self.partner_id.name,
            "rifcedulacliente": self.partner_id.vat,
            "emailcliente": self.partner_id.email,
            "idtipocedulacliente": idtipocedulacliente,
            "direccioncliente": self.partner_id.contact_address_complete,
            "telefonocliente": self.partner_id.phone,
            "idtipodocumento": idtipodocumento,
            "subtotal": self.amount_untaxed,
            "exento": exento,
            "tasag": ivag if ivag else 0,
            "baseg": baseg,
            "impuestog": (baseg * 16)/100,
            "tasar": ivar if ivar else 0,
            "baser": baser,
            "impuestor": (baser * 8)/100,
            "tasaigtf": self.company_id.igtf_divisa_porcentage,
            "baseigtf": 0.00,
            "impuestoigtf": 0.00,
            # "tasaa": 0.00,
            # "basea": 0.00,
            # "impuestoa": 0.00,
            "total": self.amount_total,
            "relacionado": "" if idtipodocumento == 1 else self.debit_origin_id.display_name,
            "sendmail": sendmail,
            # "sucursal": "001",
            "numerointerno": nro_interno,
            "tasacambio": self.tax_today,
            "tipomoneda": tipomoneda,
            "observacion": "",
            "cuerpofactura": cuerpofactura,
            "formasdepago": formaspago,
        }

        response = requests.post(
            url,
            headers=token,
            json=DATA
        )

        if response.status_code == 200:

            resp = response.json()
            numerodecontrol = resp['data']['numerodocumento']
            urlpdf = resp['data']['urlpdf']
            self.nro_ctrl = numerodecontrol
            self.urlfactura = urlpdf
            self.factura_enviada = True
            self.statusfactura = 'Enviada'
            sequence.number_next_actual = sequence.number_next_actual + sequence.number_increment

        else:
            message = response.text.split('"error":')
            message[1] = message[1].replace('{', '').replace('}', '')
            self.nro_ctrl = ''
            self.urlfactura = ''
            self.factura_enviada = False
            self.statusfactura = 'No Enviada'
            raise ValidationError(_(message[1]))
        
    def anulacion_facturacion_digital(self):

        numerocontrol = self.nro_ctrl 

        url = self.company_id.url_fdigital + 'anulacion'
        token = {
            'Authorization': 'Bearer ' + self.company_id.token_fdigital.replace(' ', ''),
            'Content-Type': 'application/json'
        }
        DATA = {
            "numerodocumento": numerocontrol,
            "observacion": "Se Anulo la Factura",
            "rif": "J-50643679-5",
        }

        response = requests.post(
            url,
            headers=token,
            json=DATA
        )

        if response.status_code == 200:
            self.factura_enviada = False
            self.statusfactura = 'Anulada'
        else:
            pass
    
    def re_facturacion_digital(self):
        
        if self.correo_adicional == False and self.partner_id.email == False:
            raise ValidationError(_("No se encontro un EMAIL valido para el envio de la factura."))
        else:
            correo = self.correo_adicional if self.correo_adicional != False else self.partner_id.email
            numerocontrol = self.nro_ctrl 

        url = self.company_id.url_fdigital + 'email'
        token = {
            'Authorization': 'Bearer ' + self.company_id.token_fdigital.replace(' ', ''),
            'Content-Type': 'application/json'
        }
        DATA = {
            "numerodocumento": numerocontrol,
            "rif": "J-50643679-5",
            "email": correo
        }

        response = requests.post(
            url,
            headers=token,
            json=DATA
        )

        if response.status_code == 200:
            pass