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
import requests

_logger = logging.getLogger(__name__)

class AccountReportCXC(models.TransientModel):
    _name = 'account.invoice.report.cxc'
    _description = 'Reporte de Cuentas por Cobrar'

    start_date = fields.Date(string='Fecha Inicio')
    end_date = fields.Date(string='Fecha Fin')
    partner_id = fields.Many2one('res.partner', string="Cliente")
    user_id = fields.Many2one('res.users', string="Comercial")  # <--- Aquí se añade
    debt_type = fields.Selection(
        selection=[
            ('cashea', 'Cashea'),
            ('ventas_internas', 'Ventas Internas'),
        ],
        string='Tipo de Deuda',
    )

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

    def _get_exchange_rate(self):
        """Obtiene la tasa de cambio más reciente en Bs. por USD desde Odoo."""
        company_currency = self.env.company.currency_id
        usd_currency = self.env.ref('base.USD')  # Dólar americano
        
        if company_currency == usd_currency:
            return 1  # Si la moneda de la empresa es USD, la tasa es 1
        
        # Obtener la tasa más reciente registrada en Odoo
        currency_rate = self.env['res.currency.rate'].search([ 
            ('currency_id', '=', usd_currency.id),
            ('company_id', '=', self.env.company.id) 
        ], order='name desc', limit=1)
        
        return round(1 / currency_rate.rate, 2) if currency_rate else "No disponible"

    def action_generate_report(self):
        """Genera el reporte según el formato seleccionado"""
        # if not self.due_range and not (self.start_date and self.end_date):
        #     raise ValidationError("Debe seleccionar un rango de vencimiento o indicar fechas manualmente.")
        if self.report_format == "pdf":
            return self._generate_pdf_report()
        else:
            raise ValidationError("Formato de reporte no válido. Elija PDF.")

    def _calculate_dates_from_due_range(self):
        """Calcula las fechas de inicio y fin según el filtro de vencimiento"""
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

    def _get_report_data(self):
        """Consulta la base de datos para obtener los datos del reporte según filtros seleccionados"""
        current_company_id = self.env.company
        start_date, end_date = self._calculate_dates_from_due_range()
        tasa_bcv = self._get_exchange_rate()  # Tasa para todos los cálculos en Bs

        query = """
            SELECT 
                m.id, 
                m.name, 
                m.date,
                m.invoice_date_due, 
                m.currency_id, 
                c.name AS currency_name,
                m.amount_total,
                m.amount_residual,
                m.amount_total_usd,
                m.amount_residual_usd,
                m.tax_today,
                p.name AS partner_name,
                EXTRACT(DAY FROM NOW() - m.invoice_date_due) AS days_due
            FROM 
                account_move m
            JOIN 
                res_partner p ON m.partner_id = p.id
            JOIN
                res_currency c ON m.currency_id = c.id
            WHERE 
                m.move_type = 'out_invoice'
                AND m.amount_residual > 0
                AND m.state = 'posted'
            """
        params = []

        # Filtros
        if start_date and end_date:
            query += " AND m.invoice_date_due BETWEEN %s AND %s"
            params.extend([start_date, end_date])
        if current_company_id:
            query += " AND m.company_id = %s"
            params.append(current_company_id.id)
        if self.partner_id:
            query += " AND m.partner_id = %s"
            params.append(self.partner_id.id)
        if self.user_id:
            query += " AND m.invoice_user_id = %s"
            params.append(self.user_id.id)
        if self.debt_type:
            query += " AND m.tipo_de_deuda = %s"
            params.append(self.debt_type)

        query += " ORDER BY m.date ASC"

        self.env.cr.execute(query, tuple(params))
        result = self.env.cr.dictfetchall()

        if not result:
            raise ValidationError("No hay facturas por cobrar en el rango o filtros especificados.")

        grouped_result = defaultdict(list)
        for inv in result:
            # Lógica tal cual la necesitas
            if inv['currency_name'] == 'USD':
                monto_usd = inv['amount_total'] or 0
                deuda_usd = inv['amount_residual'] or 0
            else:
                monto_usd = inv['amount_total_usd'] or 0
                deuda_usd = inv['amount_residual_usd'] or 0

            monto_bs = monto_usd * tasa_bcv
            deuda_bs = deuda_usd * tasa_bcv

            inv.update({
                'monto_usd': monto_usd,
                'deuda_usd': deuda_usd,
                'monto_bs': monto_bs,
                'deuda_bs': deuda_bs,
                'tasa_bcv': tasa_bcv,
            })

            grouped_result[inv['partner_name']].append(inv)

        return grouped_result

    def _generate_pdf_report(self):
        """Genera el reporte en PDF con los filtros aplicados"""
        grouped_result = self._get_report_data()

        if not grouped_result:
            raise ValidationError("No hay facturas en el rango de fecha especificado")

        buffer = BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=landscape(letter))

        def draw_header():
            """Dibuja el encabezado en cada página"""
            pdf.setFont("Helvetica-Bold", 14)
            pdf.drawString(250, 550, "REPORTE DE CUENTAS POR COBRAR")
            pdf.setFont("Helvetica", 10)
            pdf.drawString(100, 520, f"Empresa: {self.env.company.name}")
            pdf.drawString(400, 520, f"Tasa del día: {self._get_exchange_rate()}")  # Tasa del día
            pdf.drawString(100, 500, f"R.I.F.: {self.env.company.vat or 'No posee RIF asociado'}")
            pdf.drawString(100, 480, f"Fecha desde: {self.start_date.strftime('%d/%m/%Y') if self.start_date else 'Automático'}")
            pdf.drawString(250, 480, f"Fecha hasta: {self.end_date.strftime('%d/%m/%Y') if self.end_date else 'Automático'}")

            if self.partner_id:
                pdf.drawString(100, 465, f"Cliente: {self.partner_id.name}")
            
            if self.user_id:
                pdf.drawString(450, 480, f"Comercial: {self.user_id.name}")

            if self.debt_type:
                pdf.drawString(450, 465, f"Tipo de deuda: {dict(self._fields['debt_type'].selection).get(self.debt_type)}")

            if self.due_range:
                pdf.drawString(550, 465, f"Filtro de Vencimiento: {dict(self._fields['due_range'].selection).get(self.due_range)}")

            # Encabezado de la tabla
            y_position = 450
            pdf.setFont("Helvetica", 8)
            headers = ["Fecha", "Cliente", "N° Doc.", "Moneda", "Monto (Bs.)", "Deuda (Bs.)", "Monto (USD)", "Deuda (USD)", "Tasa BCV", "Días Venc."]

            x_positions = [30, 80, 220, 400, 440, 495, 555, 620, 680, 740]

            for i, header in enumerate(headers):
                pdf.drawString(x_positions[i], y_position, header)

            return y_position - 20

        total_monto_bs = 0
        total_deuda_bs = 0
        total_monto_usd = 0
        total_deuda_usd = 0

        y_position = draw_header()

        # Recorrer los clientes y facturas agrupadas
        for partner_name, invoices in grouped_result.items():
            # Inicializar los totales por cliente
            client_total_monto_bs = 0
            client_total_deuda_bs = 0
            client_total_monto_usd = 0
            client_total_deuda_usd = 0

            # Verificar si hay suficiente espacio en la página
            if y_position < 50:  # Control de salto de página
                pdf.showPage()
                pdf.setFont("Helvetica", 8)
                y_position = draw_header()

            # Mostrar solo el nombre del cliente en el título
            pdf.setFont("Helvetica-Bold", 8)
            pdf.drawString(30, y_position, f"Cliente: {partner_name}")
            y_position -= 10
            pdf.setFont("Helvetica", 8)

            # Mostrar las facturas de cada cliente
            for inv in invoices:
                if y_position < 50:  # Control de salto de página
                    pdf.showPage()
                    pdf.setFont("Helvetica", 7)
                    y_position = draw_header()

                # Obtener la tasa de cambio del día
                exchange_rate = self._get_exchange_rate()

                # Convertir a Bs usando el monto en USD y la tasa del día
                monto_bs = round(inv.get('amount_total_usd', 0) * exchange_rate, 2)
                deuda_bs = round(inv.get('amount_residual_usd', 0) * exchange_rate, 2)

                pdf.drawString(30, y_position, inv.get('date').strftime('%d/%m/%Y') if inv.get('date') else 'Fecha no disponible')
                pdf.drawString(220, y_position, f"{inv.get('name', '-')}")  # N° Doc.
                pdf.drawString(415, y_position, f"{inv.get('currency_name', 'N/A')}")  # Moneda
                pdf.drawString(440, y_position, f"{inv.get('monto_bs', 0):,.2f}")  # Monto Bs.
                pdf.drawString(495, y_position, f"{inv.get('deuda_bs', 0):,.2f}")  # Deuda Bs.
                pdf.drawString(555, y_position, f"{inv.get('monto_usd', 0):,.2f}")  # Monto USD
                pdf.drawString(620, y_position, f"{inv.get('deuda_usd', 0):,.2f}")  # Deuda USD
                pdf.drawString(680, y_position, f"{inv.get('tax_today', 0):,.2f}")  # Tasa BCV
                pdf.drawString(740, y_position, str(inv.get('days_due') or "VIGENTE"))  # Días vencidos

                # Acumulando sumatoria por cliente
                client_total_monto_bs += inv.get('monto_bs', 0)
                client_total_deuda_bs += inv.get('deuda_bs', 0)
                client_total_monto_usd += inv.get('monto_usd', 0)
                client_total_deuda_usd += inv.get('deuda_usd', 0)

                y_position -= 15

            # Mostrar el total del cliente en una sola línea
            pdf.setFont("Helvetica-Bold", 9)
            pdf.drawString(30, y_position, "Total Cliente:") 
            pdf.drawString(440, y_position, f"{client_total_monto_bs:,.2f}")
            pdf.drawString(495, y_position, f"{client_total_deuda_bs:,.2f}")
            pdf.drawString(555, y_position, f"{client_total_monto_usd:,.2f}")
            pdf.drawString(620, y_position, f"{client_total_deuda_usd:,.2f}")
            
            # Sumar totales generales
            total_monto_bs += client_total_monto_bs
            total_deuda_bs += client_total_deuda_bs
            total_monto_usd += client_total_monto_usd
            total_deuda_usd += client_total_deuda_usd

            y_position -= 15

            # Dibujar una línea divisoria entre clientes
            pdf.line(30, y_position, 740, y_position)
            y_position -= 10
            
        # --- Aquí va el bloque de totales generales, fuera del ciclo ---
        # Si no hay suficiente espacio, crea una nueva página
        if y_position < 80:
            pdf.showPage()
            y_position = draw_header()

        y_position -= 5  # Espacio antes de los totales generales
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
        
        pdf.save()
        buffer.seek(0)

        pdf_data = base64.b64encode(buffer.getvalue())
        self.write({
            'state': 'get',
            'file_name_pdf': pdf_data,
            'invoice_data': 'cuentas_por_cobrar.pdf'
        })

        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content?model=%s&id=%s&field=file_name_pdf&filename_field=invoice_data&download=true' % (
                self._name,
                self.id,
            ),
            'target': 'self',
        }