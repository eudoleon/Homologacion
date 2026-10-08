import xlwt
import base64
import calendar
from io import BytesIO
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import letter, landscape
from reportlab.pdfgen import canvas
from collections import defaultdict
import logging

_logger = logging.getLogger(__name__)

class AccountReportCXC(models.TransientModel):
    _name = 'account.invoice.report.cx'
    _description = 'Reporte de Cuentas por Cobrar'

    start_date = fields.Date(string='Fecha Inicio')
    end_date = fields.Date(string='Fecha Fin')
    partner_id = fields.Many2one('res.partner', string="Cliente")
    user_id = fields.Many2one('res.users', string="Comercial")

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

        # Si se selecciona un rango predefinido, devolver fechas basadas en el rango
        ranges = {
            '1-7': (today - timedelta(days=7), today),
            '7-15': (today - timedelta(days=15), today),
            '1-30': (first_day_of_month, today),
            '15-30': (today - timedelta(days=30), today),
            '30-60': (first_day_of_month - timedelta(days=30), today),
            '60-90': (first_day_of_month - timedelta(days=60), today),
            '90-120': (first_day_of_month - timedelta(days=90), today),
        }

        if self.due_range in ranges:
            return ranges[self.due_range]

        # Si el usuario ingresó fechas manualmente
        if self.start_date and self.end_date:
            return self.start_date, self.end_date

        # No aplicar filtro de fechas
        return None, None

    def _get_report_data(self):
        current_company_id = self.env.company
        use_due_filter = bool(self.due_range)
        start_date, end_date = self._calculate_dates_from_due_range()

        query = """
        SELECT 
            m.id, 
            m.name, 
            m.date,
            m.invoice_date_due, 
            m.currency_id, 
            c.name as currency_name,
            CASE 
                WHEN c.name = 'VEF' THEN m.amount_total 
                ELSE m.amount_total 
            END AS amount_total_bs,
            CASE 
                WHEN c.name = 'VEF' THEN m.amount_residual 
                ELSE m.amount_residual
            END AS amount_residual_bs,
            CASE 
                WHEN c.name = 'USD' THEN m.amount_total 
                ELSE 0 
            END AS amount_total_usd,
            CASE 
                WHEN c.name = 'USD' THEN m.amount_residual 
                ELSE 0
            END AS amount_residual_usd,
            m.tax_day,
            p.name as partner_name,
            EXTRACT(DAY FROM NOW() - m.invoice_date_due) AS days_due
        FROM 
            account_move m
        JOIN 
            res_partner p ON m.partner_id = p.id
        JOIN
            res_currency c ON m.currency_id = c.id
        LEFT JOIN
            res_users u ON m.invoice_user_id = u.id
        WHERE 
            m.move_type = 'out_invoice' 
            AND m.amount_residual != 0
            AND m.state = 'posted'
            AND m.company_id = %s
        """

        params = [current_company_id.id]

        if use_due_filter:
            query += " AND m.invoice_date_due BETWEEN %s AND %s"
            params.extend([start_date, end_date])

        if self.partner_id:
            query += " AND m.partner_id = %s"
            params.append(self.partner_id.id)

        if self.user_id:
            query += " AND m.invoice_user_id = %s"
            params.append(self.user_id.id)

        if start_date and end_date:
            query += " AND m.invoice_date_due BETWEEN %s AND %s"
            params.extend([start_date, end_date])

        query += " ORDER BY m.date ASC"

        self.env.cr.execute(query, tuple(params))
        result = self.env.cr.dictfetchall()

        grouped_result = defaultdict(list)
        for inv in result:
            grouped_result[inv['partner_name']].append(inv)

        return grouped_result

    def _generate_pdf_report(self):
        grouped_result = self._get_report_data()

        if not grouped_result:
            raise ValidationError("No hay facturas en el rango de fecha especificado")

        buffer = BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=landscape(letter))

        def draw_header():
            pdf.setFont("Helvetica-Bold", 14)
            pdf.drawString(250, 550, "REPORTE DE CUENTAS POR COBRAR")
            pdf.setFont("Helvetica", 10)
            pdf.drawString(100, 520, f"Empresa: {self.env.company.name}")
            pdf.drawString(100, 500, f"R.I.F.: {self.env.company.vat or 'No posee RIF asociado'}")
            pdf.drawString(100, 480, f"Fecha desde: {self.start_date.strftime('%d/%m/%Y') if self.start_date else 'Automático'}")
            pdf.drawString(250, 480, f"Fecha hasta: {self.end_date.strftime('%d/%m/%Y') if self.end_date else 'Automático'}")

            if self.partner_id:
                pdf.drawString(100, 465, f"Cliente: {self.partner_id.name}")
            
            if self.user_id:
                pdf.drawString(450, 480, f"Comercial: {self.user_id.name}")

            if self.due_range:
                pdf.drawString(550, 465, f"Filtro de Vencimiento: {dict(self._fields['due_range'].selection).get(self.due_range)}")

            # Encabezado de la tabla
            y_position = 450
            pdf.setFont("Helvetica", 8)
            headers = ["Fecha", "Cliente", "N° Doc.", "Monto (Bs.)", "Deuda (Bs.)", "Monto (USD)", "Deuda (USD)", "Tasa del Día", "Días Venc."] 
            x_positions = [30, 80, 340, 440, 495, 555, 620, 680, 740]

            for i, header in enumerate(headers):
                pdf.drawString(x_positions[i], y_position, header)

            return y_position - 20

        y_position = draw_header()

        # Recorrer los clientes y facturas agrupadas
        for partner_name, invoices in grouped_result.items():
            pdf.setFont("Helvetica-Bold", 8)
            pdf.drawString(30, y_position, f"Cliente: {partner_name}")
            y_position -= 10
            pdf.setFont("Helvetica", 8)

            # Inicializar totales por cliente
            total_bs = sum(inv.get('amount_total_bs', 0) for inv in invoices)
            total_deuda_bs = sum(inv.get('amount_residual_bs', 0) for inv in invoices)
            total_usd = sum((inv.get('amount_total_bs', 0) / inv.get('tax_day', 1)) for inv in invoices)
            total_deuda_usd = sum((inv.get('amount_residual_bs', 0) / inv.get('tax_day', 1)) for inv in invoices)

            # Mostrar las facturas de cada cliente
            for inv in invoices:
                if y_position < 50:  # Control de salto de página
                    pdf.showPage()
                    y_position = draw_header()

                # Convertir monto en USD a Bs usando la tasa del día
                amount_total_bs = inv.get('amount_total_usd', 0) * inv.get('tax_day', 1)
                amount_residual_bs = inv.get('amount_residual_usd', 0) * inv.get('tax_day', 1)

                # Mostrar las facturas de cada cliente
                pdf.drawString(30, y_position, inv.get('date').strftime('%d/%m/%Y'))
                pdf.drawString(340, y_position, inv.get('name', '-'))
                pdf.drawString(440, y_position, f"{amount_total_bs:,.2f}")  # Monto convertido a Bs
                pdf.drawString(495, y_position, f"{amount_residual_bs:,.2f}")  # Deuda convertida a Bs
                pdf.drawString(555, y_position, f"{inv.get('amount_total_usd', 0):,.2f}")  # Monto en USD
                pdf.drawString(620, y_position, f"{inv.get('amount_residual_usd', 0):,.2f}")  # Deuda en USD
                pdf.drawString(680, y_position, f"{inv.get('tax_day', 0):,.2f}")  # Mostrar la tasa del día
                pdf.drawString(740, y_position, str(inv.get('days_due') or "VIGENTE"))

                y_position -= 15

            # Agregar línea de total por cliente
            y_position -= 10
            pdf.setFont("Helvetica-Bold", 8)
            pdf.drawString(340, y_position, "Total:")
            pdf.drawString(440, y_position, f"{total_bs:,.2f}")
            pdf.drawString(495, y_position, f"{total_deuda_bs:,.2f}")
            pdf.drawString(555, y_position, f"{total_usd:,.2f}")
            pdf.drawString(620, y_position, f"{total_deuda_usd:,.2f}")
            y_position -= 20

        pdf.showPage()
        pdf.save()

        pdf_output = base64.b64encode(buffer.getvalue()).decode()
        buffer.close()

        self.write({
            'file_name_pdf': pdf_output,
            'invoice_data': "Reporte CXC",
            'state': 'get'
        })

        return {
            'type': 'ir.actions.act_window',
            'name': 'Reporte CXC',
            'res_model': 'account.invoice.report.cx',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }




