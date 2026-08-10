# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class ResPartner(models.Model):
    _inherit = 'res.partner'

    activate_credit = fields.Boolean(
        string='Activar Crédito',
        default=False,
        help='Habilita el control de crédito para este cliente'
    )

    credit_limit_custom = fields.Float(
        string='Límite de Crédito Personalizado',
        default=0.0,
        help='Límite de crédito personalizado para este cliente'
    )
    total_invoiced_amount = fields.Float(
        string='Monto Total Facturado',
        compute='_compute_total_invoiced_amount',
        store=True,
        help='Suma de las facturas en USD residual'
    )
    is_credit_restricted = fields.Boolean(
        string='Crédito Restringido',
        compute='_compute_is_credit_restricted',
        store=True,
        readonly=False,
        help='Se marca automáticamente cuando el monto facturado supera el límite'
    )

    @api.depends(
        'activate_credit',
        'invoice_ids',
        'invoice_ids.amount_residual',
        'invoice_ids.currency_id',
        'invoice_ids.company_id',
        'invoice_ids.date',
        'invoice_ids.invoice_date',
        'invoice_ids.state',
        'invoice_ids.move_type',
    )
    def _compute_total_invoiced_amount(self):
        """Calcula el monto total facturado del cliente en USD residual"""
        usd_currency = self.env['res.currency'].search([('name', '=', 'USD')], limit=1)
        for partner in self:
            if not partner.activate_credit:
                partner.total_invoiced_amount = 0.0
                continue

            invoices = partner.invoice_ids.filtered(
                lambda i: i.state == 'posted' and i.move_type == 'out_invoice'
            )
            total_usd = 0.0
            for invoice in invoices:
                company_currency = invoice.company_id.currency_id
                if usd_currency and company_currency and company_currency != usd_currency:
                    conversion_date = invoice.invoice_date or invoice.date or fields.Date.context_today(invoice)
                    total_usd += company_currency._convert(
                        invoice.amount_residual,
                        usd_currency,
                        invoice.company_id,
                        conversion_date,
                        round=False,
                    )
                else:
                    total_usd += invoice.amount_residual

            partner.total_invoiced_amount = total_usd
            _logger.info(
                f"Partner {partner.name} ({partner.id}): "
                f"Monto facturado USD ${partner.total_invoiced_amount:.2f}, "
                f"Límite ${partner.credit_limit_custom:.2f}"
            )

    @api.depends('total_invoiced_amount', 'credit_limit_custom')
    def _compute_is_credit_restricted(self):
        """Marca el cliente como restringido si supera el límite"""
        for partner in self:
            if not partner.activate_credit:
                partner.is_credit_restricted = False
                continue

            is_restricted = partner.total_invoiced_amount > partner.credit_limit_custom
            partner.is_credit_restricted = is_restricted
            if is_restricted:
                _logger.warning(
                    f"❌ CLIENTE RESTRINGIDO: {partner.name} ({partner.id}) - "
                    f"Deuda: ${partner.total_invoiced_amount:.2f} > "
                    f"Límite: ${partner.credit_limit_custom:.2f}"
                )

    def get_customer_credit_info(self):
        """Retorna información de crédito del cliente para sincronización con POS"""
        self.ensure_one()
        info = {
            'id': self.id,
            'name': self.name,
            'activate_credit': self.activate_credit,
            'is_credit_restricted': self.is_credit_restricted,
            'credit_limit_custom': self.credit_limit_custom,
            'total_invoiced_amount': self.total_invoiced_amount,
        }
        _logger.debug(f"Credit info for POS - {self.name}: {info}")
        return info

    @api.model
    def check_credit_restriction(self, partner_id):
        """
        Método RPC para validar restricción de crédito desde POS frontend
        Llamado por JavaScript antes de finalizar la orden
        """
        partner = self.env['res.partner'].browse(partner_id)

        if not partner.activate_credit:
            result = {
                'restricted': False,
                'activate_credit': False,
                'name': partner.name,
                'total_invoiced_amount': partner.total_invoiced_amount,
                'credit_limit_custom': partner.credit_limit_custom,
            }
            _logger.info(f"POS Frontend check - {partner.name}: credit disabled")
            return result
        
        result = {
            'restricted': partner.is_credit_restricted,
            'activate_credit': partner.activate_credit,
            'name': partner.name,
            'total_invoiced_amount': partner.total_invoiced_amount,
            'credit_limit_custom': partner.credit_limit_custom,
        }
        
        _logger.info(f"POS Frontend check - {partner.name}: restricted={result['restricted']}")
        return result
