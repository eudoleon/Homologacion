import time
import base64
import xlsxwriter
from odoo import fields, models, api, _
from odoo.exceptions import UserError
from odoo.exceptions import ValidationError
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT as DATETIME_FORMAT
from datetime import datetime, date, timedelta
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
from io import BytesIO


DATE_FORMAT = "%Y-%m-%d"   # Asegúrate de que coincida con tu formato en el servidor
class FiscalBookWizard(models.TransientModel):
    """
    Sales/Purchase fiscal book wizard
    """
    _name = "account.fiscal.book.wizard"
    _description = "Wizard para generar Libros Fiscales (Venta/Compra)"

    TYPE = [
        ("sale", _("Venta")),
        ("purchase", _("Compra")),
    ]

    type = fields.Selection(TYPE, string="Tipo de Libro", readonly=True)
    date_start = fields.Date(string="Fecha Inicio", required=True)
    date_end = fields.Date(string="Fecha Fin", required=True)

    @api.model
    def default_get(self, field_list):
        fiscal_book_obj = self.env['account.fiscal.book']
        fiscal_book = fiscal_book_obj.browse(self._context.get('active_id'))
        res = super(FiscalBookWizard, self).default_get(field_list)
        local_period = fiscal_book_obj.get_time_period(fiscal_book.time_period, fiscal_book)
        res.update({'type': fiscal_book.type})
        res.update({'date_start': local_period.get('dt_from', '')})
        res.update({'date_end': local_period.get('dt_to', '')})
        if fiscal_book.fortnight == 'first':
            date_obj = local_period.get('dt_to', '').split('-')
            res.update({'date_end': "%0004d-%02d-15" % (int(date_obj[0]), int(date_obj[1]))})
        elif fiscal_book.fortnight == 'second':
            date_obj = local_period.get('dt_to', '').split('-')
            res.update({'date_start': "%0004d-%02d-16" % (int(date_obj[0]), int(date_obj[1]))})
        return res

    def check_report_xlsx(self):
        """
        Genera el libro en formato XLSX (Ventas o Compras),
        aplicando un diseño “profesional” acorde a la normativa.
        """
        if self.type == 'purchase':
            return self._generate_purchase_book()
        else:
            return self._generate_sales_book()

    def _generate_purchase_book(self):
        file_name = 'Libro_Compra.xlsx'
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {
            'in_memory': True,
            'strings_to_numbers': False
        })
        sheet = workbook.add_worksheet('Libro Compra')

        formats = self.set_formats(workbook)
        datos_compras, datos_compras_ajustes = self.get_datas_compras()
        if not datos_compras:
            raise UserError('No hay datos disponibles para el período seleccionado')

        sheet.set_zoom(90)
        sheet.freeze_panes(7, 1)

        col_widths = [
            10, 14, 18, 28, 22, 18, 18, 18, 18, 24, 24, 24,
            22, 22, 22, 16, 22, 22, 22, 16, 22, 22, 16, 22, 20, 26
        ]
        for i, width in enumerate(col_widths):
            col_letter = xlsxwriter.utility.xl_col_to_name(i + 1)
            sheet.set_column(f'{col_letter}:{col_letter}', width)

        row = 3

        formats['encabezado_izquierda'] = workbook.add_format({
            'bold': True,
            'font_color': 'black',
            'font_size': 11,
            'align': 'left',
            'valign': 'vcenter',
        })

        sheet.merge_range(f'B{row}:H{row}', datos_compras[0]['company_name'], formats['encabezado_izquierda'])
        row += 1
        sheet.merge_range(f'B{row}:H{row}', f"RIF: {datos_compras[0]['company_rif']}", formats['encabezado_izquierda'])
        row += 1
        date_start = datetime.strptime(str(self.date_start), DATE_FORMAT).date()
        date_end = datetime.strptime(str(self.date_end), DATE_FORMAT).date()
        sheet.merge_range(f'B{row}:H{row}', f"Libro de compras del: {date_start.strftime('%d/%m/%Y')} al: {date_end.strftime('%d/%m/%Y')}", formats['encabezado_izquierda'])

        row += 2
        sheet.merge_range(f'N{row}:R{row}', 'COMPRAS DE IMPORTACIONES', formats['title'])
        sheet.merge_range(f'S{row}:Y{row}', 'COMPRAS NACIONALES', formats['title'])

        row += 1
        headers = [
            'Nº De Oper.', 'Fecha del  Documento', 'Nº de RIF', 'Nombre ó Razón Social', 'Tipo de transacción',
            'Nº De Factura', 'Nro. Nota de Débito', 'Nº De Nota De Credito', 'Nº De Control',
            'Nº de Planilla  de Importación (C-80 o C-81)', 'Nº de Expediente  de Importación', 'Nº De Documento  Afectado',
            'Total Compras Incluyendo el IVA', 'Compras sin Derecho a Crédito', 'Base Imponible Importaciones',
            'Impuesto IVA  16%', 'Impuesto (I.V.A) Importaciones',
            'Compras sin Derecho a Crédito', 'Base Imponible Alicuota Reducida', '8% Alicuota Reducida',
            'Impuesto (I.V.A) Alicuota Reducida', 'Base Imponible Alicuota General', '16% Alicuota General',
            'Impuesto (I.V.A) Alicuota General', 'IVA Retenido (Al Vendedor)', 'Nº De Comprobante De Retención De IVA'
        ]

        col = 1
        for title in headers:
            sheet.write(row, col, title, formats['title'])
            col += 1

        row += 1
        row_data_start = row
        contador = 1

        for d in datos_compras:
            col = 1
            sheet.write(row, col, contador); col += 1
            sheet.write(row, col, d['emission_date']); col += 1
            sheet.write(row, col, d['partner_vat']); col += 1
            sheet.write(row, col, d['partner_name']); col += 1
            sheet.write(row, col, d['type']); col += 1
            sheet.write(row, col, d['invoice_number'] or '', formats['string']); col += 1
            sheet.write(row, col, d['debit_affected'] or '', formats['string']); col += 1
            sheet.write(row, col, d['credit_affected'] if d['doc_type'] == 'N/CR' else '', formats['string']); col += 1
            sheet.write(row, col, d['ctrl_number'], formats['string']); col += 1
            sheet.write(row, col, d['nro_planilla'], formats['string']); col += 1
            sheet.write(row, col, d['nro_expediente'], formats['string']); col += 1
            sheet.write(row, col, d['affected_invoice'] or '', formats['string']); col += 1
            sheet.write(row, col, d['total_with_iva'], formats['number']); col += 1
            sheet.write(row, col, d['vat_exempt'], formats['number']); col += 1
            sheet.write(row, col, d['vat_general_base_importaciones'], formats['number']); col += 1
            sheet.write(row, col, d['vat_general_rate_importaciones'], formats['number']); col += 1
            sheet.write(row, col, d['vat_general_tax_importaciones'], formats['number']); col += 1
            sheet.write(row, col, d['vat_exempt'], formats['number']); col += 1
            sheet.write(row, col, d['vat_reduced_base'], formats['number']); col += 1
            sheet.write(row, col, d['vat_reduced_rate'], formats['number']); col += 1
            sheet.write(row, col, d['vat_reduced_tax'], formats['number']); col += 1
            sheet.write(row, col, d['vat_general_base'], formats['number']); col += 1
            sheet.write(row, col, d['vat_general_rate'], formats['number']); col += 1
            sheet.write(row, col, d['vat_general_tax'], formats['number']); col += 1
            sheet.write(row, col, d['get_wh_vat'], formats['number']); col += 1
            sheet.write(row, col, str(d['wh_number']), formats['number_sd'])
            row += 1
            contador += 1

        row_totals = row
        sheet.write(row, 12, 'TOTALES', formats['title'])
        for idx in range(13, 26):
            col_letter = xlsxwriter.utility.xl_col_to_name(idx)
            formula = f'=SUM({col_letter}{row_data_start}:{col_letter}{row_totals - 1})'
            sheet.write_formula(row, idx, formula, formats['title_number'])

            # Agregar resumen formateado como el modelo
        row += 3
        formats['resumen_total'] = workbook.add_format({
            'bold': True,
            'align': 'right',
            'valign': 'vcenter',
            'font_color': 'black',
            'bg_color': '#FFFF99',
            'border': 1
        })
        formats['resumen_label'] = workbook.add_format({
            'align': 'center',
            'bold': True,
            'valign': 'vcenter',
            'font_color': 'black',
            'bg_color': '#FFFF99',
            'border': 1
        })
        formats['resumen_items'] = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'font_color': 'black',
            'border': 1
        })
        formats['resumen_value'] = workbook.add_format({
            'align': 'right',
            'valign': 'vcenter',
            'num_format': '#,##0.00',
            'border': 1
        })

        # Título del resumen
        sheet.merge_range(f'L{row}:T{row}', 'Resumen de Libro de Compras', formats['resumen_label'])
        # justo en la misma fila, columna U (índice 20)
        sheet.write(f'U{row}:U{row}', 'Base Imponible', formats['resumen_label'])
        # ahora sí avanzamos una fila para los ítems
        row += 1

        # Filas de detalle del resumen
        resumen_items = [
            ('Compras Internas no Gravadas y/o Sin Derecho a Crédito Fiscal', f'=SUM(N{row_data_start}:N{row_totals - 1})'),
            ('Compras Internas gravadas por Alicuota General',          f'=SUM(V{row_data_start}:V{row_totals - 1})'),
            ('Compras Internas gravadas por Alicuota General mas Alicuota Adicional', '0'),
            ('Compras Internas gravadas por Alicuota Reducida',        f'=SUM(R{row_data_start}:R{row_totals - 1})'),
            ('Importaciones gravadas Alícuota General',               f'=SUM(P{row_data_start}:P{row_totals - 1})'),
            ('Importaciones gravadas por Alícuota General más Adicional', '0'),
            ('Importaciones gravadas por Alicuota Reducida',          f'=SUM(T{row_data_start}:T{row_totals - 1})'),
        ]

        for label, formula in resumen_items:
            sheet.merge_range(f'L{row}:T{row}', label, formats['resumen_items'])
            if formula.startswith('='):
                sheet.write_formula(f'U{row}:U{row}', formula, formats['resumen_value'])
            else:
                sheet.write       (f'U{row}:U{row}', float(formula), formats['resumen_value'])
            row += 1

        # Total compras y créditos fiscales
        sheet.merge_range(f'L{row}:T{row}', 'Total Compras y Créditos Fiscales', formats['resumen_label'])
        sheet.write_formula(f'U{row}:U{row}', f'=SUM(U{row - len(resumen_items)}:U{row - 1})', formats['resumen_total'])
        row += 1

        # Total IVA Retenido
        sheet.merge_range(f'L{row}:T{row}', 'Total IVA Retenido', formats['resumen_label'])
        sheet.write_formula(f'U{row}:U{row}', f'=SUM(Z{row_data_start}:Z{row_totals - 1})', formats['resumen_total'])

        # Guardar y cerrar workbook
        workbook.close()
        file_base64 = base64.b64encode(output.getvalue())
        attachment_id = self.env['ir.attachment'].sudo().create({
            'name': 'Libro de Compra',
            'datas': file_base64
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment_id.id}?download=true',
            'target': 'current',
        }


    def _generate_sales_book(self):
        import logging
        _logger = logging.getLogger(__name__)

        file_name = 'Libro_Venta.xlsx'
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {
            'in_memory': True,
            'strings_to_numbers': True,
        })
        sheet = workbook.add_worksheet('Libro de Venta')
        formats = self.set_formats(workbook)

        datos_ventas, datos_ventas_ajustes = self.get_datas_ventas()
        if not datos_ventas:
            raise UserError('No hay datos disponibles para el período seleccionado')

        # 1) CONFIGURACIÓN GLOBAL
        sheet.set_row(2, 22)
        sheet.set_row(3, 18)
        sheet.set_row(5, 30)
        sheet.freeze_panes(6, 1)
        sheet.set_zoom(90)

        # Anchos de columna B:U
        widths = [12,15,30,14,16,16,16,16,20,16,16,14,18,18,18,18,12,18,12,18,12]
        for idx, w in enumerate(widths, start=1):
            col = xlsxwriter.utility.xl_col_to_name(idx)
            sheet.set_column(f'{col}:{col}', w)

        # 2) ENCABEZADO SUPERIOR
        row = 2
        fmt_left = workbook.add_format({
            'bold': True, 'font_size': 12,
            'align': 'left', 'valign': 'vcenter'
        })
        datos = datos_ventas[0]
        sheet.merge_range(f'B{row}:H{row}', datos['company_name'], fmt_left)
        sheet.merge_range(f'B{row+1}:H{row+1}', f"RIF: {datos['company_rif']}", fmt_left)
        date_start = datetime.strptime(str(self.date_start), DATE_FORMAT).date().strftime('%d/%m/%Y')
        date_end   = datetime.strptime(str(self.date_end),   DATE_FORMAT).date().strftime('%d/%m/%Y')
        sheet.merge_range(f'B{row+2}:H{row+2}', f"Libro de Venta del: {date_start} al: {date_end}", fmt_left)

        # 4) ENCABEZADO DE COLUMNAS
        row = 6
        headers = [
            'Nº De Oper.', 'Fecha del Documento', 'RIF', 'Nombre ó Razón Social',
            'Tipo de Transaccion', 'Nº De Factura', 'Nº De Nota De Debito',
            'Nº De Nota De Credito', 'Nº De Control', 'Nº de Documento Afectado',
            'Total Ventas Incluyendo el IVA', 'Sin derecho a Credito',
            'Base Imponible Alicuota Reducida', '8 % Alicuota Reducida',
            'Impuesto IVA Alicuota Reducida', 'Base Imponible Alicuota General',
            '16 % Alicuota General', 'Impuesto IVA Alicuota General',
            'IVA Retenido', 'Nº De Comprobante De Retención De IVA',
        ]
        for col_idx, title in enumerate(headers, start=1):
            sheet.write(row, col_idx, title, formats['title'])

        # 5) INICIALIZAR ACUMULADORES
        suma_total_w_iva         = 0.0
        suma_no_taxe_sale        = 0.0
        suma_vat_general_base    = 0.0
        suma_vat_general_tax     = 0.0
        suma_vat_reduced_base    = 0.0
        suma_vat_reduced_tax     = 0.0
        suma_vat_additional_base = 0.0
        suma_vat_additional_tax  = 0.0
        suma_get_wh_vat          = 0.0

        # 6) POBLAR FILAS DE DATOS
        row = 7  # aquí comienza la primera fila de datos (coincide con L7, M7, etc.)
        first_data_row = row
        contador = 1
        for d in datos_ventas:
            col = 1
            sheet.write_number(row, col, contador); col += 1
            sheet.write(row,     col, d['emission_date']); col += 1
            sheet.write(row,     col, d['partner_vat']);    col += 1
            sheet.write(row,     col, d['partner_name']);   col += 1
            # columna Tipo de Transacción
            sheet.write(row, col, d.get('type', '') or '', formats['string']); col += 1

            # columna Nº de Factura
            sheet.write(row, col, d.get('invoice_number', '') or '', formats['string']); col += 1

            # Nº De Nota De Debito
            sheet.write(row, col, d.get('debit_note', '') or '', formats['string']); col += 1

            # Nº De Nota De Credito
            sheet.write(row, col, d.get('credit_note', '') or '', formats['string']); col += 1

            # Nº De Control
            sheet.write(row, col, d.get('ctrl_number', '') or '', formats['string']); col += 1

            # Nº de Documento Afectado
            sheet.write(row, col, d.get('affected_invoice', '') or '', formats['string']); col += 1

            # valores numéricos
            sheet.write_number(row, col, d['total_w_iva'],      formats['number']); col += 1
            sheet.write_number(row, col, d['no_taxe_sale'],     formats['number']); col += 1
            sheet.write_number(row, col, d['vat_reduced_base'], formats['number']); col += 1
            # el rate lo escribimos como string para no romper el método write_number
            sheet.write(row,        col, str(d['vat_reduced_rate']), formats['string']); col += 1
            sheet.write_number(row, col, d['vat_reduced_tax'],  formats['number']); col += 1
            sheet.write_number(row, col, d['vat_general_base'], formats['number']); col += 1
            sheet.write(row,        col, str(d['vat_general_rate']), formats['string']); col += 1
            sheet.write_number(row, col, d['vat_general_tax'],  formats['number']); col += 1
            sheet.write_number(row, col, d['get_wh_vat'],        formats['number']); col += 1
            sheet.write(row,        col, d.get('wh_number','') or '',    formats['string'])

            # Acumular (opcional, para uso interno)
            suma_total_w_iva       += float(d['total_w_iva'] or 0.0)
            suma_no_taxe_sale      += float(d['no_taxe_sale'] or 0.0)
            suma_vat_general_base  += float(d['vat_general_base'] or 0.0)
            suma_vat_general_tax   += float(d['vat_general_tax'] or 0.0)
            suma_vat_reduced_base  += float(d['vat_reduced_base'] or 0.0)
            suma_vat_reduced_tax   += float(d['vat_reduced_tax'] or 0.0)
            suma_vat_additional_base += float(d.get('vat_additional_base', 0.0))
            suma_vat_additional_tax  += float(d.get('vat_additional_tax', 0.0))
            suma_get_wh_vat       += float(d['get_wh_vat'] or 0.0)

            row += 1
            contador += 1

        # después del bucle, row está en la primera fila vacía
        totals_row    = row
        last_data_row = totals_row
        

        _logger.info("Libro de Venta: SUM desde fila %s hasta fila %s", first_data_row, last_data_row)

        # 7) FILA DE TOTALES PARCIALES (dinámico de L7:L155, M7:M155, etc.)
        sheet.merge_range(f'J{totals_row+1}:K{totals_row+1}', 'TOTALES', formats['title'])
        cols = ['L','M','N','O','P','Q','R','S','T','U']
        for idx, letra in enumerate(cols):
            col_idx = 11 + idx
            if letra in ('O','R','U'):
                sheet.write(totals_row, col_idx, '', formats['title_number'])
            else:
                formula = f"=SUM({letra}{first_data_row}:{letra}{last_data_row})"
                sheet.write_formula(totals_row, col_idx, formula, formats['title_number'])
                _logger.info("Totales columna %s: fórmula %s", letra, formula)

        # ——— formatos para resúmenes ———
        formats['resumen_label'] = workbook.add_format({
            'align': 'center', 'bold': True, 'valign': 'vcenter',
            'font_color': 'black', 'bg_color': '#FFFF99', 'border': 1
        })
        formats['resumen_items'] = workbook.add_format({
            'align': 'left', 'valign': 'vcenter',
            'font_color': 'black', 'border': 1
        })
        formats['resumen_value'] = workbook.add_format({
            'align': 'right', 'valign': 'vcenter',
            'num_format': '#,##0.00', 'border': 1
        })
        formats['resumen_header'] = workbook.add_format({
            'align': 'center', 'valign': 'vcenter', 'bold': True,
            'font_color': 'white', 'bg_color': '#00B0F0', 'border': 1
        })

        # ——— RESUMEN DE VENTAS ———
        row = totals_row + 3
        sheet.merge_range(f'A{row}:G{row}', 'RESUMEN DE VENTAS', formats['title'])
        sheet.merge_range(f'A{row+1}:C{row+1}', 'DÉBITOS FISCALES',     formats['resumen_header'])
        sheet.merge_range(f'D{row+1}:E{row+1}', 'BASE IMPONIBLE (Bs)', formats['resumen_header'])
        sheet.merge_range(f'F{row+1}:G{row+1}', 'DÉBITO FISCAL ( Bs)', formats['resumen_header'])

        ventas = [
            # (texto, item, código_de_base, fórmula de base, fórmula de débito)
            ("Ventas internas no gravadas",       1, "40",  f"=M{totals_row+1}",       None),
            ("Ventas de exportación",             2, "41",  None,                      None),
            ("Ventas internas gravadas por alícuota general", 3, "42", None,                "43"),
            ("Ventas internas gravadas por alícuota general más alícuota adicional", 4, "442", None, "452"),
            ("Ventas internas gravadas por alícuota reducida", 5, "443", None,               "453"),
            ("Total ventas y débitos fiscales para efectos de determinación", 6, "46",
                 f"=SUM(Q{totals_row+1},N{totals_row+1})", "47"),
            ("Ajustes a los débitos fiscales de períodos anteriores. Si la operación (47 +/- 48 > 0) indique el monto del ajuste, si la operación (47 +/- 48 < 0), repita con signo negativo hasta la concurrencia del 47; y la diferencia ajústela en períodos futuros",
                 7, "48", None, None),
            ("Certificados de débitos fiscales exonerados (recibos de entes exonerados). Registro de período",
                 8, "80", None, None),
            ("Total débitos fiscales (47 +/- 48 - 80)", 9, "49", None, f"=SUM(47,-48,-80)"),
        ]

        for i, (lbl, item, code, base_f, debit_f) in enumerate(ventas, start=1):
            r = row + 1 + i
            sheet.write_number(f'A{r}', item)
            sheet.merge_range(f'B{r}:C{r}', lbl,       formats['resumen_items'])
            sheet.write_number(f'D{r}', int(code),    formats['resumen_items'])
            if base_f:
                sheet.write_formula(f'E{r}', base_f, formats['resumen_value'])
            else:
                sheet.write_blank(f'E{r}', None, formats['resumen_value'])
            if debit_f:
                sheet.write_blank  (f'F{r}', None,               formats['resumen_items'])
                sheet.write_formula(f'G{r}', debit_f, formats['resumen_value'])
            else:
                sheet.write_blank(f'F{r}', None, formats['resumen_items'])
                sheet.write_blank(f'G{r}', None, formats['resumen_value'])

        # ——— RESUMEN DE COMPRAS ———
        row = row + len(ventas) + 3
        sheet.merge_range(f'A{row}:G{row}', 'RESUMEN DE COMPRAS', formats['title'])
        sheet.merge_range(f'A{row+1}:C{row+1}', 'CRÉDITOS FISCALES',      formats['resumen_header'])
        sheet.merge_range(f'D{row+1}:E{row+1}', 'BASE IMPONIBLE (Bs)',   formats['resumen_header'])
        sheet.merge_range(f'F{row+1}:G{row+1}', 'CRÉDITO FISCAL (Bs)',    formats['resumen_header'])

        datos_compras, _ = self.get_datas_compras()
        base_ng = sum(d['vat_exempt']       for d in datos_compras)
        base_g  = sum(d['vat_general_base'] for d in datos_compras)
        tax_g   = sum(d['vat_general_tax']  for d in datos_compras)
        base_r  = sum(d['vat_reduced_base'] for d in datos_compras)
        tax_r   = sum(d['vat_reduced_tax']  for d in datos_compras)

        compras = [
            ("Compras no gravadas y/o sin derecho a crédito fiscal", 10, "30", base_ng,  0.0),
            ("Importaciónes gravadas por alícuota general",           11, "31", 0.0,      0.0),
            ("Importaciónes gravadas por alícuota general más alícuota adicional", 12, "312",0.0,0.0),
            ("Importaciones gravadas por alícuota reducida",          13, "313",0.0,      0.0),
            ("Compras internas gravadas por alícuota general",       14, "33", base_g,   tax_g),
            ("Compras internas gravadas por alícuota general más alícuota adicional",15,"332",0.0,0.0),
            ("Compras internas gravadas por alícuota reducida",      16, "333",base_r,   tax_r),
            ("Total compras y créditos fiscales del Período",        17, "35", base_g+base_r, tax_g+tax_r),
            ("Créditos fiscales totalmente deducibles",              18, "70", tax_g+tax_r, 0.0),
            ("Créditos fiscales producto de la aplicación del porcentaje de la prorrata (36 - 70 X % prorrata)",19, "37", 0.0,0.0),
            ("Total créditos fiscales deducibles… Realice la operación (70 + 37)",20,"71", tax_g+tax_r, 0.0),
            ("Excedente créditos fiscales del mes anterior (ítem 60 de la declaración anterior)",21,"20",0.0,0.0),
            ("Reintegro solicitado (sólo exportadores)",             22, "21", 0.0,0.0),
            ("Reintegro solicitado (sólo quien suministre bienes o presten servicios a entes exonerados)",23,"81",0.0,0.0),
            ("Ajustes a los créditos fiscales de períodos anteriores. En caso de ser negativo, el ajuste no puede ser mayor al monto resultante de la operación (71 + 20 - 21 - 81)",24,"38",0.0,0.0),
            ("Certificados de débitos fiscales exonerados (emitidos por entes exonerados). Registrado en el período.",25,"82",0.0,0.0),
            ("Total créditos fiscales (71 + 20 - 21 - 81 +/- 38 - 82)",26,"39",tax_g+tax_r, 0.0),
        ]

        for i, (lbl, item, code, bval, cval) in enumerate(compras, start=1):
            r = row + 1 + i
            sheet.write_number(f'A{r}', item)
            sheet.merge_range(f'B{r}:C{r}', lbl,     formats['resumen_items'])
            sheet.write_number(f'D{r}', int(code), formats['resumen_items'])
            sheet.write_number(f'E{r}', bval,       formats['resumen_value'])
            sheet.write_number(f'F{r}', cval,       formats['resumen_value'])

        # 9) Cerrar y devolver
        workbook.close()
        file_base64 = base64.b64encode(output.getvalue())
        attachment_id = self.env['ir.attachment'].sudo().create({
            'name': file_name,
            'datas': file_base64,
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment_id.id}?download=true',
            'target': 'current',
        }

    def check_report(self):
        if self.type == 'purchase':
            if self.date_start and self.date_end:
                fecha_inicio = self.date_start
                fecha_fin = self.date_end
                book_id = self.env.context['active_id']
                purchase_book_obj = self.env['account.move']
                purchase_book_ids = purchase_book_obj.search(
                    [('invoice_date', '>=', fecha_inicio), ('invoice_date', '<=', fecha_fin),
                     ('state', 'in', ['posted'])])
                if purchase_book_ids:
                    ids = []
                    for id in purchase_book_ids:
                        ids.append(id.id)
                    data = {
                        'ids': ids,
                        'model': 'report.fiscal_book.report_fiscal_purchase_book',
                        'form': {
                            'date_from': self.date_start,
                            'date_to': self.date_end,
                            'book_id': book_id,
                        },
                    }
                    return self.env.ref('l10n_ve_full.report_purchase_book').report_action(self,
                                                                                           data=data)  # , config=False
                else:
                    raise ValidationError('Advertencia! No existen facturas entre las fechas seleccionadas')
        else:
            if self.date_start and self.date_end:
                fecha_inicio = self.date_start
                fecha_fin = self.date_end
                book_id = self.env.context['active_id']

                ids = [book_id]
                data = {
                        'ids': ids,
                        'model': 'report.fiscal_book.report_fiscal_sale_book',
                        'form': {
                            'date_from': self.date_start,
                            'date_to': self.date_end,
                            'book_id': book_id,
                        },
                }
                return self.env.ref('l10n_ve_full.report_sale_book').report_action(self, data=data, config=False)


    date_start = fields.Date("Fecha de Inicio", required=True, default=time.strftime('%Y-%m-%d'))
    date_end = fields.Date("Fecha Fin", required=True, default=time.strftime('%Y-%m-%d'))
    control_start = fields.Integer("Control Start")
    control_end = fields.Integer("Control End")
    type = fields.Selection(TYPE, "Tipo", required=True)

    def set_formats(self, workbook):
        merge_format_string = workbook.add_format({
            'border': 0,
            'align': 'center',
            'valign': 'vcenter',
        })
        merge_format_string_titulo = workbook.add_format({
            'border': 0,
            'align': 'center',
            'valign': 'vcenter',
            'font_size': 20,
        })
        merge_format_date = workbook.add_format({
            'border': 0,
            'align': 'center',
            'valign': 'vcenter',
            'num_format': 'dd-mm-yyyy'
        })
        merge_format_number = workbook.add_format({
            'bold': 0,
            'valign': 'vcenter',
            'num_format': '#,##0.00'
        })
        merge_format_number_sd = workbook.add_format({
            'bold': 0,
            'valign': 'vcenter',
            'num_format': '###0'
        })
        merge_format_number_peso = workbook.add_format({
            'bold': 0,
            'valign': 'vcenter',
            'num_format': '$ #,##0.00'
        })
        merge_format_number_usd = workbook.add_format({
            'bold': 0,
            'valign': 'vcenter',
            'num_format': '[$USD-409] #,##0.00'
        })
        merge_format_number_euro = workbook.add_format({
            'bold': 0,
            'valign': 'vcenter',
            'num_format': '€ #,##0.00'
        })
        merge_format_title = workbook.add_format({
            'bold': 1,
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': '#fff5af',
            'text_wrap': True,
            'font_size': 10,
            'border': 1
        })
        merge_format_title_number = workbook.add_format({
            'bold': 1,
            'valign': 'vcenter',
            'bg_color': '#fff5af',
            'num_format': '#,##0.00',
            'text_wrap': True,
            'border': 1
        })
        merge_format_red_status = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': '#c30f0f',
            'font_color': 'white',
        })
        merge_format_yellow_status = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': '#ffeb9c',
            'font_color': 'black',
        })
        merge_format_light_green_status = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': '#c6efce',
            'font_color': '#50612e',
        })
        merge_format_green_status = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': '#87c842',
            'font_color': 'black',
        })
        merge_format_pink_status = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': '#ffc7ce',
            'font_color': '#9c0031',
        })
        return {
            'string': merge_format_string,
            'string_titulo': merge_format_string_titulo,
            'date': merge_format_date,
            'number': merge_format_number,
            'number_sd': merge_format_number_sd,
            'number_peso': merge_format_number_peso,
            'number_usd': merge_format_number_usd,
            'number_euro': merge_format_number_euro,
            'title': merge_format_title,
            'title_number': merge_format_title_number,
            'red_status': merge_format_red_status,
            'yellow_status': merge_format_yellow_status,
            'green_status': merge_format_green_status,
            'light_green_status': merge_format_light_green_status,
            'pink_status': merge_format_pink_status
        }

    def get_datas_compras(self):
        datos_compras = []
        datos_compras_ajustes = []
        for rec in self:
            format_new = "%d/%m/%Y"
            date_start = datetime.strptime(str(self.date_start), DATE_FORMAT).date()
            date_end = datetime.strptime(str(self.date_end), DATE_FORMAT).date()

            purchasebook_ids = self.env['account.fiscal.book.line'].search(
                [('fb_id', '=', self.env.context['active_id']),
                 ('emission_date', '>=', date_start.strftime(DATETIME_FORMAT)),
                 ('emission_date', '<=', date_end.strftime(DATETIME_FORMAT))], order='emission_date asc')

            emission_date = ' '
            sum_compras_credit = 0
            sum_total_with_iva = 0
            sum_vat_general_base = 0
            sum_vat_general_tax = 0
            sum_vat_reduced_base = 0
            sum_vat_reduced_tax = 0
            sum_vat_additional_base = 0
            sum_vat_additional_tax = 0
            sum_get_wh_vat = 0
            suma_vat_exempt = 0

            sum_compras_credit_ajustes = 0
            sum_total_with_iva_ajustes = 0
            sum_vat_general_base_ajustes = 0
            sum_vat_general_tax_ajustes = 0
            sum_vat_reduced_base_ajustes = 0
            sum_vat_reduced_tax_ajustes = 0
            sum_vat_additional_base_ajustes = 0
            sum_vat_additional_tax_ajustes = 0
            sum_get_wh_vat_ajustes = 0
            suma_vat_exempt_ajustes = 0

            vat_reduced_base = 0
            vat_reduced_rate = 0
            vat_reduced_tax = 0
            vat_additional_base = 0
            vat_additional_rate = 0
            vat_additional_tax = 0

            ''' COMPRAS DE IMPORTACIONES'''

            sum_total_with_iva_importaciones = 0
            sum_vat_general_base_importaciones = 0
            suma_base_general_importaciones = 0
            sum_base_general_tax_importaciones = 0
            sum_vat_general_tax_importaciones = 0
            sum_vat_reduced_base_importaciones = 0
            sum_vat_reduced_tax_importaciones = 0
            sum_vat_additional_base_importaciones = 0
            sum_vat_additional_tax_importaciones = 0

            hola = 0
            #######################################
            compras_credit = 0
            origin = 0
            number = 0
    
            for h in purchasebook_ids:
                h_vat_general_base = 0.0
                h_vat_general_rate = 0.0
                h_vat_general_tax = 0.0
                vat_general_base_importaciones = 0
                vat_general_rate_importaciones = 0
                vat_general_general_rate_importaciones = 0
                vat_general_tax_importaciones = 0
                vat_reduced_base_importaciones = 0
                vat_reduced_rate_importaciones = 0
                vat_reduced_tax_importaciones = 0
                vat_additional_tax_importaciones = 0
                vat_additional_rate_importaciones = 0
                vat_additional_base_importaciones = 0
                vat_reduced_base = 0
                vat_reduced_rate = 0
                vat_reduced_tax = 0
                vat_additional_base = 0
                vat_additional_rate = 0
                vat_additional_tax = 0
                get_wh_vat = 0

                if isinstance(h.emission_date, str):
                    emission_date_dt = datetime.strptime(h.emission_date, DEFAULT_SERVER_DATE_FORMAT).date()
                else:
                    emission_date_dt = h.emission_date if isinstance(h.emission_date, date) else h.emission_date.date()

                if h.type == 'ntp':
                    compras_credit = h.invoice_id.amount_untaxed

                if h.doc_type == 'N/DB':
                    origin = h.affected_invoice
                    if h.invoice_id:
                        if h.invoice_id.nro_ctrl:
                            busq1 = self.env['account.move'].search([('nro_ctrl', '=', h.invoice_id.nro_ctrl)])
                            if busq1:
                                for busq2 in busq1:
                                    if busq2.type == 'in_invoice':
                                        number = busq2.name or ''

                sum_compras_credit += compras_credit
                suma_vat_exempt += h.vat_exempt
                planilla = ''
                expediente = ''
                total = 0
                partner = self.env['res.partner'].search([('rif', '=', h.partner_vat)])
                if partner and len(partner) == 1:
                    partner_1 = partner
                else:
                    partner = self.env['res.partner'].search([('name', '=', h.partner_vat)])
                    partner_1 = partner
                if h.invoice_id:
                    partner = h.invoice_id.partner_id
                    partner_1 = partner
                if (partner_1.company_type == 'company' or partner_1.company_type == 'person') and (
                        partner_1.people_type_company or partner_1.people_type_individual) and (
                        partner_1.people_type_company == 'pjdo' or partner_1.people_type_individual == 'pnre' or partner_1.people_type_individual == 'pnnr'):
                    '####################### NO ES PROVEDOR INTERNACIONAL########################################################3'

                    if h.invoice_id:
                        print('tiene factura')
                        tasa = 1
                        if h.invoice_id.currency_id.name == "USD":
                            tasa = self.obtener_tasa(h.invoice_id)
                        if h.doc_type == 'N/CR':
                            total = (h.invoice_id.amount_total) * -1 * tasa
                        else:
                            total = (h.invoice_id.amount_total) * tasa
                        sum_vat_reduced_base += h.vat_reduced_base  # Base Imponible de alicuota Reducida
                        sum_vat_reduced_tax += h.vat_reduced_tax  # Impuesto de IVA alicuota reducida
                        sum_vat_additional_base += h.vat_additional_base  # BASE IMPONIBLE ALICUOTA ADICIONAL

                        sum_vat_additional_tax += h.vat_additional_tax  # IMPUESTO DE IVA ALICUOTA ADICIONAL

                        sum_total_with_iva = (
                            h.fb_id.base_amount + h.fb_id.tax_amount) if emission_date_dt >= date_start else 0
                        sum_total_with_iva_ajustes = (
                            h.fb_id.base_amount + h.fb_id.tax_amount) if emission_date_dt < date_start else 0
                        # Total monto con IVA
                        sum_vat_general_base += h.vat_general_base  # Base Imponible Alicuota general
                        sum_vat_general_tax += h.vat_general_tax  # Impuesto de IVA
                        h_vat_general_base = h.vat_general_base
                        h_vat_general_rate = (
                                h.vat_general_base and h.vat_general_tax * 100 / h.vat_general_base) if h.vat_general_base else 0.0
                        h_vat_general_rate = round(h_vat_general_rate, 0)
                        h_vat_general_tax = h.vat_general_tax if h.vat_general_tax else 0.0
                        vat_reduced_base = h.vat_reduced_base
                        vat_reduced_rate = int(h.vat_reduced_base and h.vat_reduced_tax * 100 / h.vat_reduced_base)
                        vat_reduced_tax = h.vat_reduced_tax
                        vat_additional_base = h.vat_additional_base
                        vat_additional_rate = int(
                            h.vat_additional_base and h.vat_additional_tax * 100 / h.vat_additional_base)
                        vat_additional_tax = h.vat_additional_tax
                        get_wh_vat = h.get_wh_vat

                        emission_date = datetime.strftime(
                            datetime.strptime(str(h.emission_date), DEFAULT_SERVER_DATE_FORMAT),
                            format_new)
                    if h.iwdl_id.invoice_id:
                        print('tiene retencion y factura')
                        tasa = 1
                        if h.iwdl_id.invoice_id.currency_id.name == "USD":
                            tasa = self.obtener_tasa(h.iwdl_id.invoice_id)
                        if h.doc_type == 'N/CR':
                            total = (h.iwdl_id.invoice_id.amount_total) * -1 * tasa
                        else:
                            total = (h.iwdl_id.invoice_id.amount_total) * tasa
                        sum_vat_reduced_base += h.vat_reduced_base  # Base Imponible de alicuota Reducida
                        sum_vat_reduced_tax += h.vat_reduced_tax
                        # Impuesto de IVA alicuota reducida

                        sum_vat_additional_base += h.vat_additional_base  # BASE IMPONIBLE ALICUOTA ADICIONAL

                        sum_vat_additional_tax += h.vat_additional_tax  # IMPUESTO DE IVA ALICUOTA ADICIONAL
                        # Asegura que emission_date_dt sea SIEMPRE tipo date
                        if isinstance(h.emission_date, str):
                            emission_date_dt = datetime.strptime(h.emission_date, DEFAULT_SERVER_DATE_FORMAT).date()
                        elif isinstance(h.emission_date, datetime):
                            emission_date_dt = h.emission_date.date()
                        elif isinstance(h.emission_date, date):
                            emission_date_dt = h.emission_date
                        else:
                            emission_date_dt = date.min  # Valor mínimo por si acaso es None
                        sum_total_with_iva = (h.fb_id.base_amount + h.fb_id.tax_amount) if emission_date_dt >= date_start else 0
                        sum_total_with_iva_ajustes = (h.fb_id.base_amount + h.fb_id.tax_amount) if emission_date_dt < date_start else 0
                        sum_vat_general_base += h.vat_general_base  # Base Imponible Alicuota general
                        sum_vat_general_tax += h.vat_general_tax  # Impuesto de IVA
                        h_vat_general_base = h.vat_general_base
                        h_vat_general_rate = (
                                h.vat_general_base and h.vat_general_tax * 100 / h.vat_general_base) if h.vat_general_base else 0.0
                        h_vat_general_rate = round(h_vat_general_rate, 0)
                        h_vat_general_tax = h.vat_general_tax if h.vat_general_tax else 0.0
                        vat_reduced_base = h.vat_reduced_base
                        vat_reduced_rate = int(h.vat_reduced_base and h.vat_reduced_tax * 100 / h.vat_reduced_base)
                        vat_reduced_tax = h.vat_reduced_tax
                        vat_additional_base = h.vat_additional_base
                        vat_additional_rate = int(
                            h.vat_additional_base and h.vat_additional_tax * 100 / h.vat_additional_base)
                        vat_additional_tax = h.vat_additional_tax
                        get_wh_vat = h.get_wh_vat

                        emission_date = datetime.strftime(
                            datetime.strptime(str(h.emission_date), DEFAULT_SERVER_DATE_FORMAT),
                            format_new)

                if (partner_1.company_type == 'company' or partner_1.company_type == 'person') and (
                        partner_1.people_type_company or partner_1.people_type_individual) and partner_1.people_type_company == 'pjnd':
                    '############## ES UN PROVEEDOR INTERNACIONAL ##############################################'

                    if h.invoice_id:
                        tasa = 1
                        if h.invoice_id.currency_id.name == "USD":
                            tasa = self.obtener_tasa(h.invoice_id)
                        if h.invoice_id.fecha_importacion:
                            date_impor = h.invoice_id.fecha_importacion
                            emission_date = datetime.strftime(
                                datetime.strptime(str(date_impor), DEFAULT_SERVER_DATE_FORMAT),
                                format_new)
                            total = h.invoice_id.amount_total * tasa
                        else:
                            date_impor = h.invoice_id.invoice_date
                            emission_date = datetime.strftime(
                                datetime.strptime(str(date_impor), DEFAULT_SERVER_DATE_FORMAT),
                                format_new)

                        planilla = h.invoice_id.nro_planilla_impor
                        expediente = h.invoice_id.nro_expediente_impor




                    else:
                        date_impor = h.iwdl_id.invoice_id.fecha_importacion
                        emission_date = datetime.strftime(
                            datetime.strptime(str(date_impor), DEFAULT_SERVER_DATE_FORMAT),
                            format_new)
                        planilla = h.iwdl_id.invoice_id.nro_planilla_impor
                        expediente = h.iwdl_id.invoice_id.nro_expediente_impor
                        tasa = 1
                        if h.iwdl_id.invoice_id.currency_id.name == "USD":
                            tasa = self.obtener_tasa(h.iwdl_id.invoice_id)
                        total = h.iwdl_id.invoice_id.amount_total * tasa
                    get_wh_vat = 0.0
                    vat_reduced_base = 0
                    vat_reduced_rate = 0
                    vat_reduced_tax = 0
                    vat_additional_base = 0
                    vat_additional_rate = 0
                    vat_additional_tax = 0
                    'ALICUOTA GENERAL IMPORTACIONES'
                    vat_general_base_importaciones = h.vat_general_base
                    vat_general_rate_importaciones = (
                            h.vat_general_base and h.vat_general_tax * 100 / h.vat_general_base)
                    vat_general_rate_importaciones = round(vat_general_rate_importaciones, 0)
                    vat_general_tax_importaciones = h.vat_general_tax
                    'ALICUOTA REDUCIDA IMPORTACIONES'
                    vat_reduced_base_importaciones = h.vat_reduced_base
                    vat_reduced_rate_importaciones = int(
                        h.vat_reduced_base and h.vat_reduced_tax * 100 / h.vat_reduced_base)
                    vat_reduced_tax_importaciones = h.vat_reduced_tax
                    'ALICUOTA ADICIONAL IMPORTACIONES'
                    vat_additional_base_importaciones = h.vat_additional_base
                    vat_additional_rate_importaciones = int(
                        h.vat_additional_base and h.vat_additional_tax * 100 / h.vat_additional_base)
                    vat_additional_tax_importaciones = h.vat_additional_tax
                    'Suma total compras con IVA'
                    sum_total_with_iva = (
                            h.fb_id.base_amount + h.fb_id.tax_amount) if h.emission_date >= date_start else 0
                    sum_total_with_iva_ajustes = (
                            h.fb_id.base_amount + h.fb_id.tax_amount) if h.emission_date < date_start else 0
                    # Total monto con IVA
                    'SUMA TOTAL DE TODAS LAS ALICUOTAS PARA LAS IMPORTACIONES'
                    sum_vat_general_base_importaciones += h.vat_general_base + h.vat_reduced_base + h.vat_additional_base  # Base Imponible Alicuota general
                    sum_vat_general_tax_importaciones += h.vat_general_tax + h.vat_additional_tax + h.vat_reduced_tax  # Impuesto de IVA

                    'Suma total de Alicuota General'
                    suma_base_general_importaciones += h.vat_general_base
                    sum_base_general_tax_importaciones += h.vat_general_tax

                    ' Suma total de Alicuota Reducida'
                    sum_vat_reduced_base_importaciones += h.vat_reduced_base  # Base Imponible de alicuota Reducida
                    sum_vat_reduced_tax_importaciones += h.vat_reduced_tax  # Impuesto de IVA alicuota reducida
                    'Suma total de Alicuota Adicional'
                    sum_vat_additional_base_importaciones += h.vat_additional_base  # BASE IMPONIBLE ALICUOTA ADICIONAL
                    sum_vat_additional_tax_importaciones += h.vat_additional_tax  # IMPUESTO DE IVA ALICUOTA ADICIONAL

                    get_wh_vat = h.get_wh_vat
                sum_get_wh_vat += h.get_wh_vat  # IVA RETENIDO

                if h_vat_general_base != 0:
                    valor_base_imponible = h.vat_general_base
                    valor_alic_general = h_vat_general_rate
                    valor_iva = h_vat_general_tax
                else:

                    valor_base_imponible = 0
                    valor_alic_general = 0
                    valor_iva = 0

                if get_wh_vat != 0:
                    hola = get_wh_vat
                else:
                    hola = 0

                if h.vat_exempt != 0:
                    vat_exempt = h.vat_exempt

                else:
                    vat_exempt = 0

                'Para las diferentes alicuotas que pueda tener el proveedor  internacional'
                'todas son mayor a 0'
                if vat_general_rate_importaciones > 0 and vat_reduced_rate_importaciones > 0 and vat_additional_rate_importaciones > 0:
                    vat_general_general_rate_importaciones = str(vat_general_rate_importaciones) + ',' + ' ' + str(
                        vat_reduced_rate_importaciones) + ',' + ' ' + str(vat_additional_rate_importaciones) + ' '
                'todas son cero'
                if vat_general_rate_importaciones == 0 and vat_reduced_rate_importaciones == 0 and vat_additional_rate_importaciones == 0:
                    vat_general_general_rate_importaciones = 0
                'Existe reducida y adicional'
                if vat_general_rate_importaciones == 0 and vat_reduced_rate_importaciones > 0 and vat_additional_rate_importaciones > 0:
                    vat_general_general_rate_importaciones = str(vat_reduced_rate_importaciones) + ',' + ' ' + str(
                        vat_additional_rate_importaciones) + ' '
                'Existe general y adicional'
                if vat_general_rate_importaciones > 0 and vat_reduced_rate_importaciones == 0 and vat_additional_rate_importaciones > 0:
                    vat_general_general_rate_importaciones = str(vat_general_rate_importaciones) + ',' + ' ' + str(
                        vat_additional_rate_importaciones) + ' '
                'Existe general y reducida'
                if vat_general_rate_importaciones > 0 and vat_reduced_rate_importaciones > 0 and vat_additional_rate_importaciones == 0:
                    vat_general_general_rate_importaciones = str(vat_general_rate_importaciones) + ',' + ' ' + str(
                        vat_reduced_rate_importaciones) + ' '
                'Existe solo la general'
                if vat_general_rate_importaciones > 0 and vat_reduced_rate_importaciones == 0 and vat_additional_rate_importaciones == 0:
                    vat_general_general_rate_importaciones = str(vat_general_rate_importaciones)
                'Existe solo la reducida'
                if vat_general_rate_importaciones == 0 and vat_reduced_rate_importaciones > 0 and vat_additional_rate_importaciones == 0:
                    vat_general_general_rate_importaciones = str(vat_reduced_rate_importaciones)
                'Existe solo la adicional'
                if vat_general_rate_importaciones == 0 and vat_reduced_rate_importaciones == 0 and vat_additional_rate_importaciones > 0:
                    vat_general_general_rate_importaciones = str(vat_additional_rate_importaciones)
                if h.emission_date >= date_start:
                    datos_compras.append({

                        'emission_date': datetime.strftime(
                            datetime.strptime(str(h.emission_date), DEFAULT_SERVER_DATE_FORMAT),
                            format_new) if h.emission_date else ' ',
                        'partner_vat': h.partner_vat if h.partner_vat else ' ',
                        'partner_name': h.partner_name,
                        'people_type': h.people_type,
                        'wh_number': h.wh_number if h.wh_number else ' ',
                        'invoice_number': h.invoice_number,
                        'affected_invoice': h.affected_invoice,
                        'ctrl_number': h.ctrl_number or h.invoice_id.correlative or '',
                        'debit_affected': h.numero_debit_credit if h.doc_type == 'N/DB' else False,
                        'credit_affected': h.numero_debit_credit if h.doc_type == 'N/CR' else False,
                        # h.credit_affected,
                        'type': h.void_form,
                        'doc_type': h.doc_type,
                        'origin': origin,
                        'number': number,
                        'total_with_iva': h.total_with_iva,
                        'vat_exempt': vat_exempt,
                        'compras_credit': compras_credit,
                        'vat_general_base': valor_base_imponible,
                        'vat_general_rate': valor_alic_general,
                        'vat_general_tax': valor_iva,
                        'vat_reduced_base': vat_reduced_base,
                        'vat_reduced_rate': vat_reduced_rate,
                        'vat_reduced_tax': vat_reduced_tax,
                        'vat_additional_base': vat_additional_base,
                        'vat_additional_rate': vat_additional_rate,
                        'vat_additional_tax': vat_additional_tax,
                        'get_wh_vat': hola,
                        'vat_general_base_importaciones': vat_general_base_importaciones + vat_additional_base_importaciones + vat_reduced_base_importaciones,
                        'vat_general_rate_importaciones': vat_general_general_rate_importaciones,
                        'vat_general_tax_importaciones': vat_general_tax_importaciones + vat_reduced_tax_importaciones + vat_additional_tax_importaciones,
                        'nro_planilla': planilla,
                        'nro_expediente': expediente,
                        'company_name': h.fb_id.company_id.name,
                        'company_rif': h.fb_id.company_id.vat
                    })
                else:
                    datos_compras_ajustes.append({

                        'emission_date': datetime.strftime(
                            datetime.strptime(str(h.emission_date), DEFAULT_SERVER_DATE_FORMAT),
                            format_new) if h.emission_date else ' ',
                        'partner_vat': h.partner_vat if h.partner_vat else ' ',
                        'partner_name': h.partner_name,
                        'people_type': h.people_type,
                        'wh_number': h.wh_number if h.wh_number else ' ',
                        'invoice_number': h.invoice_number,
                        'affected_invoice': h.affected_invoice,
                        'ctrl_number': h.ctrl_number or h.invoice_id.correlative or '',
                        'debit_affected': h.numero_debit_credit if h.doc_type == 'N/DB' else False,
                        'credit_affected': h.numero_debit_credit if h.doc_type == 'N/CR' else False,
                        # h.credit_affected,
                        'type': h.void_form,
                        'doc_type': h.doc_type,
                        'origin': origin,
                        'number': number,
                        'total_with_iva': h.total_with_iva,
                        'vat_exempt': vat_exempt,
                        'compras_credit': compras_credit,
                        'vat_general_base': valor_base_imponible,
                        'vat_general_rate': valor_alic_general,
                        'vat_general_tax': valor_iva,
                        'vat_reduced_base': vat_reduced_base,
                        'vat_reduced_rate': vat_reduced_rate,
                        'vat_reduced_tax': vat_reduced_tax,
                        'vat_additional_base': vat_additional_base,
                        'vat_additional_rate': vat_additional_rate,
                        'vat_additional_tax': vat_additional_tax,
                        'get_wh_vat': hola,
                        'vat_general_base_importaciones': vat_general_base_importaciones + vat_additional_base_importaciones + vat_reduced_base_importaciones,
                        'vat_general_rate_importaciones': vat_general_general_rate_importaciones,
                        'vat_general_tax_importaciones': vat_general_tax_importaciones + vat_reduced_tax_importaciones + vat_additional_tax_importaciones,
                        'nro_planilla': planilla,
                        'nro_expediente': expediente,
                        'company_name': h.fb_id.company_id.name,
                        'company_rif': h.fb_id.company_id.vat
                    })

        return datos_compras, datos_compras_ajustes

    def get_datas_ventas(self):
        datos_ventas = []
        datos_ventas_ajustes = []
        DATE_FORMAT = "%Y-%m-%d"
        DEFAULT_SERVER_DATE_FORMAT = "%Y-%m-%d"
        format_new = "%d/%m/%Y"

        for rec in self:
            fb_id = self.env.context['active_id']
            busq = self.env['account.fiscal.book'].browse(fb_id)
            date_start = datetime.strptime(str(self.date_start), DATE_FORMAT).date()
            date_end = datetime.strptime(str(self.date_end), DATE_FORMAT).date()

            # Obtenemos todas las líneas sin orden; después ordenaremos por ctrl_number
            fbl_obj = self.env['account.fiscal.book.line'].search(
                [('fb_id', '=', busq.id), ('emission_date', '>=', date_start)]
            )

            suma_vat_reduced_base = suma_vat_reduced_tax = 0
            suma_vat_additional_base = suma_vat_additional_tax = 0
            suma_vat_general_base = suma_vat_general_tax = 0
            suma_get_wh_vat = 0

            def _safe_format_date(date_value, out_format):
                if date_value:
                    return datetime.strftime(
                        datetime.strptime(str(date_value), DEFAULT_SERVER_DATE_FORMAT),
                        out_format
                    )
                return ''

            for line in fbl_obj:
                vat_general_base = vat_general_rate = vat_general_tax = 0
                vat_reduced_base = vat_reduced_rate = vat_reduced_tax = 0
                vat_additional_base = vat_additional_rate = vat_additional_tax = 0

                if line.vat_reduced_base:
                    vat_reduced_base = line.vat_reduced_base
                    vat_reduced_rate = int(round(line.vat_reduced_tax * 100.0 / line.vat_reduced_base, 0))
                    vat_reduced_tax = line.vat_reduced_tax
                    suma_vat_reduced_base += line.vat_reduced_base
                    suma_vat_reduced_tax += line.vat_reduced_tax

                if line.vat_additional_base:
                    vat_additional_base = line.vat_additional_base
                    vat_additional_rate = int(round(line.vat_additional_tax * 100.0 / line.vat_additional_base, 0))
                    vat_additional_tax = line.vat_additional_tax
                    suma_vat_additional_base += line.vat_additional_base
                    suma_vat_additional_tax += line.vat_additional_tax

                if line.vat_general_base:
                    vat_general_base = line.vat_general_base
                    vat_general_rate = int(round(line.vat_general_tax * 100.0 / line.vat_general_base, 0))
                    vat_general_tax = line.vat_general_tax
                    suma_vat_general_base += line.vat_general_base
                    suma_vat_general_tax += line.vat_general_tax

                if line.get_wh_vat:
                    suma_get_wh_vat += line.get_wh_vat

                vat_reduced_rate = str(vat_reduced_rate) if vat_reduced_rate else ''
                vat_additional_rate = str(vat_additional_rate) if vat_additional_rate else ''
                vat_general_rate = str(vat_general_rate) if vat_general_rate else ''
                if not vat_general_rate and not vat_reduced_rate and not vat_additional_rate:
                    vat_general_rate = 0

                acc_date = line.accounting_date
                if isinstance(acc_date, date):
                    acc_date_str = acc_date.strftime("%Y-%m-%d")
                else:
                    acc_date_str = str(acc_date) if acc_date else ""

                # Usar invoice.correlative si existe; si no, line.ctrl_number
                if line.invoice_id and hasattr(line.invoice_id, 'correlative') and line.invoice_id.correlative:
                    ctrl_value = line.invoice_id.correlative
                else:
                    ctrl_value = line.ctrl_number

                doc_dict = {
                    'tipo': 'factura',
                    'emission_date': datetime.strftime(
                        datetime.strptime(str(line.emission_date), DEFAULT_SERVER_DATE_FORMAT),
                        format_new
                    ) if line.emission_date else '',
                    'rannk': line.rank,
                    'partner_vat': line.partner_vat or ' ',
                    'partner_name': line.partner_name,
                    'people_type': line.people_type or ' ',
                    # 'report_z' eliminado para no incluir la columna "Nro Z"
                    'export_form': '',
                    'wh_number': line.wh_number,
                    'accounting_date': acc_date_str,
                    'fecha_orden': line.accounting_date or line.emission_date,
                    'wh_date': _safe_format_date(line.wh_date, format_new),
                    'date_wh_number': line.iwdl_id.retention_id.date_ret if line.wh_number else '',
                    'invoice_number': line.invoice_number,
                    'n_ultima_factZ': line.n_ultima_factZ,
                    'ctrl_number': ctrl_value,
                    'debit_note': line.numero_debit_credit if line.doc_type == 'N/DB' else False,
                    'credit_note': line.numero_debit_credit if line.doc_type == 'N/CR' else False,
                    'type': line.void_form,
                    'affected_invoice': line.affected_invoice or ' ',
                    'total_w_iva': line.total_with_iva or 0,
                    'no_taxe_sale': line.vat_exempt,
                    'export_sale': '',
                    'vat_general_base': vat_general_base,
                    'vat_general_rate': vat_general_rate,
                    'vat_general_tax': vat_general_tax,
                    'vat_reduced_base': vat_reduced_base,
                    'vat_reduced_rate': vat_reduced_rate,
                    'vat_reduced_tax': vat_reduced_tax,
                    'vat_additional_base': vat_additional_base,
                    'vat_additional_rate': vat_additional_rate,
                    'vat_additional_tax': vat_additional_tax,
                    'get_wh_vat': line.get_wh_vat,
                    'company_name': line.fb_id.company_id.name,
                    'company_rif': line.fb_id.company_id.vat,
                }

                if line.emission_date >= date_start:
                    datos_ventas.append(doc_dict)
                else:
                    datos_ventas_ajustes.append(doc_dict)

                if line.wh_number and line.get_wh_vat:
                    wh_acc_date = line.wh_date or line.accounting_date or line.emission_date
                    if isinstance(wh_acc_date, date):
                        wh_acc_date_str = wh_acc_date.strftime("%Y-%m-%d")
                    else:
                        wh_acc_date_str = str(wh_acc_date)

                    ret_dict = {
                        'tipo': 'retencion',
                        'rannk': line.rank,
                        'emission_date': _safe_format_date(line.wh_date, format_new),
                        'partner_vat': line.partner_vat or ' ',
                        'partner_name': line.partner_name,
                        'people_type': line.people_type or ' ',
                        # 'report_z' también eliminado aquí
                        'export_form': '',
                        'wh_number': line.wh_number,
                        'wh_date': _safe_format_date(line.wh_date, format_new),
                        'date_wh_number': line.iwdl_id.retention_id.date_ret if line.wh_number else '',
                        'invoice_number': line.invoice_number,
                        'n_ultima_factZ': '',
                        'ctrl_number': ctrl_value,
                        'debit_note': '',
                        'credit_note': '',
                        'type': 'RETENCIÓN',
                        'affected_invoice': '',
                        'total_w_iva': 0,
                        'no_taxe_sale': 0,
                        'export_sale': '',
                        'vat_general_base': 0,
                        'vat_general_rate': '',
                        'vat_general_tax': 0,
                        'vat_reduced_base': 0,
                        'vat_reduced_rate': '',
                        'vat_reduced_tax': 0,
                        'vat_additional_base': 0,
                        'vat_additional_rate': '',
                        'vat_additional_tax': 0,
                        'get_wh_vat': line.get_wh_vat,
                        'accounting_date': wh_acc_date_str,
                    }
                    if line.wh_date >= date_start:
                        datos_ventas.append(ret_dict)
                    else:
                        datos_ventas_ajustes.append(ret_dict)

        # Convertir ctrl_number a entero o lo ubica al final si no es numérico
        def _ctrl_to_int(ctrl):
            try:
                return int(ctrl)
            except (ValueError, TypeError):
                return float('inf')

        # Ordenar de menor a mayor por ctrl_number
        datos_ventas = sorted(datos_ventas, key=lambda d: _ctrl_to_int(d.get('ctrl_number')))
        datos_ventas_ajustes = sorted(datos_ventas_ajustes, key=lambda d: _ctrl_to_int(d.get('ctrl_number')))

        return datos_ventas, datos_ventas_ajustes

        # ORDEN GLOBAL POR FECHA, LA QUE PREFIERAS
        def get_fecha(linea):
            # Prioriza fecha de retención, si no la de factura
            if linea.get('emission_date'):
                if isinstance(linea['emission_date'], datetime):
                    return linea['emission_date']
                elif isinstance(linea['emission_date'], str):
                    try:
                        return datetime.strptime(linea['emission_date'], "%Y-%m-%d")
                    except Exception:
                        try:
                            return datetime.strptime(linea['emission_date'], "%d/%m/%Y")
                        except Exception:
                            return datetime(1900,1,1)
            return datetime(1900,1,1)

        docs_ordenados = sorted(docs, key=get_fecha)

        return docs_ordenados

    def obtener_tasa(self, invoice):
        fecha = invoice.date
        tasa_id = invoice.currency_id
        tasa = self.env['res.currency.rate'].search(
            [('currency_id', '=', tasa_id.id), ('name', '<=', fecha)],
            order='name desc',  # normalmente desc para agarrar la tasa más reciente anterior a la fecha
            limit=1
        )
        if not tasa:
            raise UserError(
                "Advertencia! \n No hay referencia de tasas registradas para moneda USD en la fecha igual o inferior de la factura %s" % (
                    invoice.name))
        return tasa.rate

#LIBRO DE COMPRAS PDF
class PurchaseBook(models.AbstractModel):
    _name = 'report.l10n_ve_full.report_fiscal_purchase_book'

    @api.model
    def _get_report_values(self, docids, data=None):
        format_new = "%d/%m/%Y"
        date_start = datetime.strptime(data['form']['date_from'], DATE_FORMAT)
        date_end = datetime.strptime(data['form']['date_to'], DATE_FORMAT)
        datos_compras = []
        datos_compras_ajustes = []
        purchasebook_ids = self.env['account.fiscal.book.line'].search(
            [
                ('fb_id', '=', data['form']['book_id']),
                ('accounting_date', '>=', date_start.strftime(DATETIME_FORMAT)),
                ('accounting_date', '<=', date_end.strftime(DATETIME_FORMAT))
            ],
            order='emission_date asc'
        )
        emission_date = ' '
        sum_compras_credit = 0
        sum_total_with_iva = 0
        sum_vat_general_base = 0
        sum_vat_general_tax = 0
        sum_vat_reduced_base = 0
        sum_vat_reduced_tax = 0
        sum_vat_additional_base = 0
        sum_vat_additional_tax = 0
        sum_get_wh_vat = 0
        suma_vat_exempt = 0

        sum_compras_credit_ajustes = 0
        sum_total_with_iva_ajustes = 0
        sum_vat_general_base_ajustes = 0
        sum_vat_general_tax_ajustes = 0
        sum_vat_reduced_base_ajustes = 0
        sum_vat_reduced_tax_ajustes = 0
        sum_vat_additional_base_ajustes = 0
        sum_vat_additional_tax_ajustes = 0
        sum_get_wh_vat_ajustes = 0
        suma_vat_exempt_ajustes = 0

        vat_reduced_base = 0
        vat_reduced_rate = 0
        vat_reduced_tax = 0
        vat_additional_base = 0
        vat_additional_rate = 0
        vat_additional_tax = 0

        ''' COMPRAS DE IMPORTACIONES'''

        sum_total_with_iva_importaciones = 0
        sum_vat_general_base_importaciones = 0
        suma_base_general_importaciones = 0
        sum_base_general_tax_importaciones = 0
        sum_vat_general_tax_importaciones = 0
        sum_vat_reduced_base_importaciones = 0
        sum_vat_reduced_tax_importaciones = 0
        sum_vat_additional_base_importaciones = 0
        sum_vat_additional_tax_importaciones = 0

        hola = 0
        #######################################
        compras_credit = 0
        origin = 0
        number = 0

        for h in purchasebook_ids:
            h_vat_general_base = 0.0
            h_vat_general_rate = 0.0
            h_vat_general_tax = 0.0
            vat_general_base_importaciones = 0
            vat_general_rate_importaciones = 0
            vat_general_general_rate_importaciones = 0
            vat_general_tax_importaciones = 0
            vat_reduced_base_importaciones = 0
            vat_reduced_rate_importaciones = 0
            vat_reduced_tax_importaciones = 0
            vat_additional_tax_importaciones = 0
            vat_additional_rate_importaciones = 0
            vat_additional_base_importaciones = 0
            vat_reduced_base = 0
            vat_reduced_rate = 0
            vat_reduced_tax = 0
            vat_additional_base = 0
            vat_additional_rate = 0
            vat_additional_tax = 0
            get_wh_vat = 0

            if h.type == 'ntp':
                compras_credit = h.invoice_id.amount_untaxed

            if h.doc_type == 'N/DB':
                origin = h.affected_invoice
                if h.invoice_id:
                    if h.invoice_id.nro_ctrl:
                        busq1 = self.env['account.move'].search([('nro_ctrl', '=', h.invoice_id.nro_ctrl)])
                        if busq1:
                            for busq2 in busq1:
                                if busq2.type == 'in_invoice':
                                    number = busq2.name or ''

            sum_compras_credit += compras_credit
            suma_vat_exempt += h.vat_exempt
            planilla = ''
            expediente = ''
            total = 0
            partner = self.env['res.partner'].search([('rif', '=', h.partner_vat)])
            if partner and len(partner) == 1:
                partner_1 = partner
            else:
                partner = self.env['res.partner'].search([('name', '=', h.partner_vat)])
                partner_1 = partner

            if h.invoice_id:
                partner = h.invoice_id.partner_id
                partner_1 = partner

            if (partner_1.company_type == 'company' or partner_1.company_type == 'person') and (
                    partner_1.people_type_company or partner_1.people_type_individual) and (
                    partner_1.people_type_company == 'pjdo' or partner_1.people_type_individual == 'pnre' or partner_1.people_type_individual == 'pnnr'):
                '####################### NO ES PROVEDOR INTERNACIONAL########################################################3'
                if h.invoice_id:
                    tasa = 1
                    if h.invoice_id.currency_id.name == "USD":
                        tasa = self.obtener_tasa(h.invoice_id)
                    if h.doc_type == 'N/CR':
                        total = (h.invoice_id.amount_total) * -1 * tasa
                    else:
                        total = (h.invoice_id.amount_total) * tasa
                    sum_vat_reduced_base += h.vat_reduced_base  # Base Imponible de alicuota Reducida
                    sum_vat_reduced_tax += h.vat_reduced_tax  # Impuesto de IVA alicuota reducida
                    sum_vat_additional_base += h.vat_additional_base  # BASE IMPONIBLE ALICUOTA ADICIONAL

                    sum_vat_additional_tax += h.vat_additional_tax  # IMPUESTO DE IVA ALICUOTA ADICIONAL

                    sum_total_with_iva = (
                                h.fb_id.base_amount + h.fb_id.tax_amount) if h.emission_date >= date_start.date() else 0  # Total monto con IVA
                    sum_total_with_iva_ajustes = (
                                h.fb_id.base_amount + h.fb_id.tax_amount) if h.emission_date < date_start.date() else 0
                    # Total monto con IVA
                    sum_vat_general_base += h.vat_general_base  # Base Imponible Alicuota general
                    sum_vat_general_tax += h.vat_general_tax  # Impuesto de IVA
                    h_vat_general_base = h.vat_general_base
                    h_vat_general_rate = (
                                h.vat_general_base and h.vat_general_tax * 100 / h.vat_general_base) if h.vat_general_base else 0.0
                    h_vat_general_rate = round(h_vat_general_rate, 0)
                    h_vat_general_tax = h.vat_general_tax if h.vat_general_tax else 0.0
                    vat_reduced_base = h.vat_reduced_base
                    vat_reduced_rate = int(h.vat_reduced_base and h.vat_reduced_tax * 100 / h.vat_reduced_base)
                    vat_reduced_tax = h.vat_reduced_tax
                    vat_additional_base = h.vat_additional_base
                    vat_additional_rate = int(
                        h.vat_additional_base and h.vat_additional_tax * 100 / h.vat_additional_base)
                    vat_additional_tax = h.vat_additional_tax
                    get_wh_vat = h.get_wh_vat

                    emission_date = datetime.strftime(
                        datetime.strptime(str(h.emission_date), DEFAULT_SERVER_DATE_FORMAT),
                        format_new)
                if h.iwdl_id.invoice_id:
                    tasa = 1
                    if h.iwdl_id.invoice_id.currency_id.name == "USD":
                        tasa = self.obtener_tasa(h.iwdl_id.invoice_id)
                    if h.doc_type == 'N/CR':
                        total = (h.iwdl_id.invoice_id.amount_total) * -1 * tasa
                    else:
                        total = (h.iwdl_id.invoice_id.amount_total) * tasa
                    sum_vat_reduced_base += h.vat_reduced_base  # Base Imponible de alicuota Reducida
                    sum_vat_reduced_tax += h.vat_reduced_tax
                    # Impuesto de IVA alicuota reducida

                    sum_vat_additional_base += h.vat_additional_base  # BASE IMPONIBLE ALICUOTA ADICIONAL

                    sum_vat_additional_tax += h.vat_additional_tax  # IMPUESTO DE IVA ALICUOTA ADICIONAL

                    sum_total_with_iva = (
                                h.fb_id.base_amount + h.fb_id.tax_amount) if h.emission_date >= date_start.date() else 0  # Total monto con IVA
                    sum_total_with_iva_ajustes = (
                                h.fb_id.base_amount + h.fb_id.tax_amount) if h.emission_date < date_start.date() else 0
                    sum_vat_general_base += h.vat_general_base  # Base Imponible Alicuota general
                    sum_vat_general_tax += h.vat_general_tax  # Impuesto de IVA
                    h_vat_general_base = h.vat_general_base
                    h_vat_general_rate = (
                                h.vat_general_base and h.vat_general_tax * 100 / h.vat_general_base) if h.vat_general_base else 0.0
                    h_vat_general_rate = round(h_vat_general_rate, 0)
                    h_vat_general_tax = h.vat_general_tax if h.vat_general_tax else 0.0
                    vat_reduced_base = h.vat_reduced_base
                    vat_reduced_rate = int(h.vat_reduced_base and h.vat_reduced_tax * 100 / h.vat_reduced_base)
                    vat_reduced_tax = h.vat_reduced_tax
                    vat_additional_base = h.vat_additional_base
                    vat_additional_rate = int(
                        h.vat_additional_base and h.vat_additional_tax * 100 / h.vat_additional_base)
                    vat_additional_tax = h.vat_additional_tax
                    get_wh_vat = h.get_wh_vat

                    emission_date = datetime.strftime(
                        datetime.strptime(str(h.emission_date), DEFAULT_SERVER_DATE_FORMAT),
                        format_new)

            if (partner_1.company_type == 'company' or partner_1.company_type == 'person') and (
                    partner_1.people_type_company or partner_1.people_type_individual) and partner_1.people_type_company == 'pjnd':
                '############## ES UN PROVEEDOR INTERNACIONAL ##############################################'

                if h.invoice_id:
                    tasa = 1
                    if h.invoice_id.currency_id.name == "USD":
                        tasa = self.obtener_tasa(h.invoice_id)
                    if h.invoice_id.fecha_importacion:
                        date_impor = h.invoice_id.fecha_importacion
                        emission_date = datetime.strftime(
                            datetime.strptime(str(date_impor), DEFAULT_SERVER_DATE_FORMAT),
                            format_new)
                        total = h.invoice_id.amount_total * tasa
                    else:
                        date_impor = h.invoice_id.invoice_date
                        emission_date = datetime.strftime(
                            datetime.strptime(str(date_impor), DEFAULT_SERVER_DATE_FORMAT),
                            format_new)

                    planilla = h.invoice_id.nro_planilla_impor
                    expediente = h.invoice_id.nro_expediente_impor




                else:
                    date_impor = h.iwdl_id.invoice_id.fecha_importacion
                    emission_date = datetime.strftime(datetime.strptime(str(date_impor), DEFAULT_SERVER_DATE_FORMAT),
                                                      format_new)
                    planilla = h.iwdl_id.invoice_id.nro_planilla_impor
                    expediente = h.iwdl_id.invoice_id.nro_expediente_impor
                    tasa = 1
                    if h.iwdl_id.invoice_id.currency_id.name == "USD":
                        tasa = self.obtener_tasa(h.iwdl_id.invoice_id)
                    total = h.iwdl_id.invoice_id.amount_total * tasa
                get_wh_vat = 0.0
                vat_reduced_base = 0
                vat_reduced_rate = 0
                vat_reduced_tax = 0
                vat_additional_base = 0
                vat_additional_rate = 0
                vat_additional_tax = 0
                'ALICUOTA GENERAL IMPORTACIONES'
                vat_general_base_importaciones = h.vat_general_base
                vat_general_rate_importaciones = (h.vat_general_base and h.vat_general_tax * 100 / h.vat_general_base)
                vat_general_rate_importaciones = round(vat_general_rate_importaciones, 0)
                vat_general_tax_importaciones = h.vat_general_tax
                'ALICUOTA REDUCIDA IMPORTACIONES'
                vat_reduced_base_importaciones = h.vat_reduced_base
                vat_reduced_rate_importaciones = int(
                    h.vat_reduced_base and h.vat_reduced_tax * 100 / h.vat_reduced_base)
                vat_reduced_tax_importaciones = h.vat_reduced_tax
                'ALICUOTA ADICIONAL IMPORTACIONES'
                vat_additional_base_importaciones = h.vat_additional_base
                vat_additional_rate_importaciones = int(
                    h.vat_additional_base and h.vat_additional_tax * 100 / h.vat_additional_base)
                vat_additional_tax_importaciones = h.vat_additional_tax
                'Suma total compras con IVA'
                sum_total_with_iva = (
                            h.fb_id.base_amount + h.fb_id.tax_amount) if h.emission_date >= date_start.date() else 0
                sum_total_with_iva_ajustes = (
                            h.fb_id.base_amount + h.fb_id.tax_amount) if h.emission_date < date_start.date() else 0
                # Total monto con IVA
                'SUMA TOTAL DE TODAS LAS ALICUOTAS PARA LAS IMPORTACIONES'
                sum_vat_general_base_importaciones += h.vat_general_base + h.vat_reduced_base + h.vat_additional_base  # Base Imponible Alicuota general
                sum_vat_general_tax_importaciones += h.vat_general_tax + h.vat_additional_tax + h.vat_reduced_tax  # Impuesto de IVA

                'Suma total de Alicuota General'
                suma_base_general_importaciones += h.vat_general_base
                sum_base_general_tax_importaciones += h.vat_general_tax

                ' Suma total de Alicuota Reducida'
                sum_vat_reduced_base_importaciones += h.vat_reduced_base  # Base Imponible de alicuota Reducida
                sum_vat_reduced_tax_importaciones += h.vat_reduced_tax  # Impuesto de IVA alicuota reducida
                'Suma total de Alicuota Adicional'
                sum_vat_additional_base_importaciones += h.vat_additional_base  # BASE IMPONIBLE ALICUOTA ADICIONAL
                sum_vat_additional_tax_importaciones += h.vat_additional_tax  # IMPUESTO DE IVA ALICUOTA ADICIONAL

                get_wh_vat = h.get_wh_vat
            sum_get_wh_vat += h.get_wh_vat  # IVA RETENIDO

            if h_vat_general_base != 0:
                valor_base_imponible = h.vat_general_base
                valor_alic_general = h_vat_general_rate
                valor_iva = h_vat_general_tax
            else:
                valor_base_imponible = 0
                valor_alic_general = 0
                valor_iva = 0

            if get_wh_vat != 0:
                hola = get_wh_vat
            else:
                hola = 0

            if h.vat_exempt != 0:
                vat_exempt = h.vat_exempt

            else:
                vat_exempt = 0

            'Para las diferentes alicuotas que pueda tener el proveedor  internacional'
            'todas son mayor a 0'
            if vat_general_rate_importaciones > 0 and vat_reduced_rate_importaciones > 0 and vat_additional_rate_importaciones > 0:
                vat_general_general_rate_importaciones = str(vat_general_rate_importaciones) + ',' + ' ' + str(
                    vat_reduced_rate_importaciones) + ',' + ' ' + str(vat_additional_rate_importaciones) + ' '
            'todas son cero'
            if vat_general_rate_importaciones == 0 and vat_reduced_rate_importaciones == 0 and vat_additional_rate_importaciones == 0:
                vat_general_general_rate_importaciones = 0
            'Existe reducida y adicional'
            if vat_general_rate_importaciones == 0 and vat_reduced_rate_importaciones > 0 and vat_additional_rate_importaciones > 0:
                vat_general_general_rate_importaciones = str(vat_reduced_rate_importaciones) + ',' + ' ' + str(
                    vat_additional_rate_importaciones) + ' '
            'Existe general y adicional'
            if vat_general_rate_importaciones > 0 and vat_reduced_rate_importaciones == 0 and vat_additional_rate_importaciones > 0:
                vat_general_general_rate_importaciones = str(vat_general_rate_importaciones) + ',' + ' ' + str(
                    vat_additional_rate_importaciones) + ' '
            'Existe general y reducida'
            if vat_general_rate_importaciones > 0 and vat_reduced_rate_importaciones > 0 and vat_additional_rate_importaciones == 0:
                vat_general_general_rate_importaciones = str(vat_general_rate_importaciones) + ',' + ' ' + str(
                    vat_reduced_rate_importaciones) + ' '
            'Existe solo la general'
            if vat_general_rate_importaciones > 0 and vat_reduced_rate_importaciones == 0 and vat_additional_rate_importaciones == 0:
                vat_general_general_rate_importaciones = str(vat_general_rate_importaciones)
            'Existe solo la reducida'
            if vat_general_rate_importaciones == 0 and vat_reduced_rate_importaciones > 0 and vat_additional_rate_importaciones == 0:
                vat_general_general_rate_importaciones = str(vat_reduced_rate_importaciones)
            'Existe solo la adicional'
            if vat_general_rate_importaciones == 0 and vat_reduced_rate_importaciones == 0 and vat_additional_rate_importaciones > 0:
                vat_general_general_rate_importaciones = str(vat_additional_rate_importaciones)
            if h.emission_date >= date_start.date():
                datos_compras.append({

                    'emission_date': datetime.strftime(
                        datetime.strptime(str(h.emission_date), DEFAULT_SERVER_DATE_FORMAT),
                        format_new) if h.emission_date else ' ',
                    'partner_vat': h.partner_vat if h.partner_vat else ' ',
                    'partner_name': h.partner_name,
                    'people_type': h.people_type,
                    'wh_number': h.wh_number if h.wh_number else ' ',
                    'invoice_number': h.invoice_number,
                    'affected_invoice': h.affected_invoice,
                    'ctrl_number': (h.invoice_id.correlative if h.invoice_id and hasattr(h.invoice_id, 'correlative') and h.invoice_id.correlative else (h.ctrl_number or '')),
                    'debit_affected': h.numero_debit_credit if h.doc_type == 'N/DB' else False,
                    'credit_affected': h.numero_debit_credit if h.doc_type == 'N/CR' else False,  # h.credit_affected,
                    'type': h.void_form,
                    'doc_type': h.doc_type,
                    'origin': origin,
                    'number': number,
                    'total_with_iva': h.total_with_iva,
                    'vat_exempt': vat_exempt,
                    'compras_credit': compras_credit,
                    'vat_general_base': valor_base_imponible,
                    'vat_general_rate': valor_alic_general,
                    'vat_general_tax': valor_iva,
                    'vat_reduced_base': vat_reduced_base,
                    'vat_reduced_rate': vat_reduced_rate,
                    'vat_reduced_tax': vat_reduced_tax,
                    'vat_additional_base': vat_additional_base,
                    'vat_additional_rate': vat_additional_rate,
                    'vat_additional_tax': vat_additional_tax,
                    'get_wh_vat': h.get_wh_vat,
                    'vat_general_base_importaciones': vat_general_base_importaciones + vat_additional_base_importaciones + vat_reduced_base_importaciones,
                    'vat_general_rate_importaciones': vat_general_general_rate_importaciones,
                    'vat_general_tax_importaciones': vat_general_tax_importaciones + vat_reduced_tax_importaciones + vat_additional_tax_importaciones,
                    'nro_planilla': planilla,
                    'nro_expediente': expediente,
                })
            else:
                datos_compras_ajustes.append({

                    'emission_date': datetime.strftime(
                        datetime.strptime(str(h.emission_date), DEFAULT_SERVER_DATE_FORMAT),
                        format_new) if h.emission_date else ' ',
                    'partner_vat': h.partner_vat if h.partner_vat else ' ',
                    'partner_name': h.partner_name,
                    'people_type': h.people_type,
                    'wh_number': h.wh_number if h.wh_number else ' ',
                    'invoice_number': h.invoice_number,
                    'affected_invoice': h.affected_invoice,
                    'ctrl_number': (h.invoice_id.correlative if h.invoice_id and hasattr(h.invoice_id, 'correlative') and h.invoice_id.correlative else (h.ctrl_number or '')),
                    'debit_affected': h.numero_debit_credit if h.doc_type == 'N/DB' else False,
                    'credit_affected': h.numero_debit_credit if h.doc_type == 'N/CR' else False,  # h.credit_affected,
                    'type': h.void_form,
                    'doc_type': h.doc_type,
                    'origin': origin,
                    'number': number,
                    'total_with_iva': h.total_with_iva,
                    'vat_exempt': vat_exempt,
                    'compras_credit': compras_credit,
                    'vat_general_base': valor_base_imponible,
                    'vat_general_rate': valor_alic_general,
                    'vat_general_tax': valor_iva,
                    'vat_reduced_base': vat_reduced_base,
                    'vat_reduced_rate': vat_reduced_rate,
                    'vat_reduced_tax': vat_reduced_tax,
                    'vat_additional_base': vat_additional_base,
                    'vat_additional_rate': vat_additional_rate,
                    'vat_additional_tax': vat_additional_tax,
                    'get_wh_vat': hola,
                    'vat_general_base_importaciones': vat_general_base_importaciones + vat_additional_base_importaciones + vat_reduced_base_importaciones,
                    'vat_general_rate_importaciones': vat_general_general_rate_importaciones,
                    'vat_general_tax_importaciones': vat_general_tax_importaciones + vat_reduced_tax_importaciones + vat_additional_tax_importaciones,
                    'nro_planilla': planilla,
                    'nro_expediente': expediente,
                })
        'SUMA TOTAL DE ALICUOTA ADICIONAL BASE'
        if sum_vat_additional_base != 0 and sum_vat_additional_base_importaciones > 0:
            sum_ali_gene_addi = sum_vat_additional_base
            sum_vat_additional_base = sum_vat_additional_base
        else:
            sum_ali_gene_addi = sum_vat_additional_base
        'SUMA TOTAL DE ALICUOTA ADICIONAL TAX'
        if sum_vat_additional_tax != 0 and sum_vat_additional_tax_importaciones > 0:
            sum_ali_gene_addi_credit = sum_vat_additional_tax
            sum_vat_additional_tax = sum_vat_additional_tax
        else:
            sum_ali_gene_addi_credit = sum_vat_additional_tax
        'SUMA TOTAL DE ALICUOTA GENERAL BASE'
        if sum_vat_general_base != 0 and suma_base_general_importaciones > 0:
            sum_vat_general_base = sum_vat_general_base
            sum_vat_general_tax = sum_vat_general_tax
        'SUMA TOTAL DE ALICUOTA REDUCIDA BASE'
        if sum_vat_reduced_base != 0 and sum_vat_reduced_base_importaciones > 0:
            sum_vat_reduced_base = sum_vat_reduced_base
            sum_vat_reduced_tax = sum_vat_reduced_tax

        ' IMPORTACIONES ALICUOTA GENERAL + ALICUOTA ADICIONAL'
        if sum_vat_additional_base_importaciones != 0:
            sum_ali_gene_addi_importaciones = sum_vat_additional_base_importaciones
        else:
            sum_ali_gene_addi_importaciones = sum_vat_additional_base_importaciones

        if sum_vat_additional_tax_importaciones != 0:
            sum_ali_gene_addi_credit_importaciones = sum_vat_additional_tax_importaciones
        else:
            sum_ali_gene_addi_credit_importaciones = sum_vat_additional_tax_importaciones

        total_compras_base_imponible = sum_vat_general_base + sum_ali_gene_addi + sum_vat_reduced_base + suma_base_general_importaciones + sum_ali_gene_addi_importaciones + sum_vat_reduced_base_importaciones + suma_vat_exempt
        total_compras_credit_fiscal = sum_vat_general_tax + sum_ali_gene_addi_credit + sum_vat_reduced_tax + sum_base_general_tax_importaciones + sum_ali_gene_addi_credit_importaciones + sum_vat_reduced_tax_importaciones

        date_start = datetime.strftime(datetime.strptime(data['form']['date_from'], DEFAULT_SERVER_DATE_FORMAT),
                                       format_new)
        date_end = datetime.strftime(datetime.strptime(data['form']['date_to'], DEFAULT_SERVER_DATE_FORMAT), format_new)

        if purchasebook_ids.env.company and purchasebook_ids.env.company.street:
            street = str(purchasebook_ids.env.company.street) + ','
        else:
            street = ' '
        return {
            'doc_ids': data['ids'],
            'doc_model': data['model'],
            'date_start': date_start,
            'date_end': date_end,
            'a': 0.00,
            'street': street,
            'company': purchasebook_ids.env.company,
            'datos_compras': datos_compras,
            'datos_compras_ajustes': datos_compras_ajustes,
            'sum_compras_credit': sum_compras_credit,
            'sum_total_with_iva': sum_total_with_iva,
            'suma_vat_exempt': suma_vat_exempt,
            'sum_vat_general_base': sum_vat_general_base,
            'sum_vat_general_tax': sum_vat_general_tax,
            'sum_vat_reduced_base': sum_vat_reduced_base,
            'sum_vat_reduced_tax': sum_vat_reduced_tax,
            'sum_vat_additional_base': sum_vat_additional_base,
            'sum_vat_additional_tax': sum_vat_additional_tax,
            'sum_get_wh_vat': sum_get_wh_vat,
            'sum_ali_gene_addi': sum_ali_gene_addi,
            'sum_ali_gene_addi_credit': sum_ali_gene_addi_credit,
            'suma_base_general_importaciones': suma_base_general_importaciones,
            'sum_base_general_tax_importaciones': sum_base_general_tax_importaciones,
            'sum_vat_general_base_importaciones': sum_vat_general_base_importaciones,
            'sum_vat_general_tax_importaciones': sum_vat_general_tax_importaciones,
            'sum_ali_gene_addi_importaciones': sum_ali_gene_addi_importaciones,
            'sum_ali_gene_addi_credit_importaciones': sum_ali_gene_addi_credit_importaciones,
            'sum_vat_reduced_base_importaciones': sum_vat_reduced_base_importaciones,
            'sum_vat_reduced_tax_importaciones': sum_vat_reduced_tax_importaciones,
            'total_compras_base_imponible': total_compras_base_imponible,
            'total_compras_credit_fiscal': total_compras_credit_fiscal,

        }

    def obtener_tasa(self, invoice):
        fecha = invoice.date
        tasa_id = invoice.currency_id
        tasa = self.env['res.currency.rate'].search([('currency_id', '=', tasa_id.id), ('name', '<=', fecha)],
                                                    order='id desc', limit=1)
        if not tasa:
            raise UserError(
                "Advertencia! \n No hay referencia de tasas registradas para moneda USD en la fecha igual o inferior de la factura %s" % (
                    invoice.name))
        return tasa.rate

#LIBRO DE VENTA PDF
class FiscalBookSaleReport(models.AbstractModel):
    _name = 'report.l10n_ve_full.report_fiscal_sale_book'

    @api.model
    def _get_report_values(self, docids, data=None):
        format_new = "%d/%m/%Y"
        DATE_FORMAT = "%Y-%m-%d"
        DEFAULT_SERVER_DATE_FORMAT = "%Y-%m-%d"

        fb_id = data['form']['book_id']
        busq = self.env['account.fiscal.book'].search([('id', '=', fb_id)])

        # Convertimos a date los rangos de fecha
        date_start = datetime.strptime(data['form']['date_from'], DATE_FORMAT).date()
        date_end   = datetime.strptime(data['form']['date_to'], DATE_FORMAT).date()

        # Traemos todas las líneas del libro fiscal de ventas, con filtro por rango
        # NOTA: Eliminamos el orden directo en el search porque haremos la ordenación
        #      personalizada al final. Solo filtramos por emisión ≥ date_start.
        fbl_obj = self.env['account.fiscal.book.line'].search([
            ('fb_id', '=', busq.id),
            ('emission_date', '>=', date_start),
        ])

        docs = []

        # Inicializamos acumuladores
        suma_total_w_iva                = 0.0
        suma_no_taxe_sale               = 0.0
        suma_vat_general_base           = 0.0
        suma_total_vat_general_base     = 0.0
        suma_total_vat_general_tax      = 0.0
        suma_vat_general_tax            = 0.0
        suma_total_vat_reduced_base     = 0.0
        suma_total_vat_reduced_tax      = 0.0
        suma_vat_reduced_base           = 0.0
        suma_vat_reduced_tax            = 0.0
        suma_total_vat_additional_base  = 0.0
        suma_total_vat_additional_tax   = 0.0
        suma_vat_additional_base        = 0.0
        suma_vat_additional_tax         = 0.0
        suma_get_wh_vat                 = 0.0
        total_ventas_base_imponible      = 0.0
        total_ventas_debit_fiscal        = 0.0

        def _safe_format_date(date_value, out_format):
            if date_value:
                try:
                    return datetime.strftime(
                        datetime.strptime(str(date_value), DEFAULT_SERVER_DATE_FORMAT),
                        out_format
                    )
                except Exception:
                    # Intentamos también con formato "%d/%m/%Y"
                    try:
                        return datetime.strftime(
                            datetime.strptime(str(date_value), "%d/%m/%Y"),
                            out_format
                        )
                    except Exception:
                        return ''
            return ''

        for line in fbl_obj:
            # Solo consideramos líneas que tengan base o sean anulaciones con número de factura
            if (
                line.vat_general_base != 0
                or line.vat_reduced_base != 0
                or line.vat_additional_base != 0
                or line.vat_exempt != 0
                or (line.void_form == '03-ANU' and line.invoice_number)
            ):

                vat_general_base       = 0.0
                vat_general_rate       = 0
                vat_general_tax        = 0.0
                vat_reduced_base       = 0.0
                vat_reduced_rate       = 0
                vat_reduced_tax        = 0.0
                vat_additional_base    = 0.0
                vat_additional_rate    = 0
                vat_additional_tax     = 0.0

                # Si es tipo 'ntp' (sin impuesto), entonces 'no_taxe_sale' toma vat_general_base
                if line.type == 'ntp':
                    no_taxe_sale = line.vat_general_base
                else:
                    no_taxe_sale = 0.0

                # Reducida
                if line.vat_reduced_base and line.vat_reduced_base != 0:
                    vat_reduced_base = line.vat_reduced_base
                    vat_reduced_rate = int(round((line.vat_reduced_tax * 100.0 / line.vat_reduced_base), 0))
                    vat_reduced_tax  = line.vat_reduced_tax
                    if line.emission_date >= date_start:
                        suma_vat_reduced_base += line.vat_reduced_base
                        suma_vat_reduced_tax  += line.vat_reduced_tax

                # Adicional
                if line.vat_additional_base and line.vat_additional_base != 0:
                    vat_additional_base = line.vat_additional_base
                    vat_additional_rate = int(round((line.vat_additional_tax * 100.0 / line.vat_additional_base), 0))
                    vat_additional_tax  = line.vat_additional_tax
                    if line.emission_date >= date_start:
                        suma_vat_additional_base += line.vat_additional_base
                        suma_vat_additional_tax  += line.vat_additional_tax

                # General
                if line.vat_general_base and line.vat_general_base != 0:
                    vat_general_base = line.vat_general_base
                    vat_general_rate = int(round((line.vat_general_tax * 100.0 / line.vat_general_base), 0))
                    vat_general_tax  = line.vat_general_tax
                    if line.emission_date >= date_start:
                        suma_vat_general_base += line.vat_general_base
                        suma_vat_general_tax  += line.vat_general_tax

                # Ajustamos cadenas vacías para tasas
                vat_reduced_rate    = '' if vat_reduced_rate == 0 else str(vat_reduced_rate)
                vat_additional_rate = '' if vat_additional_rate == 0 else str(vat_additional_rate)
                vat_general_rate    = '' if vat_general_rate == 0 else str(vat_general_rate)
                if vat_general_rate == '' and vat_reduced_rate == '' and vat_additional_rate == '':
                    vat_general_rate = 0

                # Formateo de accounting_date a cadena YYYY-MM-DD
                acc_date = line.accounting_date
                if isinstance(acc_date, str):
                    acc_date_str = acc_date
                elif isinstance(acc_date, date):
                    acc_date_str = acc_date.strftime("%Y-%m-%d")
                else:
                    acc_date_str = str(acc_date) if acc_date else ""

                # Construimos el 'ctrl_number' definitivo:
                # - Si existe invoice_id.correlative, lo usamos (asumimos entero o cadena de dígitos).
                # - Si no, tomamos line.ctrl_number tal cual (o cadena vacía si no existe).
                if line.invoice_id and hasattr(line.invoice_id, 'correlative') and line.invoice_id.correlative:
                    ctrl_value = str(line.invoice_id.correlative)
                else:
                    ctrl_value = line.ctrl_number or ''

                # --- FACTURA ---
                doc_dict = {
                    'tipo'                 : 'factura',
                    'rannk'                : line.rank,
                    'emission_date'        : datetime.strftime(
                                                datetime.strptime(str(line.emission_date), DEFAULT_SERVER_DATE_FORMAT),
                                                format_new
                                             ),
                    'partner_vat'          : line.partner_vat or ' ',
                    'partner_name'         : line.partner_name,
                    'people_type'          : line.people_type or ' ',
                    'report_z'             : line.z_report or '',
                    'export_form'          : '',
                    'wh_number'            : line.wh_number,
                    'wh_date'              : _safe_format_date(line.wh_date, format_new),
                    'date_wh_number'       : (line.iwdl_id.retention_id.date_ret
                                              if line.wh_number else ''),
                    'invoice_number'       : line.invoice_number,
                    'n_ultima_factZ'       : line.n_ultima_factZ,
                    'ctrl_number'          : ctrl_value,  # <--- aquí usamos el 'correlative'
                    'debit_note'           : (line.numero_debit_credit
                                              if line.doc_type == 'N/DB' else False),
                    'credit_note'          : (line.numero_debit_credit
                                              if line.doc_type == 'N/CR' else False),
                    'type'                 : line.void_form,
                    'affected_invoice'     : line.affected_invoice or ' ',
                    'total_w_iva'          : line.total_with_iva or 0,
                    'no_taxe_sale'         : line.vat_exempt,
                    'export_sale'          : '',
                    'vat_general_base'     : vat_general_base,
                    'vat_general_rate'     : str(vat_general_rate),
                    'vat_general_tax'      : vat_general_tax,
                    'vat_reduced_base'     : line.vat_reduced_base,
                    'vat_reduced_rate'     : str(vat_reduced_rate),
                    'vat_reduced_tax'      : vat_reduced_tax,
                    'vat_additional_base'  : vat_additional_base,
                    'vat_additional_rate'  : str(vat_additional_rate),
                    'vat_additional_tax'   : vat_additional_tax,
                    'get_wh_vat'           : 0,
                    'accounting_date'      : acc_date_str,
                }
                docs.append(doc_dict)

                # --- RETENCIÓN asociada (se crea una línea aparte si existe withholding) ---
                if line.get_wh_vat and line.wh_number:
                    wh_acc_date = line.wh_date
                    if wh_acc_date:
                        if isinstance(wh_acc_date, str):
                            wh_acc_date_str = wh_acc_date
                        elif isinstance(wh_acc_date, date):
                            wh_acc_date_str = wh_acc_date.strftime("%Y-%m-%d")
                        else:
                            wh_acc_date_str = str(wh_acc_date)
                    else:
                        wh_acc_date_str = acc_date_str

                    ret_dict = {
                        'tipo'                 : 'retencion',
                        'rannk'                : line.rank,
                        'emission_date'        : _safe_format_date(line.wh_date, format_new),
                        'partner_vat'          : line.partner_vat or ' ',
                        'partner_name'         : line.partner_name,
                        'people_type'          : line.people_type or ' ',
                        'report_z'             : '',
                        'export_form'          : '',
                        'wh_number'            : line.wh_number,
                        'wh_date'              : _safe_format_date(line.wh_date, format_new),
                        'date_wh_number'       : (line.iwdl_id.retention_id.date_ret
                                                  if line.wh_number else ''),
                        'invoice_number'       : line.invoice_number,
                        'n_ultima_factZ'       : '',
                        'ctrl_number'          : ctrl_value,
                        'debit_note'           : '',
                        'credit_note'          : '',
                        'type'                 : 'RETENCIÓN',
                        'affected_invoice'     : '',
                        'total_w_iva'          : 0,
                        'no_taxe_sale'         : 0,
                        'export_sale'          : '',
                        'vat_general_base'     : 0,
                        'vat_general_rate'     : '',
                        'vat_general_tax'      : 0,
                        'vat_reduced_base'     : 0,
                        'vat_reduced_rate'     : '',
                        'vat_reduced_tax'      : 0,
                        'vat_additional_base'  : 0,
                        'vat_additional_rate'  : '',
                        'vat_additional_tax'   : 0,
                        'get_wh_vat'           : line.get_wh_vat,
                        'accounting_date'      : wh_acc_date_str,
                    }
                    docs.append(ret_dict)
                    suma_get_wh_vat += line.get_wh_vat

                # Acumulamos totales para ventas
                suma_total_w_iva               += line.total_with_iva
                suma_no_taxe_sale              += line.vat_exempt
                suma_total_vat_general_base    += line.vat_general_base
                suma_total_vat_general_tax     += line.vat_general_tax
                suma_total_vat_reduced_base    += line.vat_reduced_base
                suma_total_vat_reduced_tax     += line.vat_reduced_tax
                suma_total_vat_additional_base += line.vat_additional_base
                suma_total_vat_additional_tax  += line.vat_additional_tax

                total_ventas_base_imponible = (
                    suma_vat_general_base
                    + suma_vat_additional_base
                    + suma_vat_reduced_base
                    + suma_no_taxe_sale
                )
                total_ventas_debit_fiscal = (
                    suma_vat_general_tax
                    + suma_vat_additional_tax
                    + suma_vat_reduced_tax
                )

        # -------------------------------
        # 9) ORDENACIÓN FINAL de la lista 'docs'
        #    - 1er criterio: ctrl_number numérico ascendente
        #    - 2do criterio (en empate o ctrl vacíos): emission_date ascendente
        # -------------------------------
        def _parse_ctrl_numero(ctrl_str):
            """
            Intenta convertir 'ctrl_str' a entero. Si no puede (cadena vacía
            o no numérica), devuelve un valor muy alto para enviarla al final.
            """
            try:
                return int(ctrl_str)
            except:
                return 10**9

        def _parse_emision(fecha_str):
            """
            La 'emission_date' ya está en formato "%d/%m/%Y".
            Si no puede parsearse, devolvemos 1900-01-01 para ordenar al inicio.
            """
            try:
                return datetime.strptime(fecha_str, "%d/%m/%Y")
            except:
                return datetime(1900, 1, 1)

        docs = sorted(
            docs,
            key=lambda x: (
                _parse_ctrl_numero(x.get('ctrl_number', '')),
                _parse_emision(x.get('emission_date', ''))
            )
        )

        # -------------------------------------
        # 10) Formateo final de fechas de impresión
        # -------------------------------------
        date_start_fmt = datetime.strftime(
            datetime.strptime(data['form']['date_from'], DEFAULT_SERVER_DATE_FORMAT),
            format_new
        )
        date_end_fmt = datetime.strftime(
            datetime.strptime(data['form']['date_to'], DEFAULT_SERVER_DATE_FORMAT),
            format_new
        )

        if fbl_obj and fbl_obj[0].fb_id.company_id and fbl_obj[0].fb_id.company_id.street:
            street = str(fbl_obj[0].fb_id.company_id.street) + ','
        else:
            street = ' '

        return {
            'doc_ids'                         : data['ids'],
            'doc_model'                       : data['model'],
            'date_start'                      : date_start_fmt,
            'date_end'                        : date_end_fmt,
            'docs'                            : docs,
            'docs_ajustes'                    : [],
            'a'                               : 0.00,
            'street'                          : street,
            'company'                         : fbl_obj[0].fb_id.company_id if fbl_obj else False,
            'suma_total_w_iva'                : suma_total_w_iva,
            'suma_no_taxe_sale'               : suma_no_taxe_sale,
            'suma_total_vat_general_base'     : suma_total_vat_general_base,
            'suma_total_vat_general_tax'      : suma_total_vat_general_tax,
            'suma_vat_general_base'           : suma_vat_general_base,
            'suma_vat_general_tax'            : suma_vat_general_tax,
            'suma_total_vat_reduced_base'     : suma_total_vat_reduced_base,
            'suma_total_vat_reduced_tax'      : suma_total_vat_reduced_tax,
            'suma_total_vat_additional_base'  : suma_total_vat_additional_base,
            'suma_total_vat_additional_tax'   : suma_total_vat_additional_tax,
            'suma_vat_reduced_base'           : suma_vat_reduced_base,
            'suma_vat_reduced_tax'            : suma_vat_reduced_tax,
            'suma_vat_additional_base'        : suma_vat_additional_base,
            'suma_vat_additional_tax'         : suma_vat_additional_tax,
            'suma_get_wh_vat'                 : suma_get_wh_vat,
            'suma_ali_gene_addi'              : suma_vat_additional_base,
            'suma_ali_gene_addi_debit'        : suma_vat_additional_tax,
            'total_ventas_base_imponible'      : total_ventas_base_imponible,
            'total_ventas_debit_fiscal'        : total_ventas_debit_fiscal,
        }