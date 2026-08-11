from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


def _flatten_percent_taxes(taxes):
    """Return percent taxes, expanding group taxes recursively."""
    percent_taxes = []
    stack = list(taxes)
    visited_ids = set()

    while stack:
        tax = stack.pop()
        if tax.id in visited_ids:
            continue
        visited_ids.add(tax.id)

        if tax.amount_type == 'group':
            stack.extend(tax.children_tax_ids)
        elif tax.amount_type == 'percent':
            percent_taxes.append(tax)

    return percent_taxes

class AccountMove(models.Model):
    _inherit = 'account.move'

    # Campos en moneda base
    tax_16 = fields.Monetary(string="IVA 16%", compute="_compute_tax_amounts", store=True)
    tax_8 = fields.Monetary(string="IVA 8%", compute="_compute_tax_amounts", store=True)
    tax_31 = fields.Monetary(string="IVA 31%", compute="_compute_tax_amounts", store=True)
    tax_exento = fields.Monetary(string="Monto Exento", compute="_compute_tax_amounts", store=True)
    base_16 = fields.Monetary(string="Base Imponible 16%", compute="_compute_tax_amounts", store=True)
    base_8 = fields.Monetary(string="Base Imponible 8%", compute="_compute_tax_amounts", store=True)
    base_31 = fields.Monetary(string="Base Imponible 31%", compute="_compute_tax_amounts", store=True)
    total_imponible = fields.Monetary(string="Total Imponible", compute="_compute_tax_amounts", store=True)
    subtotal = fields.Monetary(string="SubTotal", compute="_compute_tax_amounts", store=True)

    # Campos en dólares
    tax_16_usd = fields.Monetary(string="IVA 16% (USD)", compute="_compute_tax_amounts", store=True, currency_field='usd_currency_id')
    tax_8_usd = fields.Monetary(string="IVA 8% (USD)", compute="_compute_tax_amounts", store=True, currency_field='usd_currency_id')
    tax_31_usd = fields.Monetary(string="IVA 31% (USD)", compute="_compute_tax_amounts", store=True, currency_field='usd_currency_id')
    tax_exento_usd = fields.Monetary(string="Monto Exento (USD)", compute="_compute_tax_amounts", store=True, currency_field='usd_currency_id')
    base_16_usd = fields.Monetary(string="Base Imponible 16% (USD)", compute="_compute_tax_amounts", store=True, currency_field='usd_currency_id')
    base_8_usd = fields.Monetary(string="Base Imponible 8% (USD)", compute="_compute_tax_amounts", store=True, currency_field='usd_currency_id')
    base_31_usd = fields.Monetary(string="Base Imponible 31% (USD)", compute="_compute_tax_amounts", store=True, currency_field='usd_currency_id')
    total_imponible_usd = fields.Monetary(string="Total Imponible (USD)", compute="_compute_tax_amounts", store=True, currency_field='usd_currency_id')
    subtotal_usd = fields.Monetary(string="SubTotal (USD)", compute="_compute_tax_amounts", store=True, currency_field='usd_currency_id')

    # Moneda USD
    usd_currency_id = fields.Many2one('res.currency', string="Moneda USD", default=lambda self: self.env.ref('base.USD'))

    # Control de impresión
    invoice_template_dual_printed = fields.Boolean(string="Factura Original Impresa", default=False, readonly=True)
    print_count = fields.Integer(string="Cantidad de impresiones", copy=False, default=0)

    # Control para visibilidad del botón
    show_print_dual_button = fields.Boolean(
        string="Mostrar botón de factura dual",
        compute="_compute_show_print_dual_button",
        store=False
    )

    @api.depends('move_type')
    def _compute_show_print_dual_button(self):
        for rec in self:
            rec.show_print_dual_button = rec.move_type == 'out_invoice'

    @api.depends('line_ids.price_subtotal', 'line_ids.tax_ids', 'tax_today')
    def _compute_tax_amounts(self):
        for move in self:
            tax_16 = tax_8 = tax_31 = tax_exento = 0.0
            base_16 = base_8 = base_31 = 0.0
    
            # Obtener la tasa del día (si no existe, usar 1 para evitar división por cero)
            exchange_rate = getattr(move, 'tax_today', 1.0) or 1.0
    
            for line in move.line_ids.filtered(lambda l: l.display_type == 'product'):
                subtotal = line.price_subtotal or 0.0

                tax_list = _flatten_percent_taxes(line.tax_ids)
                positive_rates = [round(t.amount, 2) for t in tax_list if t.amount > 0]

                # Exento
                if not positive_rates:
                    tax_exento += subtotal
                else:
                    total_rate = round(sum(positive_rates), 2)

                    if total_rate == 16:
                        base_16 += subtotal
                        tax_16 += subtotal * (total_rate / 100)
                    elif total_rate == 8:
                        base_8 += subtotal
                        tax_8 += subtotal * (total_rate / 100)
                    elif total_rate == 31:
                        base_31 += subtotal
                        tax_31 += subtotal * (total_rate / 100)
    
            # Totales en bolívares
            move.tax_16 = tax_16
            move.tax_8 = tax_8
            move.tax_31 = tax_31
            move.tax_exento = tax_exento
            move.base_16 = base_16
            move.base_8 = base_8
            move.base_31 = base_31
            move.total_imponible = base_16 + base_8 + base_31
            move.subtotal = tax_exento + move.total_imponible + tax_16 + tax_8 + tax_31
    
            # --- Conversión automática a USD ---
            move.tax_16_usd = tax_16 / exchange_rate
            move.tax_8_usd = tax_8 / exchange_rate
            move.tax_31_usd = tax_31 / exchange_rate
            move.tax_exento_usd = tax_exento / exchange_rate
            move.base_16_usd = base_16 / exchange_rate
            move.base_8_usd = base_8 / exchange_rate
            move.base_31_usd = base_31 / exchange_rate
            move.total_imponible_usd = move.total_imponible / exchange_rate
            move.subtotal_usd = move.subtotal / exchange_rate


    def get_report_name(self):
        return f"Factura Fiscal - {self.name}"

    def action_print_invoice_custom_dual(self):
        # Verificar si el movimiento está en estado 'posted'
        if self.state == 'posted':
            # Verificar si el tipo de movimiento es una nota de crédito o débito
            if self.move_type == 'out_refund':  # Nota de Crédito
                return self.env.ref('forma_libre.action_report_invoice_custom_dual').report_action(self)
            elif self.debit_origin_id:  # Nota de Débito (cuando debit_origin_id está establecido)
                return self.env.ref('forma_libre.action_report_invoice_custom_dual').report_action(self)
            else:
                # Es una factura normal
                return self.env.ref('forma_libre.action_report_invoice_custom_dual').report_action(self)
        else:
            # Si el movimiento no está publicado, lanzar un error con el mensaje correspondiente
            if self.move_type == 'out_refund':
                message = 'La Nota de Crédito debe estar publicada para ser impresa.'
            elif self.debit_origin_id:
                message = 'La Nota de Débito debe estar publicada para ser impresa.'
            else:
                message = 'La factura debe estar publicada para ser impresa.'
            
            raise UserError(message)
    
    @api.model_create_multi
    def create(self, vals_list):
        # Odoo 19: create recibe una lista de diccionarios
        for vals in vals_list:
            vals['invoice_template_dual_printed'] = False
        return super().create(vals_list)
    
    # Código anterior (Odoo 13-16):
    # @api.model
    # def create(self, vals):
    #     vals['invoice_template_dual_printed'] = False
    #     return super().create(vals)

    def copy(self, default=None):
        default = dict(default or {}, invoice_template_dual_printed=False)
        return super().copy(default)
    
class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    alicuota = fields.Char(string='Alícuota', compute='_compute_alicuota', store=True)

    @api.depends('tax_ids')
    def _compute_alicuota(self):
        for line in self:
            percent_taxes = _flatten_percent_taxes(line.tax_ids)
            has_positive_tax = any(tax.amount > 0 for tax in percent_taxes)
            line.alicuota = '( E )' if not has_positive_tax else ''

    
