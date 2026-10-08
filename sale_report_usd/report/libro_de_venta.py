from odoo import models, fields
import xlsxwriter
from io import BytesIO
import base64
from datetime import datetime
from odoo.exceptions import UserError
from datetime import timedelta
import pytz
import logging
_logger = logging.getLogger(__name__)


class POSReportZExcelWizard(models.TransientModel):
    _name = 'pos.report.z.excel.wizard'
    _description = 'Wizard for generating POS Report Z Excel'

    
    date_from = fields.Date(string='Desde', required=True)
    date_to = fields.Date(string='Hasta', required=True)
    #fiscal_printer_id = fields.Many2many('x.pos.fiscal.printer', string='Impresoras Fiscales', required=True)
    excel_file = fields.Binary('Excel Report', readonly=True)
    file_name = fields.Char('Excel File', readonly=True)
    report_type = fields.Selection([
        ('normal', 'Consolidado'),
        ('detallado', 'Detallado')  # Nuevo tipo de reporte detallado
    ], string='Tipo de Reporte', default='normal', required=True)

    def _convert_to_caracas_timezone(self, date_obj):
        """Convierte la fecha/hora a la zona horaria America/Caracas."""
        if not date_obj:
            return ""
        local_tz = pytz.timezone('America/Caracas')
        utc_dt = pytz.utc.localize(date_obj) if not date_obj.tzinfo else date_obj
        return utc_dt.astimezone(local_tz)

    def _get_caracas_datetime_range(self, date_field):
        """Genera el rango completo para un día en la zona horaria de Caracas"""
        caracas_tz = pytz.timezone('America/Caracas')
        start_date = datetime.combine(date_field, datetime.min.time())
        end_date = datetime.combine(date_field, datetime.max.time())

        start_dt = caracas_tz.localize(start_date)
        end_dt = caracas_tz.localize(end_date)
        return start_dt.astimezone(pytz.utc), end_dt.astimezone(pytz.utc)

    def generate_excel_report(self):
        self.ensure_one()
        if self.report_type == 'normal':
            return self._generate_normal_report()
        elif self.report_type == 'detallado':
            return self._generate_detailed_report()  # Llamar al nuevo reporte detallado
    
    def _generate_detailed_report(self):
        self.ensure_one()

        # Obtener las fechas con zona horaria de Caracas para cada día del rango
        dates_in_range = [self.date_from + timedelta(days=i) for i in range((self.date_to - self.date_from).days + 1)]
        report_data = []

        for date in dates_in_range:
            start_dt, end_dt = self._get_caracas_datetime_range(date)
            day_data = self.env['pos.report.z'].search([
                ('date', '>=', start_dt),
                ('date', '<=', end_dt),
            ])
            report_data.extend(day_data)

        # Crear el archivo Excel
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Reporte Z Detallado')

        # Ajustar el ancho de la columna A antes de escribir cualquier dato en ella
        worksheet.set_column('A:A', 30)  # Ancho fijo para la columna A

        # Formats
        header_format = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1})
        cell_format = workbook.add_format({'align': 'center', 'valign': 'vcenter', 'border': 1})
        number_format = workbook.add_format({'align': 'right', 'valign': 'vcenter', 'border': 1, 'num_format': '#,##0.00'})

        # Información de la empresa
        company = self.env.company
        worksheet.write('A1', company.name, header_format)
        worksheet.write('A2', f"N° DE RIF.: {company.vat}", header_format)
        worksheet.write('A3', "CONTRIBUYENTE FORMAL-ESPECIAL", header_format)

        # Fecha y título
        MESES_ES = {
            1: "Enero", 2: "Febrero", 3: "Marzo", 
            4: "Abril", 5: "Mayo", 6: "Junio", 
            7: "Julio", 8: "Agosto", 9: "Septiembre", 
            10: "Octubre", 11: "Noviembre", 12: "Diciembre"
        }
        mes_es = MESES_ES[self.date_from.month]
        worksheet.write('A6', f"LIBRO DE VENTAS - MES DE {mes_es.upper()} {self.date_from.year}", header_format)

        # Agregar encabezados con bordes
        worksheet.write('A9', 'Fecha de Emisión', header_format)  
        worksheet.write('B9', 'Serial Impresora', header_format)  # Nueva columna Serial Impresora
        worksheet.write('C9', 'Nro Z', header_format)  # Nueva columna Nro Z al lado de la Factura
        worksheet.write('D9', 'Concepto', header_format)
        worksheet.write('E9', 'Factura', header_format)
        worksheet.write('F9', 'Nota de Crédito', header_format)
        worksheet.write('G9', 'Documento Afectado', header_format)
        worksheet.write('H9', 'Monto de la Factura Afectada', header_format)
        worksheet.write('I9', 'Total', header_format)
        worksheet.write('J9', 'Razón Social', header_format)
        worksheet.write('K9', 'RIF', header_format)
        worksheet.write('L9', 'Total Exento', header_format)
        worksheet.write('M9', 'Base Imponible 16%', header_format)
        worksheet.write('N9', 'IVA 16%', header_format)
        worksheet.write('O9', 'Base Imponible 8%', header_format)
        worksheet.write('P9', 'IVA 8%', header_format)
        worksheet.write('Q9', 'Base Imponible 31%', header_format)
        worksheet.write('R9', 'IVA 31%', header_format)
        worksheet.write('S9', 'IGTF', header_format)

        # Continuar con el resto de la lógica de datos
        row = 9

        # Generación de detalles de facturas por cada reporte
        for record in report_data:
            for order in record.pos_order_ids:
                if order.ticket_fiscal:
                    # Cálculos de impuestos (8%, 16%, 31%)
                    base_imponible_exento = sum(line.price_subtotal for line in order.lines if any(tax.amount == 0 for tax in line.tax_ids))  # Base Exento
                    iva_exento = sum(line.price_subtotal_incl - line.price_subtotal for line in order.lines if any(tax.amount == 0 for tax in line.tax_ids))  # IVA Exento

                    base_imponible_16 = sum(line.price_subtotal for line in order.lines if any(tax.amount == 16 for tax in line.tax_ids))  # Base imponible 16%
                    iva_16 = sum(line.price_subtotal_incl - line.price_subtotal for line in order.lines if any(tax.amount == 16 for tax in line.tax_ids))  # IVA 16%

                    base_imponible_8 = sum(line.price_subtotal for line in order.lines if any(tax.amount == 8 for tax in line.tax_ids))  # Base imponible 8%
                    iva_8 = sum(line.price_subtotal_incl - line.price_subtotal for line in order.lines if any(tax.amount == 8 for tax in line.tax_ids))  # IVA 8%

                    base_imponible_31 = sum(line.price_subtotal for line in order.lines if any(tax.amount == 31 for tax in line.tax_ids))  # Base imponible 31%
                    iva_31 = sum(line.price_subtotal_incl - line.price_subtotal for line in order.lines if any(tax.amount == 31 for tax in line.tax_ids))  # IVA 31%

                    total_factura = order.amount_total
                    igtf = order.igtf_amount  # IGTF
                    #serial_impresora = order.serial_fiscal_pos or ''  # Serial de la impresora

                    # Obtener el valor de amount_total del pedido
                    amount_total = order.amount_total - igtf
                    # Obtener el valor del contacto
                    contacto = order.partner_id
                    # Obtener el valor del rif
                    rif = order.partner_id.identification_id or order.partner_id.rif or ''

                    # Si el rif no empieza por 'V-', 'J-' o 'E-', se le antepone 'V-'
                    if not (rif.startswith('V-') or rif.startswith('J-') or rif.startswith('E-')):
                        rif = 'V-' + rif
                    total_documento_afectado_total = 0
                    # Escribir "FC" si amount_total es positivo, "NC" si es negativo
                    concepto = '01' if amount_total > 0 else '03'
                    nota_credito = order.ticket_fiscal if amount_total < 0 else ''
                    factura = order.ticket_fiscal if amount_total > 0 else ''

                    # Verificar si la orden es un reembolso
                    if 'REFUND' in order.name.upper() or 'REEMBOLSO' in order.name.upper():
                        # Si es un reembolso, buscar la orden original
                        original_order_name = order.name.replace(' REFUND', '').replace(' REEMBOLSO', '').strip()
                        original_order = self.env['pos.order'].search([('name', '=', original_order_name)], limit=1)
                        
                        # Obtener el ticket fiscal de la orden original (si existe)
                        documento_afectado = original_order.ticket_fiscal if original_order else 'NO HUBO'
                        # Obtener el total de la orden original (si existe)
                        total_documento_afectado = original_order.amount_total if original_order else 0
                    else:
                        # Si no es un reembolso, no hay documento afectado
                        documento_afectado = ''
                        total_documento_afectado = 0
                    
                    if total_documento_afectado > 0:
                        total_documento_afectado_total = amount_total * -1

                    # Escribir los detalles en las filas
                    worksheet.write(row, 0, self._convert_to_caracas_timezone(order.date_order).strftime('%d/%m/%Y'), cell_format)
                    worksheet.write(row, 1, order.serial_fiscal or '', cell_format)  # Serial Impresora
                    worksheet.write(row, 2, record.number or '', cell_format)  # Nro Z
                    worksheet.write(row, 3, concepto or '', cell_format)  # Concepto
                    worksheet.write(row, 4, factura or '', cell_format)  # Usamos ticket_fiscal en lugar de order.name
                    worksheet.write(row, 5, nota_credito, number_format) # Nota de Crédito
                    worksheet.write(row, 6, documento_afectado, number_format) # Documento Afectado
                    worksheet.write(row, 7, total_documento_afectado_total, number_format) # Total Documento Afectado
                    worksheet.write(row, 8, amount_total, number_format) # Total
                    worksheet.write(row, 9, contacto.name or '', cell_format) #Contacto
                    worksheet.write(row, 10, rif, cell_format) # rif
                    worksheet.write(row, 11, base_imponible_exento, number_format) # Exento
                    worksheet.write(row, 12, base_imponible_16, number_format)  # Base 16%
                    worksheet.write(row, 13, iva_16, number_format)  # IVA 16%
                    worksheet.write(row, 14, base_imponible_8, number_format)  # Base 8%
                    worksheet.write(row, 15, iva_8, number_format)  # IVA 8%
                    worksheet.write(row, 16, base_imponible_31, number_format)  # Base 31%
                    worksheet.write(row, 17, iva_31, number_format)  # IVA 31%
                    worksheet.write(row, 18, igtf, number_format)  # IGTF

                    row += 1

                    total_row = row # Fila debajo del último dato

                    # Insertar sumatorias por columna usando write_formula
                    worksheet.write_formula(total_row, 8, f'=SUM(I10:I{row})', number_format)  # Total
                    worksheet.write_formula(total_row, 11, f'=SUM(L10:L{row})', number_format)  # Exento
                    worksheet.write_formula(total_row, 12, f'=SUM(M10:M{row})', number_format)  # Base 16%
                    worksheet.write_formula(total_row, 13, f'=SUM(N10:N{row})', number_format)  # IVA 16%
                    worksheet.write_formula(total_row, 14, f'=SUM(O10:O{row})', number_format)  # Base 8%
                    worksheet.write_formula(total_row, 15, f'=SUM(P10:P{row})', number_format)  # IVA 8%
                    worksheet.write_formula(total_row, 16, f'=SUM(Q10:Q{row})', number_format)  # Base 31%
                    worksheet.write_formula(total_row, 17, f'=SUM(R10:R{row})', number_format)  # IVA 31%
                    worksheet.write_formula(total_row, 18, f'=SUM(S10:S{row})', number_format)  # IGTF

        # Ajustar el ancho de las columnas de acuerdo al contenido
        worksheet.set_column('A:A', 30)  # Fecha de Emisión
        worksheet.set_column('B:B', 18)  # Serial Impresora
        worksheet.set_column('C:C', 15)  # Nro Z
        worksheet.set_column('D:D', 20)  # Concepto
        worksheet.set_column('E:E', 15)  # Factura
        worksheet.set_column('F:F', 15)  # Nota de Crédito
        worksheet.set_column('G:G', 15)  # Documento Afectado
        worksheet.set_column('H:H', 20)  # Total Factura Afectada
        worksheet.set_column('I:I', 20)  # Total
        worksheet.set_column('J:J', 20)  # Contacto
        worksheet.set_column('K:K', 20)  # RIF
        worksheet.set_column('L:L', 20)  # Exento
        worksheet.set_column('M:M', 25)  # Base Imponible 16%
        worksheet.set_column('N:N', 15)  # IVA 16%
        worksheet.set_column('O:O', 25)  # Base Imponible 16%
        worksheet.set_column('P:P', 15)  # IVA 8%
        worksheet.set_column('Q:Q', 25)  # Base Imponible 31%
        worksheet.set_column('R:R', 15)  # IVA 31%
        worksheet.set_column('S:S', 15)  # IGTF

        # Inicializar las variables de totales
        total_no_gravadas = 0
        total_base_16 = 0
        total_iva_16 = 0
        total_ventas_16 = 0

        total_base_31 = 0
        total_iva_31 = 0
        total_ventas_31 = 0

        total_base_8 = 0
        total_iva_8 = 0
        total_ventas_8 = 0

        total_colum_base = 0  # Asegúrate de inicializar las variables de columna
        total_colum_iva = 0
        total_colum_total = 0

        # Iterar sobre los registros de report_data (pos.report.z)
        for record in report_data:
            # Reiniciar los totales por cada 'record'
            total_no_gravadas_record = 0
            total_base_16_record = 0
            total_iva_16_record = 0
            total_base_31_record = 0
            total_iva_31_record = 0
            total_base_8_record = 0
            total_iva_8_record = 0

            # Iterar sobre las líneas de cada pedido
            for order in record.pos_order_ids:
                for line in order.lines:  # Asumiendo que 'lines' contiene las líneas de la venta
                    # Obtener los impuestos asociados a la línea de la orden
                    taxes = line.tax_ids  # 'tax_ids' contiene los impuestos aplicados

                    # Calcular el valor del impuesto para cada línea
                    for tax in taxes:
                        if tax.amount == 0:  # Si es un impuesto exento
                            total_no_gravadas_record += line.price_subtotal
                        elif tax.amount == 16:  # Si tiene IVA del 16%
                            total_base_16_record += line.price_subtotal
                            total_iva_16_record += line.price_subtotal * (tax.amount / 100)
                        elif tax.amount == 31:  # Si tiene IVA del 31%
                            total_base_31_record += line.price_subtotal
                            total_iva_31_record += line.price_subtotal * (tax.amount / 100)
                        elif tax.amount == 8:  # Si tiene IVA del 8%
                            total_base_8_record += line.price_subtotal
                            total_iva_8_record += line.price_subtotal * (tax.amount / 100)

            # Calcular los totales de ventas para cada tipo de IVA
            total_ventas_16_record = total_base_16_record + total_iva_16_record
            total_ventas_31_record = total_base_31_record + total_iva_31_record
            total_ventas_8_record = total_base_8_record + total_iva_8_record

            # Calcular los totales de la columna
            total_colum_base_record = total_base_8_record + total_base_16_record + total_base_31_record + total_no_gravadas_record
            total_colum_iva_record = total_iva_8_record + total_iva_16_record + total_iva_31_record
            total_colum_total_record = total_colum_base_record + total_colum_iva_record

            # Sumar a los totales generales
            total_no_gravadas += total_no_gravadas_record
            total_base_16 += total_base_16_record
            total_iva_16 += total_iva_16_record
            total_ventas_16 += total_ventas_16_record
            total_base_31 += total_base_31_record
            total_iva_31 += total_iva_31_record
            total_ventas_31 += total_ventas_31_record
            total_base_8 += total_base_8_record
            total_iva_8 += total_iva_8_record
            total_ventas_8 += total_ventas_8_record
            total_colum_base += total_colum_base_record
            total_colum_iva += total_colum_iva_record
            total_colum_total += total_colum_total_record

        # Crear lista de detalles
        details = [
            ('VENTAS INTERNAS NO GRAVADAS', total_no_gravadas, 0, total_no_gravadas),
            ('VENTAS INTERNAS GRAVADAS POR ALICUOTA REDUCIDA (8%)', total_base_8, total_iva_8, total_ventas_8),
            ('VENTAS INTERNAS GRAVADAS POR ALICUOTA GENERAL (16%)', total_base_16, total_iva_16, total_ventas_16),
            ('VENTAS INTERNAS GRAVADAS POR ALICUOTA ADICIONAL (31%)', total_base_31, total_iva_31, total_ventas_31),
        ]

        row += 2
        worksheet.write_blank(row, 0, '', cell_format)
        worksheet.write_blank(row + 1, 0, '', cell_format)

        # Escribir los detalles en las filas del Excel
        for detail in details:
            worksheet.write(row, 0, detail[0], cell_format)
            worksheet.write(row, 1, detail[1], number_format)
            worksheet.write(row, 2, detail[2], number_format)
            worksheet.write(row, 3, detail[3], number_format)
            row += 1

        # Escribir el total final
        worksheet.write(row, 0, 'TOTAL VENTAS Y DEBITO FISCAL PARA EFECTOS DE DETERMINACION', cell_format)
        worksheet.write(row, 1, total_colum_base, number_format)
        worksheet.write(row, 2, total_colum_iva, number_format)
        worksheet.write(row, 3, total_colum_total, number_format)

        workbook.close()

        excel_data = output.getvalue()
        self.excel_file = base64.encodebytes(excel_data)
        self.file_name = f'Reporte_Z_Detallado_{mes_es.upper()}_{self.date_from.year}.xlsx'
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'pos.report.z.excel.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'new',
        }
        
    def _generate_normal_report(self):
        
        #_logger.info(f"Generando reporte Z para impresoras: {self.fiscal_printer_id.ids}")
        self.ensure_one()

        # Obtener las fechas con zona horaria de Caracas para cada día del rango
        dates_in_range = [self.date_from + timedelta(days=i) for i in range((self.date_to - self.date_from).days + 1)]
        report_data = []

        for date in dates_in_range:
            start_dt, end_dt = self._get_caracas_datetime_range(date)
            day_data  = self.env['pos.report.z'].search([
                ('date', '>=', start_dt),
                ('date', '<=', end_dt),
                #('x_fiscal_printer_id', 'in', self.fiscal_printer_id.ids)
            ])
            report_data.extend(day_data)

        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Libro de Ventas')
        MESES_ES = {
            1: "Enero", 2: "Febrero", 3: "Marzo", 
            4: "Abril", 5: "Mayo", 6: "Junio", 
            7: "Julio", 8: "Agosto", 9: "Septiembre", 
            10: "Octubre", 11: "Noviembre", 12: "Diciembre"
        }
        # Formats
        company_format = workbook.add_format({'bold': True, 'align': 'left', 'valign': 'vcenter'})
        header_format = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'text_wrap': True})
        subheader_format = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1})
        cell_format = workbook.add_format({'align': 'left', 'valign': 'vcenter', 'border': 1})
        number_format = workbook.add_format({'align': 'right', 'valign': 'vcenter', 'border': 1, 'num_format': '#,##0.00'})

        # Company information
        company = self.env.company
        worksheet.write('A1', company.name, company_format)
        worksheet.write('A2', f"N° DE RIF.: {company.vat}", company_format)
        worksheet.write('A3', "CONTRIBUYENTE FORMAL-ESPECIAL", company_format)

        # Dirección completa
        full_address = ", ".join(filter(None, [
            company.street,
            company.street2,
            company.city,
            company.state_id.name if company.state_id else None,
            company.country_id.name if company.country_id else None
        ]))
        worksheet.write('A4', full_address, company_format)
        worksheet.write('A5', "LIBRO DE VENTAS", company_format)
        mes_es = MESES_ES[self.date_from.month]
        worksheet.write('A6', f"MES DE {mes_es.upper()} {self.date_from.year}", company_format)
        # Subheaders: Agregar la nueva columna "Nro Z"
        worksheet.merge_range('A9:A10', 'Fecha de Emision', header_format)
        worksheet.merge_range('B9:M9', 'MAQUINA FISCAL', subheader_format)
        worksheet.write('B10', 'Factura Inicial', header_format)
        worksheet.write('C10', 'Factura Final', header_format)
        worksheet.write('D10', 'Nro Z', header_format)
        worksheet.write('E10', 'Serial Impresora', header_format)  # Nueva columna
        worksheet.write('F10', 'Total', header_format)
        worksheet.write('G10', 'Exento', header_format)
        worksheet.write('H10', 'Base Imponible 16%', header_format)
        worksheet.write('I10', 'IVA 16%', header_format)
        worksheet.write('J10', 'Base Imponible 8%', header_format)
        worksheet.write('K10', 'IVA 8%', header_format)
        worksheet.write('L10', 'Base Imponible 31%', header_format)  # Nueva columna para Base Imponible 31%
        worksheet.write('M10', 'IVA 31%', header_format)  # Nueva columna para IVA 31%

        worksheet.merge_range('N9:X9', 'Nota de Credito', subheader_format)
        worksheet.write('N10', 'NC Inicial', header_format)
        worksheet.write('O10', 'NC Final', header_format)
        worksheet.write('P10', 'Facturas Afectadas', header_format)
        worksheet.write('Q10', 'Total', header_format)
        worksheet.write('R10', 'Exento', header_format)
        worksheet.write('S10', 'Base Imponible 16%', header_format)
        worksheet.write('T10', 'IVA 16%', header_format)
        worksheet.write('U10', 'Base Imponible 8%', header_format)
        worksheet.write('V10', 'IVA 8%', header_format)
        worksheet.write('W10', 'Base Imponible 31%', header_format)  # Nueva columna para Base Imponible 31%
        worksheet.write('X10', 'IVA 31%', header_format)  # Nueva columna para IVA 31%

        worksheet.merge_range('Y9:Y10', 'Total de Ventas Consolidadas Bs', header_format)
        #worksheet.merge_range('Q9:Q10', 'Total Ventas Mas IGTF Consolidadas Bs', header_format)

        # Luego de escribir los títulos, ajustamos el ancho de cada columna
        worksheet.set_column('A:A', 20)  # Ancho fijo para la columna A
        worksheet.set_column('B:B', 25)  # Ancho fijo para la columna B
        worksheet.set_column('C:C', 25)  # Ancho fijo para la columna C
        worksheet.set_column('D:D', 15)  # Ancho fijo para la columna D
        worksheet.set_column('E:E', 20)  # Ancho fijo para la columna E
        worksheet.set_column('F:F', 15)  # Ancho fijo para la columna F
        worksheet.set_column('G:G', 15)  # Ancho fijo para la columna G
        worksheet.set_column('H:H', 25)  # Ancho fijo para la columna H
        worksheet.set_column('I:I', 15)  # Ancho fijo para la columna I
        worksheet.set_column('J:J', 25)  # Ancho fijo para la columna J
        worksheet.set_column('K:K', 15)  # Ancho fijo para la columna K
        worksheet.set_column('L:L', 25)  # Ancho fijo para la columna L
        worksheet.set_column('M:M', 25)  # Ancho fijo para la columna M
        worksheet.set_column('N:N', 15)  # Ancho fijo para la columna N
        worksheet.set_column('O:O', 155)  # Ancho fijo para la columna O
        worksheet.set_column('P:P', 25)  # Ancho fijo para la columna P
        worksheet.set_column('Q:Q', 25)  # Ancho fijo para la columna Q
        worksheet.set_column('R:R', 25)  # Ancho fijo para la columna R
        worksheet.set_column('S:S', 25)  # Ancho fijo para la columna S
        worksheet.set_column('T:T', 25)  # Ancho fijo para la columna T
        worksheet.set_column('U:U', 25)  # Ancho fijo para la columna U
        worksheet.set_column('V:V', 25)  # Ancho fijo para la columna V
        worksheet.set_column('W:W', 25)  # Ancho fijo para la columna W
        worksheet.set_column('X:X', 25)  # Ancho fijo para la columna X
        worksheet.set_column('Y:Y', 25)  # Ancho fijo para la columna Y
        

        row = 10
        total_ventas_consolidadas = 0
        total_igtf_consolidadas = 0
        total_ventas_mas_igtf = 0
        # Inicializar total_ventas_linea
        total_ventas_linea = 0  # <-- Inicialización de la variable

        for record in report_data:
            col = 0
            factura_inicial = ''
            factura_final = ''
            nc_inicial = ''
            nc_final = ''
            serial_maquina = ''
            serial_nc = ''
            facturas_afectadas_list = []
            

            for order in record.pos_order_ids:
                if not order.ticket_fiscal:
                    continue  # Si no tiene ticket fiscal, lo ignoramos

                name_upper = order.name.upper()

                if 'REFUND' in name_upper or 'REEMBOLSO' in name_upper:
                    # Nota de Crédito
                    if not nc_inicial:
                        nc_inicial = order.ticket_fiscal
                        serial_nc = order.serial_fiscal  # Guardamos el serial de la primera NC

                    nc_final = order.ticket_fiscal

                    # Buscar la factura original afectada
                    posible_original_name = order.name.replace(' REFUND', '').replace(' REEMBOLSO', '').strip()
                    original_order = self.env['pos.order'].search([('name', '=', posible_original_name)], limit=1)

                    if original_order and original_order.ticket_fiscal:
                        facturas_afectadas_list.append(original_order.ticket_fiscal)

                else:
                     # Pedido normal (venta)
                    if not factura_inicial:
                        factura_inicial = order.ticket_fiscal
                        serial_maquina = order.serial_fiscal  # Guardamos el serial de la primera factura normal

                    factura_final = order.ticket_fiscal

            # Asegurar que solo haya una factura afectada (no la NC)
            facturas_afectadas_str = " / ".join(set(facturas_afectadas_list))

            # Si no hay NC, mostrar "NO HUBO"
            if not nc_inicial:
                nc_inicial = ''
                nc_final = ''
                facturas_afectadas_str = ''

            # Si no hay seriales, mostrar "NO HUBO"
            serial_maquina = serial_maquina or 'NO HUBO'
            serial_nc = serial_nc or 'NO HUBO'
            # Convertir la fecha a la zona horaria de Caracas
            date_in_caracas = self._convert_to_caracas_timezone(record.date)

            worksheet.write(row, col,  date_in_caracas.strftime('%d/%m/%Y'), cell_format)

            total_ventas = (
                getattr(record, 'total_exempt_pos', 0) + 
                getattr(record, 'total_base_iva_16_pos', 0) + 
                getattr(record, 'total_iva_16_pos', 0) +
                getattr(record, 'total_base_iva_8_pos', 0) + 
                getattr(record, 'total_iva_8_pos', 0) + 
                getattr(record, 'total_base_iva_31_pos', 0) + 
                getattr(record, 'total_iva_31_pos', 0) 
            ) - abs(getattr(record, 'total_exempt_pos_nc', 0)) - abs(getattr(record, 'total_base_iva_16_pos_nc', 0)) - abs(getattr(record, 'total_iva_16_pos_nc', 0)) - abs(getattr(record, 'total_iva_8_pos_nc', 0)) - abs(getattr(record, 'total_base_iva_8_pos_nc', 0)) - abs(getattr(record, 'total_iva_31_pos_nc', 0)) - abs(getattr(record, 'total_base_iva_31_pos_nc', 0))


            
            
            # Maquina Fiscal
            worksheet.write(row, col + 1, factura_final or 'NO HUBO', cell_format)
            worksheet.write(row, col + 2, factura_inicial or 'NO HUBO', cell_format)
            # Nueva columna "Nro Z"
            worksheet.write(row, col + 3, record.number or '', cell_format)  # Mostrar el número Z
            # Escribimos en la columna col+4
            worksheet.write(row, col + 4, serial_maquina, cell_format)
            worksheet.write(row, col + 5, (
                getattr(record, 'total_exempt_pos', 0) +
                getattr(record, 'total_base_iva_16_pos', 0) +
                getattr(record, 'total_iva_16_pos', 0) +
                getattr(record, 'total_base_iva_8_pos', 0) +
                getattr(record, 'total_iva_8_pos', 0) + 
                getattr(record, 'total_base_iva_31_pos', 0) +
                getattr(record, 'total_iva_31_pos', 0)
            ), number_format)
            worksheet.write(row, col + 6, getattr(record, 'total_exempt_pos', 0), number_format)
            worksheet.write(row, col + 7, getattr(record, 'total_base_iva_16_pos', 0), number_format)
            worksheet.write(row, col + 8, getattr(record, 'total_iva_16_pos', 0), number_format)
            worksheet.write(row, col + 9, getattr(record, 'total_base_iva_8_pos', 0), number_format)
            worksheet.write(row, col + 10, getattr(record, 'total_iva_8_pos', 0), number_format)
            worksheet.write(row, col + 11, getattr(record, 'total_base_iva_31_pos', 0), number_format)
            worksheet.write(row, col + 12, getattr(record, 'total_iva_31_pos', 0), number_format)
            # === CAMBIO IMPORTANTE: obtener el serial_fiscal desde los pedidos asociados ===
            # Si tu modelo pos.report.z tiene un campo one2many/many2many a pos.order (pos_order_ids),
            # y cada pos.order tiene un campo serial_fiscal, lo concatenamos:
            if record.pos_order_ids:
                seriales = []
                for order in record.pos_order_ids:
                    if order.serial_fiscal:
                        seriales.append(order.serial_fiscal)
                # Si hay varios pedidos, los concatenas con coma, guión, salto de línea, etc.
                serial_fiscal_str = ", ".join(seriales) if seriales else ""
            else:
                serial_fiscal_str = "NO HUBO"

            
            
            
            
            # Nota de Credito
            worksheet.write(row, col + 13, nc_final or 'NO HUBO', cell_format)
            worksheet.write(row, col + 14, nc_inicial or 'NO HUBO', cell_format)
            worksheet.write(row, col + 15, facturas_afectadas_str or 'NO HUBO', cell_format)
            worksheet.write(row, col + 16, (
                getattr(record, 'total_exempt_pos_nc', 0) +
                getattr(record, 'total_base_iva_16_pos_nc', 0) +
                getattr(record, 'total_iva_16_pos_nc', 0) +
                getattr(record, 'total_base_iva_8_pos_nc', 0) +
                getattr(record, 'total_iva_8_pos_nc', 0) +
                getattr(record, 'total_base_iva_31_pos_nc', 0) +
                getattr(record, 'total_iva_31_pos_nc', 0)
            ), number_format)
            worksheet.write(row, col + 17, getattr(record, 'total_exempt_pos_nc', 0), number_format)
            worksheet.write(row, col + 18, getattr(record, 'total_base_iva_16_pos_nc', 0), number_format)
            worksheet.write(row, col + 19, getattr(record, 'total_iva_16_pos_nc', 0), number_format)
            worksheet.write(row, col + 20, getattr(record, 'total_base_iva_8_pos_nc', 0), number_format)
            worksheet.write(row, col + 21, getattr(record, 'total_iva_8_pos_nc', 0), number_format)
            worksheet.write(row, col + 22, getattr(record, 'total_base_iva_31_pos_nc', 0), number_format)
            worksheet.write(row, col + 23, getattr(record, 'total_iva_31_pos_nc', 0), number_format)
            worksheet.write(row, col + 24, total_ventas, number_format)

            #row += 1
            

            # === CAMBIO IMPORTANTE: obtener el serial_fiscal desde los pedidos asociados ===
            # Si tu modelo pos.report.z tiene un campo one2many/many2many a pos.order (pos_order_ids),
            # y cada pos.order tiene un campo serial_fiscal, lo concatenamos:
            if record.pos_order_ids:
                seriales = []
                for order in record.pos_order_ids:
                    if order.serial_fiscal:
                        seriales.append(order.serial_fiscal)
                # Si hay varios pedidos, los concatenas con coma, guión, salto de línea, etc.
                serial_fiscal_str = ", ".join(seriales) if seriales else ""
            else:
                serial_fiscal_str = ""
            # Escribimos en la columna col+4
            #worksheet.write(row, col + 10, serial_nc, cell_format)
            
            # Manual
            # worksheet.write(row, col + 11, '', cell_format)
            # worksheet.write(row, col + 12, '', cell_format)
            # worksheet.write(row, col + 13, 0, number_format)
            # # === CAMBIO IMPORTANTE: obtener el serial_fiscal desde los pedidos asociados ===
            # # Si tu modelo pos.report.z tiene un campo one2many/many2many a pos.order (pos_order_ids),
            # # y cada pos.order tiene un campo serial_fiscal, lo concatenamos:
            # if record.pos_order_ids:
            #     seriales = []
            #     for order in record.pos_order_ids:
            #         if order.serial_fiscal:
            #             seriales.append(order.serial_fiscal)
            #     # Si hay varios pedidos, los concatenas con coma, guión, salto de línea, etc.
            #     serial_fiscal_str = ", ".join(seriales) if seriales else ""
            # else:
            #     serial_fiscal_str = ""
            # # Escribimos en la columna col+4
            # worksheet.write(row, col + 14, '', cell_format)
            
            
            total_igtf = getattr(record, 'total_igtf_pos', 0) - abs(getattr(record, 'total_igtf_pos_nc', 0))
            #total_ventas_mas_igtf += total_ventas_mas_igtf_dia

            
            

            # Totals
            total_ventas_consolidadas += (getattr(record, 'total_exempt_pos', 0) +
                                      getattr(record, 'total_base_iva_16_pos', 0) +
                                      getattr(record, 'total_iva_16_pos', 0) +
                                      getattr(record, 'total_base_iva_8_pos', 0) +
                                      getattr(record, 'total_iva_8_pos', 0) +
                                      getattr(record, 'total_base_iva_31_pos', 0) +
                                      getattr(record, 'total_iva_31_pos', 0))

            row += 1

        worksheet.write(row, 24, total_ventas_consolidadas, number_format)

        # Inicializar las variables de totales
        total_no_gravadas = 0
        total_base_16 = 0
        total_iva_16 = 0
        total_ventas_16 = 0

        total_base_31 = 0
        total_iva_31 = 0
        total_ventas_31 = 0

        total_base_8 = 0
        total_iva_8 = 0
        total_ventas_8 = 0

        total_colum_base = 0  # Asegúrate de inicializar las variables de columna
        total_colum_iva = 0
        total_colum_total = 0

        # Iterar sobre los registros de report_data (pos.report.z)
        for record in report_data:
            # Reiniciar los totales por cada 'record'
            total_no_gravadas_record = 0
            total_base_16_record = 0
            total_iva_16_record = 0
            total_base_31_record = 0
            total_iva_31_record = 0
            total_base_8_record = 0
            total_iva_8_record = 0

            # Iterar sobre las líneas de cada pedido
            for order in record.pos_order_ids:
                for line in order.lines:  # Asumiendo que 'lines' contiene las líneas de la venta
                    # Obtener los impuestos asociados a la línea de la orden
                    taxes = line.tax_ids  # 'tax_ids' contiene los impuestos aplicados

                    # Calcular el valor del impuesto para cada línea
                    for tax in taxes:
                        if tax.amount == 0:  # Si es un impuesto exento
                            total_no_gravadas_record += line.price_subtotal
                        elif tax.amount == 16:  # Si tiene IVA del 16%
                            total_base_16_record += line.price_subtotal
                            total_iva_16_record += line.price_subtotal * (tax.amount / 100)
                        elif tax.amount == 31:  # Si tiene IVA del 31%
                            total_base_31_record += line.price_subtotal
                            total_iva_31_record += line.price_subtotal * (tax.amount / 100)
                        elif tax.amount == 8:  # Si tiene IVA del 8%
                            total_base_8_record += line.price_subtotal
                            total_iva_8_record += line.price_subtotal * (tax.amount / 100)

            # Calcular los totales de ventas para cada tipo de IVA
            total_ventas_16_record = total_base_16_record + total_iva_16_record
            total_ventas_31_record = total_base_31_record + total_iva_31_record
            total_ventas_8_record = total_base_8_record + total_iva_8_record

            # Calcular los totales de la columna
            total_colum_base_record = total_base_8_record + total_base_16_record + total_base_31_record + total_no_gravadas_record
            total_colum_iva_record = total_iva_8_record + total_iva_16_record + total_iva_31_record
            total_colum_total_record = total_colum_base_record + total_colum_iva_record

            # Sumar a los totales generales
            total_no_gravadas += total_no_gravadas_record
            total_base_16 += total_base_16_record
            total_iva_16 += total_iva_16_record
            total_ventas_16 += total_ventas_16_record
            total_base_31 += total_base_31_record
            total_iva_31 += total_iva_31_record
            total_ventas_31 += total_ventas_31_record
            total_base_8 += total_base_8_record
            total_iva_8 += total_iva_8_record
            total_ventas_8 += total_ventas_8_record
            total_colum_base += total_colum_base_record
            total_colum_iva += total_colum_iva_record
            total_colum_total += total_colum_total_record

        # Crear lista de detalles
        details = [
            ('VENTAS INTERNAS NO GRAVADAS', total_no_gravadas, 0, total_no_gravadas),
            ('VENTAS INTERNAS GRAVADAS POR ALICUOTA GENERAL (16%)', total_base_16, total_iva_16, total_ventas_16),
            ('VENTAS INTERNAS GRAVADAS POR ALICUOTA ADICIONAL (31%)', total_base_31, total_iva_31, total_ventas_31),
            ('VENTAS INTERNAS GRAVADAS POR ALICUOTA REDUCIDA (8%)', total_base_8, total_iva_8, total_ventas_8),
        ]

        row += 2
        worksheet.write_blank(row, 0, '', cell_format)
        worksheet.write_blank(row + 1, 0, '', cell_format)

        # Escribir los detalles en las filas del Excel
        for detail in details:
            worksheet.write(row, 0, detail[0], cell_format)
            worksheet.write(row, 1, detail[1], number_format)
            worksheet.write(row, 2, detail[2], number_format)
            worksheet.write(row, 3, detail[3], number_format)
            row += 1

        # Escribir el total final
        worksheet.write(row, 0, 'TOTAL VENTAS Y DEBITO FISCAL PARA EFECTOS DE DETERMINACION', cell_format)
        worksheet.write(row, 1, total_colum_base, number_format)
        worksheet.write(row, 2, total_colum_iva, number_format)
        worksheet.write(row, 3, total_colum_total, number_format)

        # Adjust column widths, agregando espacio para "Nro Z"
        for i, width in enumerate([15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 25, 25, 25, 25]):
            worksheet.set_column(i, i, width)

        workbook.close()
        
        excel_data = output.getvalue()
        self.excel_file = base64.encodebytes(excel_data)
        self.file_name = f'Libro_de_Ventas_ {mes_es.upper()}.xlsx'
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'pos.report.z.excel.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'new',
        }