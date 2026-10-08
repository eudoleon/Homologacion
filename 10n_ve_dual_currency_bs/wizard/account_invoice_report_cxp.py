# -*- coding: utf-8 -*-
###############################################################################
# Author: Jesus Pozzo / Andres Castillo
# Copyleft: 2023-Present.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).
#
# Migrado a Odoo v19:
# - Eliminado import de osv (no existe en v19)
# - Eliminado import de Warning (usar UserError)
# - _get_current_exchange_rate: usa company_rate (campo de v17+)
###############################################################################
import base64
from io import BytesIO
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import letter, landscape
from reportlab.pdfgen import canvas
from collections import defaultdict
import logging

_logger = logging.getLogger(__name__)

class AccountReportCXP(models.TransientModel):
    _name = 'account.invoice.report.cxp'
    _description = 'Reporte de Cuentas por Pagar'

    start_date = fields.Date(string='Fecha Inicio')
    end_date = fields.Date(string='Fecha Fin')
    partner_id = fields.Many2one('res.partner', string="Proveedor")

    due_range = fields.Selection([
        ('1-7', '1-7 días'),
        ('7-15', '7-15 días'),
        ('1-30', '1-30 días'),
        ('15-30', '15-30 días'),
        ('30-60', '30-60 días'),
        ('60-90', '60-90 días'),
        ('90-120', '90-120 días'),
    ], string="Filtrar por Vencimiento")

    report_format = fields.Selection([
        ('pdf', 'PDF')
    ], string="Formato del Reporte", required=True, default='pdf')

    invoice_data = fields.Char(string='Nombre del Archivo')
    file_name_pdf = fields.Binary('Descargar PDF', readonly=True)
    state = fields.Selection([('choose', 'choose'), ('get', 'get')], default='choose')

    def action_generate_report(self):
        if self.report_format == "pdf":
            return self._generate_pdf_report()
        else:
            raise ValidationError("Formato de reporte no válido. Elija PDF.")

    def _calculate_dates_from_due_range(self):
        today = datetime.today()
        first_day_of_month = today.replace(day=1)
        ranges = {
            '1-7': (today - timedelta(days=7), today),
            '7-15': (today - timedelta(days=15), today),
            '1-30': (first_day_of_month, today),
            '15-30': (today - timedelta(days=30), today),
            '30-60': (first_day_of_month - timedelta(days=30), today),
            '60-90': (first_day_of_month - timedelta(days=60), today),
            '90-120': (first_day_of_month - timedelta(days=90), today),
        }
        return ranges.get(self.due_range, (self.start_date, self.end_date))

    def _get_current_exchange_rate(self):
        """
        Retorna la tasa de cambio USD→Bs (cuántos Bs. por 1 USD).
        En Odoo v17+, res.currency.rate.company_rate es el campo directo
        que indica cuántas unidades de la moneda de la empresa equivalen
        a 1 unidad de la moneda extranjera.
        """
        currency_usd = self.env.ref('base.USD')
        currency_company = self.env.company.currency_id

        if currency_usd == currency_company:
            return 1.0

        today = fields.Date.context_today(self)
        rate = self.env['res.currency.rate'].search([
            ('currency_id', '=', currency_usd.id),
            ('name', '<=', today),
            ('company_id', '=', self.env.company.id),
        ], order='name desc', limit=1)

        if rate:
            # company_rate: cuántos Bs. por 1 USD (ya es la tasa directa en v17+)
            return round(rate.company_rate, 2)
        return 1.0

    def _get_report_data(self):
        company_id = self.env.company
        start_date, end_date = self._calculate_dates_from_due_range()
        current_rate = self._get_current_exchange_rate()

        # Nota: amount_total_usd, amount_residual_usd y tax_today son provistos
        # por el módulo account_dual_currency (dependencia requerida).
        query = """
            SELECT
                m.id,
                m.name,
                m.date,
                m.invoice_date_due,
                m.currency_id,
                c.name as currency_name,
                m.amount_total_usd,
                m.amount_total,
                m.amount_residual,
                m.amount_residual_usd,
                m.tax_today AS invoice_tax_rate,
                p.name as partner_name,
                EXTRACT(DAY FROM NOW() - m.invoice_date_due) AS days_due
            FROM
                account_move m
            JOIN
                res_partner p ON m.partner_id = p.id
            JOIN
                res_currency c ON m.currency_id = c.id
            WHERE
                m.move_type = 'in_invoice'
                AND m.amount_residual != 0
                AND m.state = 'posted'
        """
        params = []

        if self.due_range and start_date and end_date:
            query += " AND m.invoice_date_due BETWEEN %s AND %s"
            params.extend([start_date, end_date])
        elif not self.due_range:
            if start_date and end_date:
                query += " AND m.invoice_date_due BETWEEN %s AND %s"
                params.extend([start_date, end_date])
            elif start_date and not end_date:
                query += " AND m.invoice_date_due >= %s"
                params.append(start_date)
            elif end_date and not start_date:
                query += " AND m.invoice_date_due <= %s"
                params.append(end_date)

        query += " AND m.company_id = %s"
        params.append(company_id.id)

        if self.partner_id:
            query += " AND m.partner_id = %s"
            params.append(self.partner_id.id)

        query += " ORDER BY p.name ASC, m.date ASC"

        self.env.cr.execute(query, tuple(params))
        result = self.env.cr.dictfetchall()

        if not result:
            raise ValidationError("No hay facturas por pagar en el rango o filtros especificados.")

        grouped_result = defaultdict(list)
        for inv in result:
            amount_total_usd = inv.get('amount_total_usd') or 0.0
            amount_total_bs = amount_total_usd * current_rate
            amount_residual = inv.get('amount_residual') or 0.0
            amount_residual_bs = amount_residual * current_rate

            # Si la factura es en VEF, calcular deuda en USD dividiendo por la tasa
            if inv.get('currency_name') == 'VEF':
                deuda_usd = (inv.get('amount_residual_usd') or 0.0) if inv.get('amount_residual_usd') else (
                    amount_residual / current_rate if current_rate else 0.0
                )
            else:
                deuda_usd = amount_residual

            inv.update({
                'amount_total_usd': amount_total_usd,
                'amount_residual': deuda_usd,
                'amount_total_bs': amount_total_bs,
                'amount_residual_bs': amount_residual_bs,
                'tax_today': inv.get('invoice_tax_rate') or 0.0,
            })

            grouped_result[inv['partner_name']].append(inv)

        return grouped_result

    def _generate_pdf_report(self):
        grouped_result = self._get_report_data()
        buffer = BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=landscape(letter))

        def draw_header():
            pdf.setFont("Helvetica-Bold", 14)
            pdf.drawString(250, 550, "REPORTE DE CUENTAS POR PAGAR")
            pdf.setFont("Helvetica", 10)
            pdf.drawString(100, 520, f"Empresa: {self.env.company.name}")
            pdf.drawString(100, 500, f"R.I.F.: {self.env.company.vat or 'No posee RIF asociado'}")
            pdf.drawString(400, 520, f"Tasa del día: {self._get_current_exchange_rate()}")
            pdf.drawString(100, 480, f"Fecha desde: {self.start_date.strftime('%d/%m/%Y') if self.start_date else 'Automático'}")
            pdf.drawString(250, 480, f"Fecha hasta: {self.end_date.strftime('%d/%m/%Y') if self.end_date else 'Automático'}")
            if self.partner_id:
                pdf.drawString(100, 465, f"Proveedor: {self.partner_id.name}")
            if self.due_range:
                pdf.drawString(550, 465, f"Filtro de Vencimiento: {dict(self._fields['due_range'].selection).get(self.due_range)}")

            y_position = 450
            pdf.setFont("Helvetica", 8)
            headers = ["Fecha", "Proveedor", "N° Doc.", "Moneda", "Monto (Bs.)", "Deuda (Bs.)", "Monto (USD)", "Deuda (USD)", "Tasa BCV", "Días Venc."]
            x_positions = [30, 80, 220, 310, 365, 435, 510, 580, 660, 720]
            for i, header in enumerate(headers):
                pdf.drawString(x_positions[i], y_position, header)
            return y_position - 20

        total_monto_bs = 0
        total_deuda_bs = 0
        total_monto_usd = 0
        total_deuda_usd = 0

        y_position = draw_header()

        for partner_name, invoices in grouped_result.items():
            client_total_monto_bs = 0
            client_total_deuda_bs = 0
            client_total_monto_usd = 0
            client_total_deuda_usd = 0

            if y_position < 50:
                pdf.showPage()
                y_position = draw_header()

            pdf.setFont("Helvetica-Bold", 8)
            pdf.drawString(30, y_position, f"Proveedor: {partner_name}")
            y_position -= 10
            pdf.setFont("Helvetica", 8)

            for inv in invoices:
                if y_position < 50:
                    pdf.showPage()
                    y_position = draw_header()

                fecha_str = inv.get('date').strftime('%d/%m/%Y') if inv.get('date') else '-'
                pdf.drawString(30, y_position, fecha_str)
                pdf.drawString(220, y_position, inv.get('name', '-'))
                pdf.drawString(310, y_position, inv.get('currency_name', 'N/A'))
                pdf.drawString(365, y_position, f"{inv.get('amount_total_bs', 0):,.2f}")
                pdf.drawString(435, y_position, f"{inv.get('amount_residual_bs', 0):,.2f}")
                pdf.drawString(510, y_position, f"{inv.get('amount_total_usd', 0):,.2f}")
                pdf.drawString(580, y_position, f"{inv.get('amount_residual', 0):,.2f}")
                pdf.drawString(660, y_position, f"{inv.get('tax_today', 0):,.2f}")
                pdf.drawString(720, y_position, str(inv.get('days_due') or "VIGENTE"))

                client_total_monto_bs += inv.get('amount_total_bs', 0)
                client_total_deuda_bs += inv.get('amount_residual_bs', 0)
                client_total_monto_usd += inv.get('amount_total_usd', 0)
                client_total_deuda_usd += inv.get('amount_residual', 0)

                y_position -= 15

            pdf.setFont("Helvetica-Bold", 9)
            pdf.drawString(30, y_position, "Total Proveedor:")
            pdf.drawString(365, y_position, f"{client_total_monto_bs:,.2f}")
            pdf.drawString(435, y_position, f"{client_total_deuda_bs:,.2f}")
            pdf.drawString(510, y_position, f"{client_total_monto_usd:,.2f}")
            pdf.drawString(580, y_position, f"{client_total_deuda_usd:,.2f}")
            pdf.line(30, y_position - 2, 740, y_position - 2)

            total_monto_bs += client_total_monto_bs
            total_deuda_bs += client_total_deuda_bs
            total_monto_usd += client_total_monto_usd
            total_deuda_usd += client_total_deuda_usd

            y_position -= 35

        if y_position < 80:
            pdf.showPage()
            y_position = draw_header()

        current_rate = self._get_current_exchange_rate()
        total_deuda_bs = total_deuda_usd * current_rate

        y_position -= 30
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(30, y_position, "TOTALES GENERALES:")

        pdf.setFont("Helvetica", 9)
        y_position -= 15
        pdf.drawString(50, y_position, f"Monto (Bs.): {total_monto_bs:,.2f}")
        y_position -= 15
        pdf.drawString(50, y_position, f"Deuda (Bs.): {total_deuda_bs:,.2f}")
        y_position -= 15
        pdf.drawString(50, y_position, f"Monto (USD): {total_monto_usd:,.2f}")
        y_position -= 15
        pdf.drawString(50, y_position, f"Deuda (USD): {total_deuda_usd:,.2f}")

        pdf.showPage()
        pdf.save()

        buffer.seek(0)
        file_data = buffer.getvalue()
        encoded_file = base64.b64encode(file_data)

        self.write({
            'file_name_pdf': encoded_file,
            'invoice_data': 'reporte_cxp.pdf',
            'state': 'get',
        })

        buffer.close()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.invoice.report.cxp',
            'view_mode': 'form',
            'view_type': 'form',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'new',
        }