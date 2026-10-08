#módulo para almacenar el reporte z de la impresora fiscal
from odoo import models, fields, api
class PosReportZ(models.Model):
    _name = "pos.report.z"
    _description = "Reporte Z"
    _order = "id desc"
    _rec_name = "number"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    #número de reporte
    number = fields.Char("Número de reporte", required=True, tracking=True)

    #state
    state = fields.Selection([('draft', 'Borrador'), ('done', 'Hecho')], string='Estado', default='draft', tracking=True)

    #impresora fiscal
    #x_fiscal_printer_id = fields.Many2one("x.pos.fiscal.printer", "Impresora fiscal", tracking=True)
    #x_fiscal_printer_code = fields.Char("Código de la impresora fiscal", related="x_fiscal_printer_id.serial", store=True, tracking=True)
    #connection_type = fields.Selection([('serial', 'Serial'), ('usb', 'USB'), ('usb_serial', 'USB Serial'),('file', 'Archivo'), ('api', 'API')], related="x_fiscal_printer_id.connection_type", store=True)
    #fecha y hora del reporte
    date = fields.Datetime("Fecha y hora", tracking=True)

    #sesiones pos
    pos_session_ids = fields.Many2many("pos.session", string="Sesiones POS")

    #total acumulado exento
    total_exempt = fields.Float("Total exento", tracking=True)

    #total base imponible iva 16
    total_base_iva_16 = fields.Float("Total base imponible", tracking=True)

    #total iva 16
    total_iva_16 = fields.Float("Total iva", tracking=True)

    # total acumulado exento nota de crédito
    total_exempt_nc = fields.Float("Total exento NC", tracking=True)

    # total base imponible iva 16 nota de crédito
    total_base_iva_16_nc = fields.Float("Total base imponible 16 NC", tracking=True)

    # total iva 16 nota de crédito
    total_iva_16_nc = fields.Float("Total iva NC", tracking=True)

    #ventas pos asociadas a las sesiones cargadas
    pos_order_ids = fields.Many2many(
        "pos.order", 
        string="Ventas POS",
        relation="pos_report_z_pos_order_rel"  # 🔴 Especificar relación única
    )

    # Total base imponible IVA 8
    total_base_iva_8 = fields.Float("Total base imponible IVA 8%", tracking=True)

    # Total IVA 8
    total_iva_8 = fields.Float("Total IVA 8%", tracking=True)

    # Total base imponible IVA 31
    total_base_iva_31 = fields.Float("Total base imponible IVA 31%", tracking=True)

    # Total IVA 31
    total_iva_31 = fields.Float("Total IVA 31%", tracking=True)

    # Total base imponible IVA 8 ventas pos
    total_base_iva_8_pos = fields.Float("Total Base Imponible IVA 8% POS", tracking=True, compute="_compute_total_pos")

    # Total IVA 8 ventas pos
    total_iva_8_pos = fields.Float("Total IVA 8% POS", tracking=True, compute="_compute_total_pos")

    # Total base imponible IVA 31 ventas pos
    total_base_iva_31_pos = fields.Float("Total Base Imponible IVA 31% POS", tracking=True, compute="_compute_total_pos")

    # Total IVA 31 ventas pos
    total_iva_31_pos = fields.Float("Total IVA 31% POS", tracking=True, compute="_compute_total_pos")

    # Total base imponible IVA 8 ventas pos nota de crédito
    total_base_iva_8_pos_nc = fields.Float("Total Base Imponible IVA 8% POS NC", tracking=True, compute="_compute_total_pos")

    # Total IVA 8 ventas pos nota de crédito
    total_iva_8_pos_nc = fields.Float("Total IVA 8% POS NC", tracking=True, compute="_compute_total_pos")

    # Total base imponible IVA 31 ventas pos nota de crédito
    total_base_iva_31_pos_nc = fields.Float("Total Base Imponible IVA 31% POS NC", tracking=True, compute="_compute_total_pos")

    # Total IVA 31 ventas pos nota de crédito
    total_iva_31_pos_nc = fields.Float("Total IVA 31% POS NC", tracking=True, compute="_compute_total_pos")

    #total excento ventas pos
    total_exempt_pos = fields.Float("Total Excento POS", tracking=True, compute="_compute_total_pos")

    #total base imponible iva 16 ventas pos
    total_base_iva_16_pos = fields.Float("Total Base Imponible POS", tracking=True, compute="_compute_total_pos")

    #total iva 16 ventas pos
    total_iva_16_pos = fields.Float("Total IVA POS", tracking=True, compute="_compute_total_pos")

    #total excento ventas pos nota de crédito
    total_exempt_pos_nc = fields.Float("Total Excento POS NC", tracking=True, compute="_compute_total_pos")

    #total base imponible iva 16 ventas pos nota de crédito
    total_base_iva_16_pos_nc = fields.Float("Total Base Imponible POS NC", tracking=True, compute="_compute_total_pos")

    #total iva 16 ventas pos nota de crédito
    total_iva_16_pos_nc = fields.Float("Total IVA POS NC", tracking=True, compute="_compute_total_pos")

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    ticket_fiscal_ids = fields.Many2many(
        'pos.order', 
        string="Tickets Fiscales",
        compute="_compute_ticket_fiscales",
        store=True,
        relation="pos_report_z_ticket_fiscal_rel"  # 🔴 Relación única
    )

    ticket_fiscal_desde = fields.Char(
        "Ticket Fiscal Desde", 
        compute="_compute_ticket_fiscales",
        store=True,
        tracking=True
    )

    ticket_fiscal_hasta = fields.Char(
        "Ticket Fiscal Hasta", 
        compute="_compute_ticket_fiscales",
        store=True,
        tracking=True
    )

    date_start = fields.Datetime(
        "Fecha Inicial",
        compute="_compute_report_dates",
        store=True,
        tracking=True
    )

    date_end = fields.Datetime(
        "Fecha Final",
        compute="_compute_report_dates",
        store=True,
        tracking=True
    )

    @api.depends('pos_order_ids', 'pos_order_ids.date_order')
    def _compute_report_dates(self):
        for report in self:
            if report.pos_order_ids:
                dates = report.pos_order_ids.mapped('date_order')
                # Filtramos valores falsos por si acaso
                dates = [d for d in dates if d]
                if dates:
                    report.date_start = min(dates)
                    report.date_end = max(dates)
                else:
                    report.date_start = False
                    report.date_end = False
            else:
                report.date_start = False
                report.date_end = False

    @api.depends('pos_order_ids', 'state')
    def _compute_total_pos(self):
        for report in self:
            # Total Exento
            report.total_exempt_pos = sum(report.pos_order_ids.filtered(lambda x: x.amount_total > 0).mapped("lines").filtered(lambda x: x.tax_ids.amount == 0).mapped("price_subtotal_incl"))
            
            # Total base imponible IVA 16
            total_base_iva_16_pos = sum(report.pos_order_ids.filtered(lambda x: x.amount_total > 0).mapped("lines").filtered(lambda x: x.tax_ids.amount == 16).mapped("price_subtotal"))
            total_16_pos = sum(report.pos_order_ids.filtered(lambda x: x.amount_total > 0).mapped("lines").filtered(lambda x: x.tax_ids.amount == 16).mapped("price_subtotal_incl"))
            report.total_base_iva_16_pos = total_base_iva_16_pos
            report.total_iva_16_pos = total_16_pos - total_base_iva_16_pos

            # Total base imponible IVA 8
            total_base_iva_8_pos = sum(report.pos_order_ids.filtered(lambda x: x.amount_total > 0).mapped("lines").filtered(lambda x: x.tax_ids.amount == 8).mapped("price_subtotal"))
            total_8_pos = sum(report.pos_order_ids.filtered(lambda x: x.amount_total > 0).mapped("lines").filtered(lambda x: x.tax_ids.amount == 8).mapped("price_subtotal_incl"))
            report.total_base_iva_8_pos = total_base_iva_8_pos
            report.total_iva_8_pos = total_8_pos - total_base_iva_8_pos

            # Total base imponible IVA 31
            total_base_iva_31_pos = sum(report.pos_order_ids.filtered(lambda x: x.amount_total > 0).mapped("lines").filtered(lambda x: x.tax_ids.amount == 31).mapped("price_subtotal"))
            total_31_pos = sum(report.pos_order_ids.filtered(lambda x: x.amount_total > 0).mapped("lines").filtered(lambda x: x.tax_ids.amount == 31).mapped("price_subtotal_incl"))
            report.total_base_iva_31_pos = total_base_iva_31_pos
            report.total_iva_31_pos = total_31_pos - total_base_iva_31_pos

            # Nota de crédito base imponible IVA 16
            total_base_iva_16_pos_nc = sum(report.pos_order_ids.filtered(lambda x: x.amount_total < 0).mapped("lines").filtered(lambda x: x.tax_ids.amount == 16).mapped("price_subtotal"))
            total_iva_16_pos_nc = sum(report.pos_order_ids.filtered(lambda x: x.amount_total < 0).mapped("lines").filtered(lambda x: x.tax_ids.amount == 16).mapped("price_subtotal_incl"))
            report.total_exempt_pos_nc = sum(report.pos_order_ids.filtered(lambda x: x.amount_total < 0).mapped("lines").filtered(lambda x: x.tax_ids.amount == 0).mapped("price_subtotal_incl"))
            report.total_base_iva_16_pos_nc = total_base_iva_16_pos_nc
            report.total_iva_16_pos_nc = total_iva_16_pos_nc - total_base_iva_16_pos_nc

            # Nota de crédito base imponible IVA 8
            total_base_iva_8_pos_nc = sum(report.pos_order_ids.filtered(lambda x: x.amount_total < 0).mapped("lines").filtered(lambda x: x.tax_ids.amount == 8).mapped("price_subtotal"))
            total_iva_8_pos_nc = sum(report.pos_order_ids.filtered(lambda x: x.amount_total < 0).mapped("lines").filtered(lambda x: x.tax_ids.amount == 8).mapped("price_subtotal_incl"))
            report.total_base_iva_8_pos_nc = total_base_iva_8_pos_nc
            report.total_iva_8_pos_nc = total_iva_8_pos_nc - total_base_iva_8_pos_nc

            # Nota de crédito base imponible IVA 31
            total_base_iva_31_pos_nc = sum(report.pos_order_ids.filtered(lambda x: x.amount_total < 0).mapped("lines").filtered(lambda x: x.tax_ids.amount == 31).mapped("price_subtotal"))
            total_iva_31_pos_nc = sum(report.pos_order_ids.filtered(lambda x: x.amount_total < 0).mapped("lines").filtered(lambda x: x.tax_ids.amount == 31).mapped("price_subtotal_incl"))
            report.total_base_iva_31_pos_nc = total_base_iva_31_pos_nc
            report.total_iva_31_pos_nc = total_iva_31_pos_nc - total_base_iva_31_pos_nc

    @api.depends('pos_order_ids', 'pos_order_ids.ticket_fiscal', 'pos_order_ids.name')
    def _compute_ticket_fiscales(self):
        for report in self:
            report.ticket_fiscal_ids = report.pos_order_ids.filtered(lambda o: o.ticket_fiscal)
            
            # Recolectar de forma segura solo tickets que sean numéricos
            ticket_fiscales = []
            for o in report.ticket_fiscal_ids:
                if o.ticket_fiscal and 'REFUND' not in (o.name or '').upper() and 'REEMBOLSO' not in (o.name or '').upper():
                    try:
                        # Extraer solo dígitos por si hay caracteres especiales
                        digits_only = ''.join(filter(str.isdigit, o.ticket_fiscal))
                        if digits_only:
                            ticket_fiscales.append(int(digits_only))
                    except ValueError:
                        pass

            if ticket_fiscales:
                report.ticket_fiscal_desde = str(min(ticket_fiscales))
                report.ticket_fiscal_hasta = str(max(ticket_fiscales))
            else:
                report.ticket_fiscal_desde = False
                report.ticket_fiscal_hasta = False


    def action_done(self):
        for report in self:
            report.state = 'done'
            if report.pos_order_ids:
                for order in report.pos_order_ids:
                    # Buscar las facturas asociadas al pedido POS
                    moves = self.env['account.move'].search([('pos_order_id', '=', order.id)])
                    
                    for move in moves:
                        move.write({'z_report_number': report.number})

    def action_draft(self):
        self.state = 'draft'

    @api.onchange('pos_session_ids')
    def _onchange_pos_session_ids(self):
        for report in self:
            report.pos_order_ids = report.pos_session_ids.mapped("order_ids")

class AccountMove(models.Model):
    _inherit = 'account.move'

    z_report_number = fields.Char(string="Número de Reporte Z", tracking=True)


