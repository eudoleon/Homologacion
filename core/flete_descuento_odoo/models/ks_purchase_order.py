# -*- coding: utf-8 -*-
# Migrado a Odoo 19.0 - Mantener compatibilidad con versiones anteriores
import json

from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
import logging
from odoo.tools.misc import formatLang

class GlobalTaxPurchases(models.Model):
    _inherit = "purchase.order"

    ks_global_tax_rate = fields.Float(string='Universal Tax (%):', readonly=True)
    ks_amount_global_tax = fields.Monetary(string="Universal Tax", readonly=True, compute='_amount_all',
                                           tracking=True, store=True)
    ks_enable_tax = fields.Boolean(compute='ks_verify_tax')


    @api.depends('company_id.ks_enable_tax')
    def ks_verify_tax(self):
        for rec in self:
            rec.ks_enable_tax = rec.company_id.ks_enable_tax


    @api.depends('order_line.price_total', 'ks_global_tax_rate')
    def _amount_all(self):
        for rec in self:
            ks_res = super(GlobalTaxPurchases, rec)._amount_all()
            if 'amount_discount' in rec:
                rec.ks_calculate_discount()
            #rec.ks_calculate_tax()  # Mover esta línea después de calcular el descuento para evitar bucle infinito
            # No llamar a rec.ks_calculate_tax() aquí para evitar bucle infinito
        return ks_res

    def _prepare_invoice(self):
        ks_res = super(GlobalTaxPurchases, self)._prepare_invoice()
        ks_res['ks_global_tax_rate'] = self.ks_global_tax_rate
        return ks_res


    def action_view_invoice(self, invoices=False):
        # 1. Llamamos al super para obtener el diccionario de la acción
        ks_res = super(GlobalTaxPurchases, self).action_view_invoice()
        
        # 2. Obtenemos el contexto (que ya es un diccionario)
        # Usamos .copy() para evitar modificar el contexto original por referencia de forma abrupta
        ctx = ks_res.get('context', {}).copy()
        
        _logger = logging.getLogger(__name__)
        _logger.warning(f'Context before modification: {ctx}')
        
        # 3. Inyectamos los valores por defecto directamente en el diccionario
        # Asegúrate de usar 'self' ya que action_view_invoice no suele iterarse (es una acción de botón)
        ctx.update({
            'default_ks_global_tax_rate': self.ks_global_tax_rate,
            'default_ks_amount_global_tax': self.ks_amount_global_tax,
        })
        
        # 4. Asignamos el diccionario de vuelta a la respuesta
        ks_res['context'] = ctx
        
        return ks_res


    @api.onchange('ks_amount_global_tax')
    def ks_calculate_tax(self):
        for rec in self:
            if rec.ks_global_tax_rate != 0.0:
                rec.ks_amount_global_tax = (rec.amount_total * rec.ks_global_tax_rate) / 100
            else:
                rec.ks_amount_global_tax = 0.0

            rec.amount_total = rec.ks_amount_global_tax + rec.amount_total

    def _compute_tax_totals(self):
        res = super(GlobalTaxPurchases, self)._compute_tax_totals()
        self.tax_totals['formatted_amount_total'] = formatLang(self.env, self.amount_total,currency_obj=self.currency_id)
        self.tax_totals['amount_total'] = self.amount_total
        self.tax_totals['ks_tax_amount'] = formatLang(self.env, self.ks_amount_global_tax,
                                                      currency_obj=self.currency_id)


    @api.constrains('ks_global_tax_rate')
    def ks_check_tax_value(self):
        if self.ks_global_tax_rate > 100 or self.ks_global_tax_rate < 0:
            raise ValidationError('You cannot enter percentage value greater than 100 or less than 0.')
