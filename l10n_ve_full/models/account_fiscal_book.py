import string
import time
from odoo import fields, models, api, _
from odoo.exceptions import UserError
# from odoo.addons import decimal_precision as dp
from datetime import timedelta, datetime, date
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
import logging
_logger = logging.getLogger(__name__)

class AccountFiscalBook(models.Model):
    _description = "Libro de Compra o Venta"
    _name = 'account.fiscal.book'
    _check_company_auto = True
    _inherit = ['mail.thread', 'mail.activity.mixin']

    FORNIGHT = [('first', "First Fortnight"), ('second', "Second Fortnight")]

    STATES = [('draft', 'Preparándose'),
              ('confirmed', 'Aprobado por el Responsable'),
              ('done', 'Enviado al Seniat'),
              ('cancel', 'Cancelar')]

    TYPES = [('sale', 'Libro de Venta'),
             ('purchase', 'Libro de Compra')]

    TIME_PERIODS = [('this_month', 'Este mes'),
                    ('this_quarter', 'Esta Trimestre'),
                    ('this_year', 'Este año Fiscal'),
                    ('last_month', 'Último mes'),
                    ('last_quarter', 'Último Trimestre'),
                 #   ('last_year', 'Último año Fiscal'),
                    ('custom', 'Personalizado')]

    @api.model
    def _get_type(self):
        context = self._context or {}
        return context.get('type', 'purchase')

    
    def _get_article_number(self):
        context = self._context or {}
        company_brw = self.env['res.users'].browse().company_id
        if context.get('type') == 'sale':
            #return company_brw.printer_fiscal and '78' or '76'
            return '76'
        else:
            return '75'

    
    def _get_article_number_types(self):

        company_brw = self.env['res.users'].browse().company_id
        if self._context.get('type') == 'sale':
            #if company_brw.printer_fiscal:
            #    return [('77', 'Article 77'), ('78', 'Article 78')]
            #else:
            return [('76', 'Article 76')]
        else:
            return [('75', 'Article 75')]

    
    def _get_partner_addr(self):
        """ It returns Partner address in printable format for the fiscal book
        report.
        @param field_name: field [get_partner_addr]
        """

        rp_obj = self.env['res.partner']
        res = {}.fromkeys(self.ids, 'NO HAY DIRECCION FISCAL DEFINIDA')
        # TODO: ASK: what company, fisal.book.company_id?
        ru_obj = self.env['res.users']
        rc_brw = ru_obj.browse().company_id
        addr = rp_obj._find_accounting_partner(rc_brw.partner_id)
        for fb_id in self.ids:
            if addr:
                res[fb_id] = (addr.street or '') + \
                             ' ' + (addr.street2 or '') + ' ' + (addr.zip or '') + ' ' \
                             + (addr.city or '') + ' ' + \
                             (addr.country_id and addr.country_id.name or '') + \
                             ', TELF.:' + (addr.phone or '') or \
                             'NO HAY DIRECCION FISCAL DEFINIDA'
        return res

    
    def _get_month_year(self):
        """ It returns an string with the information of the the year and month
        of the fiscal book.
        @param field_name: field [get_month_year]
        """

        months = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                  "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre",
                  "Diciembre"]
        res = {}.fromkeys(self.ids, '')
        for fb_brw in self.browse(self.ids):
            month = months[time.strptime(fb_brw.date_start, "%Y-%m-%d")[1] - 1]
            year = time.strptime(fb_brw.date_start, "%Y-%m-%d")[0]
            res[fb_brw.id] = ("Correspodiente al Mes de " + str(month) +
                              " del año " + str(year))
        return res

    
    def _get_total_with_iva_sum(self, field_names=None):
        """ It returns sum of of all columns total with iva of the fiscal book
        lines.
        @param field_name: ['get_total_with_iva_sum',
                            'get_total_with_iva_imex_sum',
                            'get_total_with_iva_do_sum',
                            'get_total_with_iva_tp_sum',
                            'get_total_with_iva_ntp_sum',
                            ]"""
        res = {}
        if field_names:
            res = {}.fromkeys(self.ids, {}.fromkeys(field_names, 0.0))
        op_types = ["imex", "do", "tp", "ntp"]
        for fb_brw in self.browse():
            for fbl_brw in fb_brw.fbl_ids:
                # TODO LINEA ORIGINAL SE COMENTA POR SU RELACION CON EL MODELO customs.form DEL MODULO l10n_ve_imex
                # if fbl_brw.invoice_id or fbl_brw.cf_id:
                # TODO SI SE UTILIZA LA LINEA ANTERIOR SE DEBE COMENTAR LA SIGUIENTE
                if fbl_brw.invoice_id:
                    fbl_op_type = fbl_brw.type in ['im', 'ex'] and 'imex' \
                                  or fbl_brw.type
                    fbl_index = "get_total_with_iva_" + fbl_op_type + "_sum"
                    res[fb_brw.id][fbl_index] += fbl_brw.total_with_iva

            res[fb_brw.id]['get_total_with_iva_sum'] = \
                sum([res[fb_brw.id]["get_total_with_iva_" + optype + "_sum"]
                     for optype in op_types])
        return res

    
    def _get_vat_sdcf_sum(self):
        """ It returns the SDCF sumation of purchase (imported, domestic) or
        sale (Exports, tax payer, Non-Tax Payer) operations types.
        @param field_name: field ['get_vat_sdcf_sum'] """

        res = {}.fromkeys(self.ids, 0.0)
        for fb_brw in self.browse():
            res[fb_brw.id] = fb_brw.type == 'purchase' \
                             and (fb_brw.imex_sdcf_vat_sum + fb_brw.do_sdcf_vat_sum) \
                             or (fb_brw.imex_sdcf_vat_sum + fb_brw.tp_sdcf_vat_sum +
                                 fb_brw.ntp_sdcf_vat_sum)
        return res

    
    def _get_total_tax_credit_debit(self, field_names):
        """ It returns sum of of all data in the fiscal book summary table.
        @param field_name: ['get_total_tax_credit_debit_base_sum',
                            'get_total_tax_credit_debit_tax_sum']
        """
        # TODO: summations of all taxes types? only ret types?
        res = {}.fromkeys(self.ids, {}.fromkeys(field_names, 0.0))
        for fb_brw in self.browse():
            op_types = fb_brw.type == 'purchase' and ['imex', 'do'] \
                       or ['imex', 'tp', 'ntp']
            tax_types = ['reduced', 'general', 'additional']

            res[fb_brw.id]['get_total_tax_credit_debit_base_sum'] += \
                sum([getattr(fb_brw, op + '_' + ttax + '_vat_base_sum')
                     for ttax in tax_types
                     for op in op_types])

            res[fb_brw.id]['get_total_tax_credit_debit_tax_sum'] += \
                sum([getattr(fb_brw, op + '_' + ttax + '_vat_tax_sum')
                     for ttax in tax_types
                     for op in op_types])
        return res

    
    def _get_wh(self, field_names):
        """ It returns sum of all data in the withholding summary table.
        @param field_name: ['get_total_wh_sum', 'get_previous_wh_sum',
                            'get_wh_sum']"""
        # TODO: this works if its ensuring that that emmision date is always
        # set and and all periods for every past dates are created.
        res = {}.fromkeys(self.ids, {}.fromkeys(field_names, 0.0))

        for fb_brw in self.browse():
            for fbl_brw in fb_brw.fbl_ids:
                if fbl_brw.iwdl_id:
                    # TODO revisar este metodo
                    # emission_period = period_obj.find(fbl_brw.emission_date)
                    local_period = self.get_time_period(self.time_period)
                    if local_period.get('dt_from') <= fb_brw.emission_date <= local_period.get('dt_to'):
                        res[fb_brw.id]['get_wh_sum'] += \
                            fbl_brw.iwdl_id.amount_tax_ret
                        res[fb_brw.id]['get_wh_debit_credit_sum'] += \
                            fbl_brw.get_wh_debit_credit
                    else:
                        res[fb_brw.id]['get_previous_wh_sum'] += \
                            fbl_brw.iwdl_id.amount_tax_ret
            res[fb_brw.id]['get_total_wh_sum'] = \
                res[fb_brw.id]['get_wh_sum'] + \
                res[fb_brw.id]['get_previous_wh_sum']
        return res

    
    def _get_do_adjustment_vat_tax_sum(self):
        res = {}
        for fb_brw in self.browse():
            avts = 0
            for fbl_brw in fb_brw.fbl_ids:
                if fbl_brw.doc_type == 'AJST':
                    avts += fbl_brw._get_wh_vat(fb_brw.id)
            res[fb_brw.id] = avts
        return res

    def _get_default_company(self):
        for inv in self.issue_invoice_ids:
            res_company = self.env['res.company'].search([('id', '=', inv.company_id.id)])
            if not res_company:
                res_company = self.env.company
            return res_company
    # def _get_company(self):
    #     user = self.env['res.users'].browse(self.uid)
    #     return user.company_id.id



    name = fields.Char('Descripción', size=256, required=True)
    company_id = fields.Many2one(
        'res.company', string='Compañia',
        default=lambda self: self.env.company,  readonly=True, store=True,
        help="Compañia", required=True)
   # company_id = fields.Many2one('res.company', 'Compañia', help='Company', )
    # period_id = fields.Many2one('account.period', string='Period', required=True,
    #        help="Book's Fiscal Period. The periods listed are thouse how are "
    #             "regular periods, i.e. not opening/closing periods.")
    currency_id = fields.Many2one('res.currency', string='Moneda')
    period_start = fields.Date('Período Inicio')
    period_end = fields.Date('Período Fin')

    fortnight = fields.Selection(FORNIGHT, string="Quincena", default=None,
                                 help="Fortnight that applies to the current book.")
    state = fields.Selection(STATES, string='Estatus', required=True, readonly=True, default='draft')
    type = fields.Selection(TYPES, help="Select Sale for Customers and Purchase for Suppliers",
                            string='Tipo de libro', required=True, default=lambda s: s._get_type())
    base_amount = fields.Float('Base imponible', help='Cantidad utilizada como base imponible')
    tax_amount = fields.Float('Cantidad gravada', help='Cantidad gravada sobre la base imponible')
    fbl_ids = fields.One2many('account.fiscal.book.line', 'fb_id', 'Lineas de libros',
                              help='Lines being recorded in the book')
    fbt_ids = fields.One2many('account.fiscal.book.taxes', 'fb_id', 'Lineas de Impuestos',
                              help='Taxes being recorded in the book')
    fbts_ids = fields.One2many('account.fiscal.book.taxes.summary', 'fb_id', 'Resumen de Impuestos')
    invoice_ids = fields.One2many('account.move', 'fb_id', 'Facturas', help="Las facturas se registran en un "
                                                                               "Libro fiscal")
    issue_invoice_ids = fields.One2many('account.move', 'issue_fb_id', 'Emitir facturas',
                                        help="Las facturas que están en estado pendiente cancelan o se borran")
    iwdl_ids = fields.One2many('account.wh.iva.line', 'fb_id', 'Retenciones de IVA',
                               help="Retenciones de IVA registradas en un libro fiscal")
    # TODO CAMPO RELACIONADO CON MODULO DE IMPUESTOS DE 9MPORTACION Y EXPORTACION (l10n_ve_imex)
    # cf_ids = fields.One2many('customs.form', 'fb_id', 'Customs Form',
    #                            help="Customs Form being recorded in the Fiscal Book")
    # TODO FALTA RESOLVER ERROR: invf = comodel._fields[self.inverse_name]
    # abl_ids = fields.One2many('adjustment.book.line', 'fb_id', 'Adjustment Lines',
    #                            help="Adjustment Lines being recorded in a Fiscal Book")
    note = fields.Text('Note')
    # TODO covert function _get_article_number_types() & _get_article_number() to ODOO 11 and check parameters
    article_number = fields.Selection(_get_article_number_types, string="Número de artículo",
                                      required=True, default=lambda s: s._get_article_number(),
                                      help="Número de artículo que describe las características especiales del libro fiscal "
                                           "De acuerdo con la declaración venezolana RLIVA para fiscal"
                                           "libros de contabilidad. Opciones:"
                                           "- Art. 75: Libro de compra"
                                           "- Art. 76: Libro de ventas. Refleja cada operación individual"
                                           "detalle"
                                           "- Art. 77: Libro de ventas. Agrupa operaciones de contribuyentes no tributarios en"
                                           " uno "
                                           "línea consolidada. Solo facturación fiscal"
                                           "- Art. 78: Libro de venta. Híbrido para el artículo 76 y 77. Mostrar"
                                           "operaciones automáticas y mecanizadas de manera individual, y"
                                           "agrupa las operaciones de facturación fiscal en una consolidada"
                                           "línea.")
    # Withholding fields
    get_wh_sum = fields.Float(compute='_get_wh',
                               store=True, #multi="get_wh",
                              string="Retención del período actual",
                              help="Usado en"
                                   " 1. Fila de totalización en el bloque de la línea del libro fiscal en la retención"
                                   " Columna de -iva"
                                   " 2. Second row at the Withholding Summary block ")
    get_previous_wh_sum = fields.Float( compute='_get_wh',
                                        store=True, #multi="get_wh",
                                       string="Retención del período anterior",
                                       help="Primera fila en el bloque Resumen de retención")
    get_total_wh_sum = fields.Float(compute='_get_wh',
                                     store=True, #multi="get_wh",
                                    string="Suma de retención de IVA",
                                    help="Fila de totalización en el bloque Resumen de retención")
    get_wh_debit_credit_sum = fields.Float(compute='_get_wh',
                                            store=True, #multi="get_wh",
                                           string="Suma de débito fiscal basado",
                                           help="Fila de totalización en el bloque de la línea del libro fiscal en "
                                                "Columna de débito fiscal basado")

    # Printable report data
    get_partner_addr = fields.Char(compute='_get_partner_addr',
                                   type="text",
                                   help='Partner address printable format')
    get_month_year = fields.Char(compute='_get_month_year',
                                 type="text",
                                 help='Year and Month ot the Fiscal book period')

    # Totalization fields for all type of transactions
    get_total_with_iva_sum = fields.Float(compute='_get_total_with_iva_sum',
                                        store=True,
                                          string='Importe total con IVA',
                                          help="Total con suma de IVA (importación / exportación, nacional, contribuyente y "
                                               "Pagador no tributario")
    get_vat_sdcf_sum = fields.Float(compute='_get_vat_sdcf_sum',
                                    store=True,
                                    string="Exento y suma de impuestos SDCF",
                                    help="Exentos y sin derecho a la totalización del crédito fiscal. La suma de"
                                         "SDCF y columnas de totalización de impuestos exentos para todas las transacciones"
                                         "tipos")
    get_total_tax_credit_debit_base_sum = fields.Float(compute='_get_total_tax_credit_debit',
                                                        store=True,
                                                  #     multi="get_total_tax_credit_debit",
                                                       string="Monto base total del crédito fiscal",
                                                       help="Usos en 1. compra: fila total en el resumen de impuestos "
                                                            "2. ventas: fila en el resumen de impuestos")
    get_total_tax_credit_debit_tax_sum = fields.Float(compute='_get_total_tax_credit_debit',
                                                       store=True,
                                                   #   multi="get_total_tax_credit_debit",
                                                      string="Crédito fiscal Monto total de impuestos")
    do_sdcf_and_exempt_sum = fields.Float(digits='Account',
                                          string="Suma de IVA interno no gravado",
                                          help="SDCF y Exempt sum para domestict transanctions "
                                               "En la venta, el libro representa la suma del contribuyente y el no contribuyente")

    # Totalization fields for international transactions
    get_total_with_iva_imex_sum = fields.Float(compute='_get_total_with_iva_sum',
                                                store=True,
                                            #   multi="get_total_with_iva",
                                               string="Importe total con IVA",
                                               help="Total importado / exportado con totalización del IVA")
    imex_vat_base_sum = fields.Float(#digits=(16, 2),
                                     string="Monto imponible internacional",
                                     help="Suma de importes de base impositiva internacional (reducida, general "
                                          "y adicional). Utilizado en la segunda fila en el resumen del libro de ventas"
                                          "con el título de ventas de exportación")
    imex_exempt_vat_sum = fields.Float(#digits=(16, 2),
                                       string="Impuesto exento",
                                       help="Totalización de impuestos exentos de importación / exportación: suma de exentos "
                                            "columna para transacciones internacionales")
    imex_sdcf_vat_sum = fields.Float(#digits=(16, 2),
                                     string="Impuesto SDCF",
                                     help="Importación / Exportación Totalización de impuestos SDCF: Suma de la columna SDCF "
                                          "para transacciones internacionales")
    imex_general_vat_base_sum = fields.Float(#digits=(16, 2),
                                             string="Importe imponible general del IVA",
                                             help="General IVA Impuestos Importaciones / Exportaciones Monto base. La suma de"
                                                  "Columna base general del IVA para transacciones internacionales")
    imex_general_vat_tax_sum = fields.Float(#digits=(16, 2),
                                            string="Cantidad gravada del IVA general",
                                            help="Impuesto general a las importaciones / impuestos a la importación Monto del impuesto. La suma de"
                                                 "Columna de IVA general para transacciones internacionales")
    imex_additional_vat_base_sum = fields.Float(#digits=(16, 2),
                                                string="Importe sujeto a IVA adicional",
                                                help="Importes adicionales gravados con IVA / exportaciones Base Monto. La suma de"
                                                     "Columna Base de IVA adicional para transacciones internacionales")
    imex_additional_vat_tax_sum = fields.Float(#digits=(16, 2),
                                               string="Cantidad de IVA adicional gravada",
                                               help="Impuesto adicional sobre las importaciones / Importes de impuestos. La suma de "
                                                    "Columna de IVA adicional para transacciones internacionales")
    imex_reduced_vat_base_sum = fields.Float(#digits=(16, 2),
                                             string="Importe sujeto a impuestos de IVA Reducido",
                                             help="IVA Reducido Importaciones / exportaciones Base Monto base. La suma de "
                                                  "Columna base de IVA reducido para transacciones internacionales")
    imex_reduced_vat_tax_sum = fields.Float(#digits=(16, 2),
                                            string="Importe reducido de IVA",
                                            help="Reducción del IVA Impuesto de Importaciones / Exportaciones Monto del impuesto. La suma de "
                                                 "Columna de IVA reducido para transacciones internacionales")

    # Totalization fields for domestic transactions
    get_total_with_iva_do_sum = fields.Float(compute='_get_total_with_iva_sum',
                                              store=True,
                                             multi="get_total_with_iva",
                                             string='Importe total con IVA',
                                             help="Total nacional con totalización de IVA")
    do_vat_base_sum = fields.Float(#digits=(16, 2),
                                   string="Cantidad imponible nacional",
                                   help="Suma de todos los importes básicos de las transacciones nacionales (reducido, "
                                        "general y adicional)")
    do_exempt_vat_sum = fields.Float(
        #digits=(16, 2),
        string="Impuesto exento",
        help="Totalización de impuestos nacionales exentos. Para la Reserva de compra"
             "sumas Columna exenta para transacciones nacionales. En la reserva de venta"
             "Sumas de las columnas de exención del contribuyente y del no contribuyente")
    do_sdcf_vat_sum = fields.Float(#digits=(16, 2),
                                   string="Impuesto SDCF",
                                   help="Totalización de impuestos nacionales SDCF. Para el libro de compra se resume "
                                        "Columna SDCF para transacciones nacionales. Para la venta Reserve sumas"
                                        "Columnas SDCF de contribuyentes y no contribuyentes")
    do_general_vat_base_sum = fields.Float(#digits=(16, 2),
                                           string="Importe imponible general del IVA",
                                           help="Totalización general de la base imponible del IVA general "
                                                "Para el Libro de compras, suma la columna Base general del IVA para uso doméstico"
                                                "transacciones. Para el libro de venta se suma al contribuyente y al contribuyente no tributario"
                                                "Columnas generales de base de IVA")
    do_general_vat_tax_sum = fields.Float(#digits=(16, 2),
                                          string="Cantidad gravada del IVA general",
                                          help="Totalización de impuestos nacionales gravados con IVA general "
                                               "Para el libro de compras, suma la columna del impuesto general del IVA para los nacionales"
                                               "transacciones. Para el libro de venta se suma al contribuyente y al contribuyente no tributario"
                                               "Columnas generales del impuesto sobre el IVA")
    do_additional_vat_base_sum = fields.Float(#digits=(16, 2),
                                              string="Importe sujeto a IVA adicional",
                                              help="Totalización del monto base nacional gravado con IVA adicional "
                                                   "Para el Libro de compras, suma la columna Base de IVA adicional para"
                                                   "transacciones nacionales. Para la venta Libro que suma el contribuyente y no"
                                                   "Columnas de la base de IVA adicional del contribuyente")
    do_additional_vat_tax_sum = fields.Float(#digits=(16, 2),
                                             string="Cantidad de IVA adicional gravada",
                                             help="Totalización del monto del impuesto interno gravado con IVA adicional "
                                                  "Para el Libro de compras, suma la columna de IVA adicional para"
                                                  "transacciones nacionales. Para el libro de ventas suma las"
                                                  "Columnas de impuestos adicionales del contribuyente   y no Contribuyente")
    do_reduced_vat_base_sum = fields.Float(#digits=(16, 2),
                                           string="Importe sujeto a impuestos reducido",
                                           help="Reduced VAT Taxed Domestic Base Amount Totalization."
                                                " For Purchase Book it sums Reduced VAT Base column for domestic"
                                                " transactions. For Sale Book it sums Tax Payer and Non-Tax Payer"
                                                " Reduced VAT Base columns")
    do_reduced_vat_tax_sum = fields.Float(#digits=(16, 2),
                                          string="Importe reducido de IVA",
                                          help="Reducción del total de impuestos nacionales gravados con IVA reducido "
                                               "Para el libro de compras, suma la columna de impuestos reducidos de IVA para nacionales"
                                               "transacciones. Para el libro de venta se suma al contribuyente y al no contribuyente "
                                               "Columnas de IVA reducido")
    do_adjustment_vat_tax_sum = fields.Float(#compute='_get_do_adjustment_vat_tax_sum',
                                              type='float',
                                             string='Ajuste IVA de Cantidad de Impuesto')

    # Apply only for sale book
    # Totalization fields for tax payer and Non-Tax Payer transactions
    ntp_fbl_ids = fields.One2many("account.fiscal.book.line", "ntp_fb_id", string="Non-Tax Payer Detail Lines",
                                  help="Non-Tax Payer Lines that are grouped by the statement law that"
                                       " represent the data of are consolidate book lines")
    get_total_with_iva_tp_sum = fields.Float(compute='_get_total_with_iva_sum',
                                              store=True,
                                      #       multi="get_total_with_iva",
                                             string="Total amount with VAT",
                                             help="Tax Payer Total with VAT Totalization")
    tp_vat_base_sum = fields.Float(#digits=(16, 2),
                                   string="Tax Payer Taxable Amount",
                                   help="Sum of all Tax Payer Grand Base Sum (reduced, general and"
                                        " additional taxes)")
    tp_exempt_vat_sum = fields.Float(#digits=(16, 2),
                                     string="Exempt Tax",
                                     help="Tax Payer Exempt Tax Totalization. Sum of Exempt column"
                                          " for tax payer transactions")
    tp_sdcf_vat_sum = fields.Float(#digits=(16, 2),
                                   string="SDCF Tax",
                                   help="Tax Payer SDCF Tax Totalization. Sum of SDCF column for"
                                        " tax payer transactions")
    tp_general_vat_base_sum = fields.Float(#digits=(16, 2),
                                           string="General VAT Taxable Amount",
                                           help="General VAT Taxed Tax Payer Base Amount Totalization."
                                                " Sum of General VAT Base column for taxy payer transactions")
    tp_general_vat_tax_sum = fields.Float(#digits=(16, 2),
                                          string="General VAT Taxed Amount",
                                          help="General VAT Taxed Tax Payer Tax Amount Totalization."
                                               " Sum of General VAT Tax column for tax payer transactions")
    tp_additional_vat_base_sum = fields.Float(#digits=(16, 2),
                                              string="Additional VAT Taxable Amount",
                                              help="Additional VAT Taxed Tax Payer Base Amount Totalization."
                                                   " Sum of Additional VAT Base column for tax payer transactions")
    tp_additional_vat_tax_sum = fields.Float(digits=(16, 2),
                                             string="Additional VAT Taxed Amount",
                                             help="Additional VAT Taxed Tax Payer Tax Amount Totalization."
                                                  " Sum of Additional VAT Tax column for tax payer transactions")
    tp_reduced_vat_base_sum = fields.Float(#digits=(16, 2),
                                           string="Reduced VAT Taxable Amount",
                                           help="Reduced VAT Taxed Tax Payer Base Amount Totalization."
                                                " Sum of Reduced VAT Base column for tax payer transactions")
    tp_reduced_vat_tax_sum = fields.Float(#digits=(16, 2),
                                          string="Reduced VAT Taxed Amount",
                                          help="Reduced VAT Taxed Tax Payer Tax Amount Totalization."
                                               " Sum of Reduced VAT Tax column for tax payer transactions")
    get_total_with_iva_ntp_sum = fields.Float(compute='_get_total_with_iva_sum',
                                               store=True,
                                        #      multi="get_total_with_iva",
                                              string="Total amount with VAT",
                                              help="Non-Tax Payer Total with VAT Totalization")
    ntp_vat_base_sum = fields.Float(#digits=(16, 2),
                                    string="Non-Tax Payer Taxable Amount",
                                    help="Non-Tax Payer Grand Base Totalization. Sum of all no tax"
                                         " payer tax bases (reduced, general and additional)")
    ntp_exempt_vat_sum = fields.Float(#digits=(16, 2),
                                      string="Exempt Tax",
                                      help="Non-Tax Payer Exempt Tax Totalization. Sum of Exempt"
                                           " column for Non-Tax Payer transactions")
    ntp_sdcf_vat_sum = fields.Float(#digits=(16, 2),
                                    string="SDCF Tax",
                                    help="Non-Tax Payer SDCF Tax Totalization. Sum of SDCF column"
                                         " for Non-Tax Payer transactions")
    ntp_general_vat_base_sum = fields.Float(#digits=(16, 2),
                                            string="General VAT Taxable Amount",
                                            help="General VAT Taxed Non-Tax Payer Base Amount Totalization."
                                                 " Sum of General VAT Base column for taxy payer transactions")
    ntp_general_vat_tax_sum = fields.Float(#digits=(16, 2),
                                           string="General VAT Taxed Amount",
                                           help="General VAT Taxed Non-Tax Payer Tax Amount Totalization."
                                                " Sum of General VAT Tax column for Non-Tax Payer transactions")
    ntp_additional_vat_base_sum = fields.Float(#digits=(16, 2),
                                               string="Additional VAT Taxable Amount",
                                               help="Additional VAT Taxed Non-Tax Payer Base Amount Totalization."
                                                    " Sum of Additional VAT Base column for Non-Tax Payer"
                                                    " transactions")
    ntp_additional_vat_tax_sum = fields.Float(#digits=(16, 2),
                                              string="Additional VAT Taxed Amount",
                                              help="Additional VAT Taxed Non-Tax Payer Tax Amount Totalization."
                                                   " Sum of Additional VAT Tax column for Non-Tax Payer"
                                                   " transactions")
    ntp_reduced_vat_base_sum = fields.Float(#digits=(16, 2),
                                            string="Reduced VAT Taxable Amount",
                                            help="Reduced VAT Taxed Non-Tax Payer Base Amount Totalization."
                                                 " Sum of Reduced VAT Base column for Non-Tax Payer transactions")
    ntp_reduced_vat_tax_sum = fields.Float(#digits=(16, 2),
                                           string="Reduced VAT Taxed Amount",
                                           help="Reduced VAT Taxed Non-Tax Payer Tax Amount Totalization."
                                                " Sum of Reduced VAT Tax column for Non-Tax Payer transactions")

    journal_ids = fields.Many2many('account.journal', string='Diarios')


    _rec_rame = 'fiscal_book_rec'
    time_period = fields.Selection(TIME_PERIODS, 'Período', default='this_month', required=True)

    # TODO revisar los efectos de este constraint
    _sql_constraints = [
        # ('period_type_company_uniq', 'unique (period_id,type,company_id,fortnight)',
        ('period_type_company_uniq', 'unique (type,company_id,fortnight)',
         'The period, type, fortnight combination must be unique per company!'),
    ]

    @api.onchange('time_period')
    def _onchange_time_period(self):
        for rec in self:
            periodo = self.get_time_period(self.time_period)



    def get_time_period(self, period_type, fiscal_book=None):
        _logger.info(f"Calculando get_time_period con period_type: {period_type}")
        dates_selected = {}
        if not period_type:
            raise UserError("Error! \nDebe seleccionar un período para el libro fiscal.")

        today = date.today()
        dt_from = False
        dt_to = False

        if period_type == 'custom':
            # Para 'custom', SÍ leemos los campos del formulario
            record = fiscal_book if fiscal_book else self
            dt_from = record.period_start
            dt_to = record.period_end
            _logger.info(f"Periodo 'custom' seleccionado: {dt_from} a {dt_to}")

        elif period_type == 'this_month':
            dt_from = today.replace(day=1)
            dt_to = (today.replace(day=1) + timedelta(days=31)).replace(day=1) - timedelta(days=1)

        elif period_type == 'this_quarter':
            quarter = (today.month - 1) // 3 + 1
            dt_to = (today.replace(month=quarter * 3, day=1) + timedelta(days=31)).replace(day=1) - timedelta(days=1)
            dt_from = dt_to.replace(day=1, month=dt_to.month - 2, year=dt_to.year)

        elif period_type == 'this_year':
            company_fiscalyear_dates = self.env.company.compute_fiscalyear_dates(datetime.now())
            dt_from = company_fiscalyear_dates['date_from']
            dt_to = company_fiscalyear_dates['date_to']

        elif period_type == 'last_month':
            dt_to = today.replace(day=1) - timedelta(days=1)
            dt_from = dt_to.replace(day=1)

        elif period_type == 'last_quarter':
            quarter = (today.month - 1) // 3 + 1
            quarter = quarter - 1 if quarter > 1 else 4
            dt_to = (today.replace(month=quarter * 3, day=1,
                                 year=today.year if quarter != 4 else today.year - 1) + timedelta(days=31)).replace(
                day=1) - timedelta(days=1)
            dt_from = dt_to.replace(day=1, month=dt_to.month - 2, year=dt_to.year)
        
        # Si las fechas se calcularon y estamos en un onchange (fiscal_book is None)
        # O si el libro no las tiene guardadas (para el update_book)
        if dt_from and dt_to:
            target_record = fiscal_book if fiscal_book else self
            if not target_record.period_start or not target_record.period_end or not fiscal_book:
                _logger.info(f"Actualizando fechas en el registro: {dt_from} a {dt_to}")
                target_record.period_start = dt_from
                target_record.period_end = dt_to
        
        if not dt_from or not dt_to:
             _logger.warning("¡Las fechas dt_from/dt_to siguen siendo False!")

        dates_selected.update({'dt_from': dt_from, 'dt_to': dt_to})
        return dates_selected

    # action methods
    # TODO Revisar colocar este onchange en el metodo creado para las fechas
    @api.onchange('article_number', 'period_start', 'period_end')
    def onchange_field_clear_book(self):
        """ It make clear all stuff of book. """
        self.clear_book()

    # update book methods
    
    def _get_invoice_ids(self, fb_brw): # Parámetro cambiado a fb_brw
        """
        It returns ids from open and paid invoices regarding to the type and
        period of the fiscal book order by date invoiced.
        """
        _logger.info(f"--- Iniciando _get_invoice_ids para Libro: {fb_brw.name} ---")
        inv_obj = self.env['account.move']
        inv_type = fb_brw.type == 'sale' and ['out_invoice', 'out_refund'] or ['in_invoice', 'in_refund']
        inv_state = ['paid', 'open', 'cancel']
        if fb_brw.type == 'purchase':
            inv_state = ['paid', 'open']

        local_period = self.get_time_period(fb_brw.time_period, fiscal_book=fb_brw)
        dt_from = local_period.get('dt_from')
        dt_to = local_period.get('dt_to')
        _logger.info(f"Periodo: {dt_from} a {dt_to}")

        domain = [('date', '>=', dt_from),
                  ('date', '<=', dt_to),
                  ('company_id', '=', fb_brw.company_id.id),
                  ('move_type', 'in', inv_type),
                  ('state', 'in', inv_state)]

        if fb_brw.journal_ids:
            _logger.info(f"Diarios seleccionados (regular): {fb_brw.journal_ids.ids}")
            domain.append(('journal_id', 'in', fb_brw.journal_ids.ids))
        else:
            _logger.warning("No hay diarios seleccionados. El filtro de diario no se aplicará.")

        _logger.info(f"Dominio de Búsqueda (regular): {domain}")
        inv_ids = inv_obj.search(domain, order='date, name asc')
        _logger.info(f"Facturas encontradas (regular - antes de quincena): {len(inv_ids)}")

        if fb_brw.fortnight:
            inv_ids = self.get_invoices_from_fortnight(fb_brw, inv_ids, dt_from, dt_to)
        if fb_brw.type == 'purchase':
            inv_ids = self.get_invoices_sin_cred(fb_brw, inv_ids)

        _logger.info(f"Facturas finales (regular - post-filtro): {len(inv_ids)}")
        return inv_ids

    
    def get_invoices_sin_cred(self, ids, inv_ids):
        """
        if the fiscal book is of type purchase then need to filter the invoice
        of the book by only the ones how has sin_cred == False.
        return the filter invoices list.
        @param inv_ids: list of invoice ids
        @return invoices list
        """
        inv_obj = self.env['account.move']
        ids = isinstance(ids, (int, int)) and [ids] or ids
        res = list()
        for inv_id in inv_ids:
            # inv_brw = inv_obj.browse(inv_id)
            if not inv_id.sin_cred:
                res.append(inv_id)
        return res

    
    # Corrected get_invoices_from_fortnight
    def get_invoices_from_fortnight(self, fb_id, inv_ids, d_st, d_en):
        """
        Returns invoices filtered by the fiscal book's fortnight.
        @param fb_id: fiscal book recordset
        @param inv_ids: list/recordset of invoice objects/ids to filter
        @param d_st: start date of the period
        @param d_en: end date of the period
        @return filtered list of invoice recordsets
        """
        inv_obj = self.env['account.move']
        res = []
        # CORRECTED: Access fortnight field directly
        is_second_fortnight = fb_id.fortnight == 'second'

        # Ensure inv_ids is a recordset for easier field access
        if inv_ids and isinstance(inv_ids[0], (int, int)): # Check if it's a list of IDs
             inv_ids = inv_obj.browse([inv.id for inv in inv_ids]) # Browse if needed, adapt if already objects

        for invoice in inv_ids: # Iterate directly over records
            invoice_date = invoice.date # Assuming date is the correct field

            if is_second_fortnight:
                # Calculate the 16th of the month
                mid_month_day = 16
                start_second_fortnight = d_st.replace(day=mid_month_day)
                # Check if the invoice date is from the 16th to the end date
                if start_second_fortnight <= invoice_date <= d_en:
                    res.append(invoice)
            else: # First fortnight
                # Calculate the 15th of the month
                mid_month_day = 15
                end_first_fortnight = d_st.replace(day=mid_month_day)
                # Check if the invoice date is from the start date to the 15th
                if d_st <= invoice_date <= end_first_fortnight:
                    res.append(invoice)

        return res # Return a list of recordsets

    
    def action_confirm(self):
        if not self.fbl_ids:
            self.update_book()
        self.write({'state': 'confirmed'})

    
    def action_done(self):
        self.write({'state': 'done'})

    
    def action_cancel(self):
        self.clear_book()
        self.write({'state': 'cancel'})

    
    def set_to_draft(self):
        self.write({'state': 'draft'})

    
    def update_book(self):
        """ It generate and fill book data with invoices, wh iva lines and
        taxes. """
        _logger.info("--- INICIANDO update_book ---")
        local_fb = self.browse(self.ids)
        
        for fb_brw in local_fb:
            _logger.info(f"Procesando Libro: {fb_brw.name} (ID: {fb_brw.id})")
            
            # Limpiar el libro
            self.clear_book() 
            
            # --- CORRECCIÓN DE PARÁMETROS ---
            # Todos los métodos deben recibir el OBJETO (fb_brw), no el ID
            
            _logger.info("Llamando a update_book_invoices...")
            self.update_book_invoices(fb_brw) 
            
            _logger.info("Llamando a update_book_issue_invoices...")
            self.update_book_issue_invoices(fb_brw) 
            
            _logger.info("Llamando a update_book_wh_iva_lines...")
            self.update_book_wh_iva_lines(fb_brw) # <--- CORREGIDO (antes era fb_brw.id)
            
            _logger.info("Llamando a update_book_lines...")
            self.update_book_lines(fb_brw) # <--- CORREGIDO (antes era fb_brw.id)
            
            # --- FIN CORRECCIÓN ---

            printer_fiscal = False #self.company_id.printer_fiscal
            busq = self.browse(fb_brw.id) # Esto es redundante, ya tienes fb_brw
            if printer_fiscal == False and fb_brw.type == 'purchase': # Usar fb_brw
                for lin in self.fbl_ids:
                    condi = 0
                    for lin2 in self.fbl_ids:
                        if lin.doc_type == lin2.doc_type and lin.emission_date == lin2.emission_date and lin.ctrl_number == lin2.ctrl_number and lin.invoice_number == lin2.invoice_number and lin.invoice_id.partner_id == lin2.invoice_id.partner_id:
                            condi += 1
                    if condi > 1:
                        lin.unlink()
            
            _logger.info("Llamando a reajuste_totales...")
            self.reajuste_totales()
            
        _logger.info("--- FINALIZANDO update_book ---")
        return True

    def reajuste_totales(self):
        base_amount = tax_amount = 0
        for lin in self.fbl_ids:
            base_amount += lin.vat_exempt + lin.vat_general_base + lin.vat_reduced_base + lin.vat_additional_base
            tax_amount += lin.vat_general_tax + lin.vat_reduced_tax + lin.vat_additional_tax
        self.base_amount = base_amount
        self.tax_amount = tax_amount

    def update_book_invoices(self, fb_id):
        """ It relate/unrelate the invoices to the fical book.
        @param fb_id: fiscal book id
        """

        inv_obj = self.env['account.move']
        # Relate invoices
        inv_ids = self._get_invoice_ids(fb_id)
        for invoice in inv_ids:
            invoice.write({'fb_id': fb_id.id})
        return True

    
    def _get_issue_invoice_ids(self, fb_brw):
        """ It returns ids from not open or paid invoices regarding to the type
        and period of the fiscal book order by date invoiced.
        @param fb_brw: fiscal book recordset.
        """
        _logger.info(f"--- Iniciando _get_issue_invoice_ids para Libro: {fb_brw.name} ---")
        inv_obj = self.env['account.move']

        inv_type = fb_brw.type == 'sale' and ['out_invoice', 'out_refund'] or ['in_invoice', 'in_refund']
        inv_state = ['posted', 'cancel']
        if fb_brw.type == 'purchase':
            inv_state = ['posted']

        local_period = self.get_time_period(fb_brw.time_period, fiscal_book=fb_brw)
        dt_from = local_period.get('dt_from')
        dt_to = local_period.get('dt_to')
        _logger.info(f"Periodo (issue): {dt_from} a {dt_to}")

        domain = [('date', '>=', dt_from),
                  ('date', '<=', dt_to),
                  ('company_id', '=', fb_brw.company_id.id),
                  ('move_type', 'in', inv_type),
                  ('state', 'in', inv_state)]

        if fb_brw.journal_ids:
            _logger.info(f"Diarios seleccionados (issue): {fb_brw.journal_ids.ids}")
            domain.append(('journal_id', 'in', fb_brw.journal_ids.ids))
        else:
            _logger.warning("No hay diarios seleccionados (issue). El filtro de diario no se aplicará.")

        _logger.info(f"Dominio de Búsqueda (issue): {domain}")
        issue_inv_ids = inv_obj.search(domain, order='id asc')
        _logger.info(f"Facturas encontradas (issue - antes de quincena): {len(issue_inv_ids)}")

        if fb_brw.fortnight:
            issue_inv_ids = self.get_invoices_from_fortnight(fb_brw, issue_inv_ids, dt_from, dt_to)
        if fb_brw.type == 'purchase':
            issue_inv_ids = self.get_invoices_sin_cred(fb_brw, issue_inv_ids)

        _logger.info(f"Facturas finales (issue - post-filtro): {len(issue_inv_ids)}")
        return issue_inv_ids

    def update_book_issue_invoices(self, fb_brw): # Ahora (cambiamos nombre)
        """ It relate the issue invoices to the fiscal book. That criterion is:
          - Invoices of the period in state different form open or paid state.
          - Invoices already related to the book but it have a period change.
        @param fb_id: fiscal book id
        """
        docum = ' '
        inv_obj = self.env['account.move']
        issue_inv_ids = self._get_issue_invoice_ids(fb_brw) # Ahora
        for invoice in issue_inv_ids:
            tasa = 1
            if not invoice.currency_id == invoice.company_id.currency_id:
                module_dual_currency = self.env['ir.module.module'].sudo().search(
                    [('name', '=', 'account_dual_currency'), ('state', '=', 'installed')])
                if module_dual_currency:
                    tasa = invoice.tax_today
                else:
                    tasa = self.obtener_tasa(invoice)
            # if invoice.currency_id.name == "USD":
            #     tasa = self.obtener_tasa(invoice)
            amount_total = invoice.amount_total * tasa
            impuestos_exc = (amount_total + (invoice.amount_tax_signed))
            total = amount_total
            a_pagar = amount_total

            if invoice.move_type == 'in_invoice':
                docum = invoice.supplier_invoice_number
            elif invoice.move_type == 'out_invoice':
                docum = invoice.name
            elif invoice.move_type == 'in_refund' or 'out_refund':
                docum = invoice.invoice_origin
            update = {'issue_fb_id': fb_brw.id # Usar el ID del objeto fb_brw
                 }
            invoice.write(update)
        return True

    def _get_wh_iva_line_ids(self, fb_brw): # Parámetro cambiado a fb_brw (objeto)
        """ It returns ids from wh iva lines with state 'done' regarding to the
        fiscal book period.
        @param fb_brw: fiscal book recordset
        """
        _logger.info(f"--- Iniciando _get_wh_iva_line_ids para Libro: {fb_brw.name} ---")

        awi_obj = self.env['account.wh.iva']
        awil_obj = self.env['account.wh.iva.line']
        # fb_brw = self.browse(fb_id) # No es necesario, fb_brw ya es el objeto
        awil_type = fb_brw.type == 'sale' \
                    and ['out_invoice', 'out_refund', 'out_debit'] \
                    or ['in_invoice', 'in_refund', 'in_debit']
        
        awil_ids = []
        local_period = self.get_time_period(fb_brw.time_period, fiscal_book=fb_brw)
        dt_from = local_period.get('dt_from')
        dt_to = local_period.get('dt_to')
        _logger.info(f"Periodo (retenciones): {dt_from} a {dt_to}")

        # Buscar retenciones usando period_id O date_ret
        # Primero intentar con period_id
        domain_period = [('period_id', '>=', dt_from),
                        ('period_id', '<=', dt_to),
                        ('type', 'in', awil_type),
                        ('state', '=', 'done')]
        
        domain_date = [('date_ret', '>=', dt_from),
                      ('date_ret', '<=', dt_to),
                      ('type', 'in', awil_type),
                      ('state', '=', 'done')]

        # --- MODIFICADO: NO filtrar por journal_ids del libro ---
        # Las retenciones tienen sus propios journals (diferentes a los de facturas)
        # Por lo tanto, no aplicamos el filtro de journal_ids del libro a las retenciones
        _logger.info("Las retenciones se buscarán en TODOS los journals de retención (sin filtro de journal_ids del libro)")
        # --- FIN DE MODIFICACIÓN ---
        
        # Buscar con period_id primero
        _logger.info(f"Dominio de Búsqueda (retenciones con period_id): {domain_period}")
        awi_ids_period = awi_obj.search(domain_period)
        _logger.info(f"Retenciones encontradas con period_id: {len(awi_ids_period)}")
        if len(awi_ids_period) > 0:
            _logger.info(f"IDs de retenciones con period_id: {awi_ids_period.ids}")
            for ret in awi_ids_period:
                _logger.info(f"  - ID: {ret.id}, Número: {ret.number}, Period: {ret.period_id}, Date_ret: {ret.date_ret}, State: {ret.state}, Type: {ret.type}")
        
        # Buscar con date_ret como fallback
        _logger.info(f"Dominio de Búsqueda (retenciones con date_ret): {domain_date}")
        awi_ids_date = awi_obj.search(domain_date)
        _logger.info(f"Retenciones encontradas con date_ret: {len(awi_ids_date)}")
        if len(awi_ids_date) > 0:
            _logger.info(f"IDs de retenciones con date_ret: {awi_ids_date.ids}")
        
        # Combinar ambos resultados (unión de recordsets)
        awi_ids = awi_ids_period | awi_ids_date
        _logger.info(f"Retenciones totales encontradas (awi_ids): {len(awi_ids)}")

        if fb_brw.fortnight:
            awi_ids = self.get_awi_from_fortnight(fb_brw.id, awi_ids, dt_from, dt_to) # Pasamos el ID aquí si la función lo espera
        
        awil_final_ids = self.env['account.wh.iva.line'] # Crear un recordset vacío
        for awi_id in awi_ids:
            # awil_ids.append(awil_obj.search([('retention_id', '=', awi_id.id)]))
            awil_final_ids |= awil_obj.search([('retention_id', '=', awi_id.id)])
        
        _logger.info(f"Líneas de retención finales encontradas (awil_ids): {len(awil_final_ids)}")
        return awil_final_ids # Devolvemos el recordset

    def get_awi_from_fortnight(self, ids, awi_ids, d_st=None, d_en=None):
        """
        return the awi ids with the same fortnight as the fiscal book.
        @param awi_ids: list of account withholding iva document ids (recordsets).
        @param ids: only one fiscal book id (integer).
        @return account withholding document id list (recordsets)
        """
        # 'ids' viene como un entero, 'awi_ids' como recordset
        res = []
        fb_brw = self.browse(ids) # Obtenemos el recordset del libro
        is_second_fortnight = fb_brw.fortnight == 'second'

        if not d_st or not d_en:
             # Fallback si las fechas no se pasaron (aunque deberían)
             local_period = self.get_time_period(fb_brw.time_period, fiscal_book=fb_brw)
             d_st = local_period.get('dt_from')
             d_en = local_period.get('dt_to')

        for awi_rec in awi_ids: # awi_ids ya es un recordset
            awi_date = awi_rec.date_ret # Fecha de la retención

            if is_second_fortnight:
                # Calcular día 16
                start_second_fortnight = d_st.replace(day=16)
                if start_second_fortnight <= awi_date <= d_en:
                    res.append(awi_rec)
            else: # Primera quincena
                # Calcular día 15
                end_first_fortnight = d_st.replace(day=15)
                if d_st <= awi_date <= end_first_fortnight:
                    res.append(awi_rec)
        return res

    # TODO: test this method.
    def update_book_wh_iva_lines(self, fb_brw): # Parámetro fb_brw (objeto)
        """ It relate/unrelate the wh iva lines to the fiscal book.
        @param fb_brw: fiscal book recordset
        """
        _logger.info(f"--- Iniciando update_book_wh_iva_lines para Libro: {fb_brw.name} ---")

        iwdl_obj = self.env['account.wh.iva.line']
        rp_obj = self.env['res.partner']
        # fb_brw = self.browse(fb_id) # No es necesario, fb_brw ya es el objeto
        
        # Relate wh iva lines
        iwdl_ids = self._get_wh_iva_line_ids(fb_brw) # Pasamos el objeto

        if (fb_brw.type == "purchase" and iwdl_ids and not
        rp_obj._find_accounting_partner(
            fb_brw.company_id.partner_id).wh_iva_agent):
            raise UserError("Error! \nTiene retenciones registradas pero no es un agente de retención.")
        
        _logger.info(f"Asignando {len(iwdl_ids)} líneas de retención al libro...")
        for iwdl in iwdl_ids:
            # --- ¡AQUÍ ESTÁ LA CORRECCIÓN! ---
            # Debes pasar el ID (fb_brw.id), no el objeto (fb_brw)
            iwdl.write({'fb_id': fb_brw.id})
            # --- FIN DE LA CORRECCIÓN ---

        # Unrelate wh iva lines
        all_iwdl_ids = iwdl_obj.search([('fb_id', '=', fb_brw.id)])
        iwdl_to_unrelate = all_iwdl_ids - iwdl_ids # Más eficiente
        
        _logger.info(f"Desvinculando {len(iwdl_to_unrelate)} líneas de retención antiguas...")
        for iwdl_id_to_check in iwdl_to_unrelate:
             iwdl_id_to_check.write({'fb_id': False})
             
        return True

    def _get_invoice_iwdl_id(self, fb_id, inv_id):
        """ It check if the invoice have wh iva lines asociated and if its
        check if it is at the same period. Return the wh iva line ID or False
        instead.
        @param fb_id: fiscal book id.
        @param inv_id: invoice id to get wh line.
        """

        # inv_obj = self.env['account.move']
        # inv_brw = inv_obj.browse( inv_id)
        iwdl_obj = self.env['account.wh.iva.line']
        iwdl_id = False
        if inv_id.wh_iva_id:
            iwdl_id = iwdl_obj.search([('invoice_id', '=', inv_id.id), ('fb_id', '=', fb_id)])
        return iwdl_id and iwdl_id[0] or False

    def _get_orphan_iwdl_ids(self, fb_id):
        """ It returns a list of ids from the orphan wh iva lines in the period
        that have not associated invoice.
        @param fb_id: fiscal book id
        """

        iwdl_obj = self.env['account.wh.iva.line']
        inv_ids = [inv_brw.id
                   for inv_brw in self.browse(fb_id).issue_invoice_ids]
        inv_wh_ids = \
            [iwdl_brw.invoice_id.id for iwdl_brw in self.browse(fb_id).iwdl_ids]
        orphan_inv_ids = set(inv_wh_ids) - set(inv_ids)
        orphan_inv_ids = list(orphan_inv_ids)
        hola = iwdl_obj.search([('invoice_id', 'in', orphan_inv_ids)])
        return orphan_inv_ids and hola or []

    def get_order_criteria_adjustment(self, book_type):
        #return book_type == 'sale' \
        #       and 'accounting_date asc, ctrl_number asc' \
        #       or 'emission_date asc, invoice_number asc'

        return 'accounting_date asc, invoice_number asc'

    def get_order_criteria(self, book_type):
        #return book_type == 'sale' \
        #   and 'accounting_date asc, invoice_number asc' \
        #   or 'emission_date asc, invoice_number asc'
        return 'accounting_date asc, invoice_number asc'

    def order_book_lines(self, fb_id):
        """ It orders book lines by a set of criteria:
            - chronologically ascendant date (For purchase book by
              emission date, for sale book by accounting date).
            - ascendant ordering for fiscal printer ascending number.
            - ascendant ordering for z report number.
            - ascendant ordering for invoice number.
        @param fb_id: book id.
        """

        fbl_obj = self.env['account.fiscal.book.line']
        fb_brw = self.browse(fb_id)
        fbl_ids = [line_brw.id for line_brw in fb_brw.fbl_ids]

        ajst_order_criteria = self.get_order_criteria_adjustment(
            fb_brw.type)
        ajst_ordered_fbl_ids = fbl_obj.search([('id', 'in', fbl_ids), ('doc_type', '=', 'AJST')],
                                              order=ajst_order_criteria)

        for rank, fbl_id in enumerate(ajst_ordered_fbl_ids, 1):
            fbl_obj.write(fbl_id, {'rank': rank})

        order_criteria = self.get_order_criteria(fb_brw.type)
        ordered_fbl_ids = fbl_obj.search([('id', 'in', fbl_ids), ('doc_type', '!=', 'AJST')], order=order_criteria)

        for rank, fbl_id in enumerate(ordered_fbl_ids, len(ajst_ordered_fbl_ids) + 1):
            fbl_id.write({'rank': rank})

        return True

    def _get_no_match_date_iwdl_ids(self, fb_id):
        """ It returns a list of wh iva lines ids that have a invoice in the
        same book period but where the invoice invoice_date is different from
        the wh iva line date.
        @param fb_id: fiscal book id.
        """

        iwdl_obj = self.env['account.wh.iva.line']
        res = []

        for inv_brw in self.issue_invoice_ids:
            iwdl_id = self._get_invoice_iwdl_id(fb_id, inv_brw)
            if iwdl_id:
                if inv_brw.date != iwdl_id.date_ret:
                    res.append(iwdl_id)
        return res


    def get_t_type(self, doc_type=None, name=None, state=False):
        tt = ''
        if doc_type:
            #if doc_type == "N/DB" or doc_type == "N/CR":
            #validar, segun seniat las notas rectificativas deben aparecer como 01-REG y solo las NOtas de debitos como 02-COMP
            if doc_type == "N/DB":
                tt = '02-COMP'
            elif doc_type == "N/CR" or state=='cancel':
                tt = '03-ANU'
            else:
                tt = '01-REG'
        return tt

    # Funcion que limpia el numero de factura para que no aparezca "papelanulado"
    
    def get_number(self, local_inv_nbr):
        tt = ''
        busqueda = local_inv_nbr.find('PAPELANULADO')

        if busqueda != -1: #si es distinto de -1 encontro la palabra
            posicion = local_inv_nbr.find("(")
            tt = local_inv_nbr[0:posicion]
        else:
            tt = local_inv_nbr
        return tt

    
    def update_book_lines(self, fb_brw): # El parámetro ya es el objeto fb_brw
        """ It updates the fiscal book lines values. Cretate, order and rank
        the book lines. Creates the book taxes too acorring to lines created.
        @param fb_brw: fiscal book recordset (objeto)
        """
        _logger.info(f"--- Iniciando update_book_lines para Libro: {fb_brw.name} ---")

        data = []
        data2= []
        iwdl_obj = self.env['account.wh.iva.line']
        rp_obj = self.env['res.partner']
        local_inv_affected = ''
        boll = False
        cliente = False
        proveedor = False
        # Initialize inv_siva and inv_iva as empty recordsets
        inv_siva = self.env['account.move']
        inv_iva = self.env['account.move']
        fecha = ''

        _logger.info(f"Procesando {len(fb_brw.issue_invoice_ids)} facturas de issue_invoice_ids...")
        for inv_brw in fb_brw.issue_invoice_ids:
            # Logic to classify inv_siva / inv_iva
            # Use |= to add records to the recordsets
            if inv_brw.wh_iva_id.state in ['draft', 'cancel'] and (inv_brw.state == 'posted' or inv_brw.state == 'cancel') and not inv_brw.sin_cred:
                inv_siva |= inv_brw
            elif inv_brw.wh_iva_id.state == 'done' and inv_brw.state == 'posted' and not inv_brw.sin_cred:
                inv_iva |= inv_brw

            if not inv_brw.wh_iva_id and not inv_brw.partner_id.wh_iva_agent and (inv_brw.state == 'posted' or inv_brw.state == 'cancel') and not inv_brw.sin_cred:
                inv_siva |= inv_brw
            elif not inv_brw.wh_iva_id and inv_brw.partner_id.wh_iva_agent and (inv_brw.state == 'posted' or inv_brw.state == 'cancel') and not inv_brw.sin_cred:
                inv_siva |= inv_brw

        _logger.info(f"Facturas CON retención (inv_iva): {len(inv_iva)}")
        _logger.info(f"Facturas SIN retención (inv_siva): {len(inv_siva)}")

        busq = fb_brw

        if inv_iva:
            # --- CORRECTION STARTS HERE ---
            # Always start with an empty recordset for iwdl_ids
            iwdl_ids = self.env['account.wh.iva.line']

            # Get orphan lines (this returns a recordset or an empty list)
            orphan_iwdl_ids_result = self._get_orphan_iwdl_ids(fb_brw.id)
            # If it's not an empty list, assign it
            if orphan_iwdl_ids_result:
                 iwdl_ids = orphan_iwdl_ids_result # Assign the recordset directly

            # --- CORRECTION ENDS HERE ---

            t_type = fb_brw.type == 'sale' and 'tp' or 'do'

            for iwdl_otro1 in inv_iva:
                otro = iwdl_otro1.id
                # Now this line will always work because iwdl_ids is a recordset
                iwdl_ids |= iwdl_obj.search([('invoice_id', '=', otro)])

            _logger.info(f"Procesando {len(iwdl_ids)} líneas de retención (iwdl_ids)...")
            for iwdl_brw in iwdl_ids:
                 # ... (rest of your loop logic remains the same) ...
                 rp_brw = rp_obj._find_accounting_partner(iwdl_brw.retention_id.partner_id)
                 people_type = 'N/A'
                 document_v = 'N/A'
                 if rp_brw:
                     if rp_brw.company_type == 'company':
                         people_type = rp_brw.people_type_company
                         if people_type == 'pjdo':
                             document_v = rp_brw.rif
                     elif rp_brw.company_type == 'person':
                         if rp_brw.rif:
                             document_v = rp_brw.rif
                             people_type = rp_brw.people_type_individual
                         else:
                             people_type = rp_brw.people_type_individual
                             if rp_brw.nationality == 'V' or rp_brw.nationality == 'E':
                                 document_v = str(rp_brw.nationality) + str(rp_brw.identification_id)
                             else:
                                 document_v = rp_brw.identification_id

                 doc_type = self.get_doc_type(inv_id=iwdl_brw.invoice_id.id)
                 local_inv_affected = False # Reset for each line
                 fecha = False # Reset for each line

                 if (doc_type == "N/DB" or doc_type == "N/CR"):
                     if fb_brw.type == 'sale':
                         if iwdl_brw.invoice_id.move_type == 'out_refund':
                             cliente = True
                             local_inv_affected = iwdl_brw.invoice_id.reversed_entry_id.name
                             fecha = iwdl_brw.invoice_id.reversed_entry_id.date
                         elif iwdl_brw.invoice_id.move_type == 'out_invoice': # Assuming Debit Notes are out_invoice
                             cliente = True
                             debit_note_origin = iwdl_brw.invoice_id.debit_origin_id
                             if debit_note_origin:
                                 local_inv_affected = debit_note_origin.name
                                 fecha = debit_note_origin.date
                     elif fb_brw.type == 'purchase': # Added purchase type check
                         if iwdl_brw.invoice_id.move_type == 'in_invoice' and doc_type == 'N/DB':
                             proveedor = True
                             debit_note_origin = iwdl_brw.invoice_id.debit_origin_id
                             if debit_note_origin:
                                 local_inv_affected = debit_note_origin.supplier_invoice_number
                                 fecha = debit_note_origin.invoice_date
                         elif iwdl_brw.invoice_id.move_type == 'in_refund' and doc_type == 'N/CR':
                             proveedor = True
                             # Corrected way to get affected invoice for vendor credit note
                             reversed_entry = iwdl_brw.invoice_id.reversed_entry_id
                             if reversed_entry:
                                 local_inv_affected = reversed_entry.supplier_invoice_number
                                 fecha = reversed_entry.invoice_date
                             # Fallback or alternative if invoice_reverse_purchase_id exists (custom field?)
                             # elif hasattr(iwdl_brw.invoice_id, 'invoice_reverse_purchase_id') and iwdl_brw.invoice_id.invoice_reverse_purchase_id:
                             #     local_inv_affected = iwdl_brw.invoice_id.invoice_reverse_purchase_id.supplier_invoice_number
                             #     fecha = iwdl_brw.invoice_id.invoice_reverse_purchase_id.invoice_date


                 sign = -1 if doc_type == 'N/CR' else 1

                 values = {
                     'iwdl_id': iwdl_brw.id,
                     'type': t_type,
                     'accounting_date': iwdl_brw.date_ret or False,
                     'emission_date': iwdl_brw.invoice_id.invoice_date or iwdl_brw.invoice_id.date or False,
                     'doc_type': doc_type, # Use the calculated doc_type
                     'wh_number': iwdl_brw.retention_id.number or False,
                     'get_wh_vat': (iwdl_brw.amount_tax_ret or 0.0) * sign, # Ensure amount_tax_ret is not None
                     'partner_name': rp_brw.name if rp_brw else 'N/A', # Check rp_brw exists
                     'people_type': people_type,
                     'partner_vat': document_v,
                     # Simplified affected invoice logic
                     'affected_invoice': local_inv_affected if doc_type in ("N/DB", "N/CR") else False,
                     'affected_invoice_date': fecha or False,
                     'wh_rate': iwdl_brw.wh_iva_rate,
                     # Unified invoice/debit/credit number logic
                     'invoice_number': iwdl_brw.invoice_id.supplier_invoice_number if fb_brw.type == 'purchase' else iwdl_brw.invoice_id.name,
                     'ctrl_number': iwdl_brw.invoice_id.correlative or "",
                     'void_form': self.get_t_type(doc_type, state=iwdl_brw.invoice_id.state), # Pass state too
                     'fiscal_printer': iwdl_brw.invoice_id.fiscal_printer or False,
                     'z_report': False, # Assuming always false for lines based on wh
                     'wh_date': iwdl_brw.retention_id.date_ret or False,
                     # Removed numero_debit_credit, handled by invoice_number now
                     # Removed debit_affected/credit_affected, handled by affected_invoice
                 }
                 data.append((0, 0, values))


        _logger.info(f"Procesando {len(inv_siva)} facturas (inv_siva)...")
        for inv_otro in inv_siva:
            local_inv_affected = False # Reset
            local_inv_nbr = ''
            people_type = 'N/A'
            doc_type = self.get_doc_type(inv_id=inv_otro.id)
            rp_brw = rp_obj._find_accounting_partner(inv_otro.partner_id)
            document_v = 'N/A'
            fecha = False # Reset

            if rp_brw:
                if rp_brw.company_type == 'company':
                    people_type = rp_brw.people_type_company
                    if people_type == 'pjdo': # Assuming pjdo means domiciled legal entity
                         document_v = rp_brw.rif
                elif rp_brw.company_type == 'person':
                    people_type = rp_brw.people_type_individual
                    if rp_brw.rif: # Prefer RIF if available for individuals too
                        document_v = rp_brw.rif
                    elif rp_brw.nationality in ('V', 'E') and rp_brw.identification_id:
                         document_v = str(rp_brw.nationality) + str(rp_brw.identification_id)
                    elif rp_brw.identification_id: # Fallback to ID if no RIF/Nationality
                         document_v = rp_brw.identification_id

            if (doc_type == "N/DB" or doc_type == "N/CR"):
                if fb_brw.type == 'sale':
                     if inv_otro.move_type == 'out_refund':
                         cliente = True
                         local_inv_affected = inv_otro.reversed_entry_id.name
                         local_inv_nbr = inv_otro.name # Use Odoo name for credit note
                         fecha = inv_otro.reversed_entry_id.date
                     elif inv_otro.move_type == 'out_invoice': # Debit Note
                         cliente = True
                         debit_note_origin = inv_otro.debit_origin_id
                         if debit_note_origin:
                             local_inv_affected = debit_note_origin.name
                             fecha = debit_note_origin.date
                         local_inv_nbr = inv_otro.name # Use Odoo name for debit note
                elif fb_brw.type == 'purchase':
                     if inv_otro.move_type == 'in_invoice' and doc_type == 'N/DB':
                         proveedor = True
                         debit_note_origin = inv_otro.debit_origin_id
                         if debit_note_origin:
                             local_inv_affected = debit_note_origin.supplier_invoice_number
                             fecha = debit_note_origin.invoice_date
                         local_inv_nbr = inv_otro.supplier_invoice_number
                     elif inv_otro.move_type == 'in_refund' and doc_type == 'N/CR':
                         proveedor = True
                         reversed_entry = inv_otro.reversed_entry_id
                         if reversed_entry:
                             local_inv_affected = reversed_entry.supplier_invoice_number
                             fecha = reversed_entry.invoice_date
                         local_inv_nbr = inv_otro.supplier_invoice_number


            sign = -1 if doc_type == 'N/CR' else 1

            # Determine the correct invoice number based on type
            current_invoice_number = inv_otro.supplier_invoice_number if fb_brw.type == 'purchase' else inv_otro.name

            values = {
                 'invoice_id': inv_otro.id,
                 'emission_date': (inv_otro.invoice_date or inv_otro.date) or False,
                 'accounting_date': inv_otro.date or False,
                 'type': self.get_transaction_type(fb_brw.id, inv_otro.id),
                 'ctrl_number': inv_otro.correlative if not inv_otro.fiscal_printer and inv_otro.correlative != 'False' else '',
                 'affected_invoice': local_inv_affected if doc_type in ("N/DB", "N/CR") else False,
                 'affected_invoice_date': fecha or False,
                 'partner_name': rp_brw.name if rp_brw else 'N/A',
                 'people_type': people_type,
                 'partner_vat': document_v,
                 'invoice_number': current_invoice_number,
                 'doc_type': doc_type,
                 'void_form': self.get_t_type(doc_type, state=inv_otro.state),
                 'fiscal_printer': inv_otro.fiscal_printer or False,
                 'z_report': False, # Assuming false for regular invoices/notes
                 # Removed numero_debit_credit, debit_affected, credit_affected
             }
            # Set amounts to zero if cancelled
            if inv_otro.state == 'cancel':
                 values.update({
                    'total_with_iva': 0.0,
                    'vat_sdcf': 0.0,
                    'vat_exempt': 0.0,
                    'vat_reduced_base': 0.0,
                    'vat_reduced_tax': 0.0,
                    'vat_general_base': 0.0,
                    'vat_general_tax': 0.0,
                    'vat_additional_base': 0.0,
                    'vat_additional_tax': 0.0,
                    'get_wh_vat': 0.0, # Also zero out withholding if cancelled
                 })


            data.append((0, 0, values))


        if data:
             _logger.info(f"Escribiendo {len(data)} líneas en fbl_ids...")
             # Use the correct object fb_brw, not self
             fb_brw.write({'fbl_ids': data})
             _logger.info("Llamando a link_book_lines_and_taxes...")
             self.link_book_lines_and_taxes(fb_brw.id)
        else:
             _logger.warning("No se generaron datos (data) en update_book_lines.")

        # --- Order/Group Lines ---
        # It's better to call these *after* link_book_lines_and_taxes
        # so that the lines have their tax data calculated before grouping/ordering.
        if fb_brw.article_number in ['77', '78']:
             _logger.info("Llamando a update_book_ntp_lines...")
             self.update_book_ntp_lines(fb_brw.id) # This function expects an ID
        else:
             _logger.info("Llamando a order_book_lines...")
             self.order_book_lines(fb_brw.id) # This function expects an ID

        _logger.info(f"--- Finalizando update_book_lines para Libro: {fb_brw.name} ---")
        return True

    def get_grouped_consecutive_lines_ids(self, lines_ids):
        """ Return a list of tuples that represent every line in the book.
        If there is a group of consecutive Non-Tax Payer with fiscal printer
        billing lines, it will return a unique tuple that holds the information
        of the lines. The return tutple has this format
            ('invoice_number'[0], 'invoice_number'[-1], [line_brw])
            - 'invoice_number'[0]: invoice number of the first line in the
            group
            - 'invoice_number'[-1]: invoice number of the last line in the
            group
            - [line_brw] list o browse records that weel be into the line.
        @param line_ids: list of book lines ids.
        """

        lines_brws = self.env['account.fiscal.book.line'].browse(lines_ids)
        res = list()
        group_list = list()
        group_value = False

        for line_brw in lines_brws:
            group_value = group_value or line_brw.type
            if line_brw.type == group_value and group_value == 'ntp' and line_brw.fiscal_printer:
                group_list.append(line_brw)
            else:
                if group_list:
                    res.append((group_list[0].invoice_number,
                                group_list[-1].invoice_number, group_value,
                                group_list))
                    group_value = line_brw.type
                    group_list = [line_brw]
                else:
                    res.append((line_brw.invoice_number, line_brw.invoice_number, group_value, [line_brw]))
                    group_value = False

        if group_list:
            res.append((group_list[0].invoice_number, group_list[-1].invoice_number, group_value, group_list))

        return res

    def update_book_ntp_lines(self, fb_id):
        """ It consolidate Non-Tax Payer book lines into one line considering
        the consecutiveness and next criteria: fiscal printer and z report.
        This consolidated groups are move to another field: Non-Tax Payer
        Detail operations. (This only applys when is a sale book)
        @param fb_id: fiscal book id
        """

        fbl_obj = self.env['account.fiscal.book.line']
        fb_brw = self.browse(fb_id)

        # separating groups
        lines_brws = fb_brw.fbl_ids
        order_dict = dict()
        date_values = list(set([line_brw.emission_date for line_brw in lines_brws]))
        date_values.sort()
        order_dict = {}.fromkeys(date_values)
        for date in date_values:
            date_records = [line_brw for line_brw in lines_brws if line_brw.emission_date == date]
            printers_values = list(set([line_brw.fiscal_printer for line_brw in date_records]))
            printers_values.sort()
            order_dict[date] = {}.fromkeys(printers_values)
            for printer in printers_values:
                printer_records = [line_brw for line_brw in date_records
                                   if line_brw.fiscal_printer == printer]
                z_report_values = list(set([line_brw.z_report for line_brw in printer_records]))
                z_report_values.sort()
                order_dict[date][printer] = {}.fromkeys(z_report_values)
                for z_report in z_report_values:
                    # this records needs to be order by invoice number
                    z_records = [(line_brw.invoice_number, line_brw) for line_brw in printer_records
                                 if line_brw.z_report == z_report]
                    z_records.sort()
                    z_records = [item[1] for item in z_records]
                    # group by type of line
                    order_dict[date][printer][z_report] = self.get_grouped_consecutive_lines_ids(
                        [item.id for item in z_records])

        # import pprint
        # print 'order_dict'
        # pprint.pprint(order_dict)

        # agruping and ranking
        rank = 1
        # order_dict[date][printer][z_report] = [ ('desde', 'hasta', 'tipot',
        #                                          list(line_brws)) ]
        ntp_groups_list = list()
        # format [ ( rank, invoice_number, [line_brws] ) ]
        ntp_no_group_list = list()  # format [ ( rank, [line_brws] ) ]
        order_no_group_list = list()  # format [ ( rank, line_id ) ]

        order_dates = order_dict.keys()
        order_dates.sort()
        for date in order_dates:
            order_printers = order_dict[date].keys()
            order_printers.sort()
            for printer in order_printers:
                order_z_reports = order_dict[date][printer].keys()
                order_z_reports.sort()
                for z_report in order_z_reports:
                    for line in order_dict[date][printer][z_report]:
                        if line[2] == 'ntp':
                            if line[0] == line[1] and len(line[3]) == 1:
                                ntp_no_group_list.append(
                                    (rank, line[3][0]))
                                # (rank, line[3][0].id))
                            elif line[0] != line[1] and len(line[3]) > 1:
                                ntp_groups_list.append(
                                    (rank, 'Desde: ' + line[0] +
                                     ' ... Hasta: ' + line[1], line[3]))
                            else:
                                raise UserError("Error! \nEsta es una línea no válida. Asegúrate de tener dos o más facturas con el mismo número de factura")
                        elif line[2] != 'ntp':
                            order_no_group_list.append(
                                # (rank, line[3][0].id))
                                (rank, line[3][0]))
                        rank += 1

        # import pprint
        # print '\n ntp_no_group_list'
        # pprint.pprint(ntp_no_group_list)
        # print '\n ntp_groups_list'
        # pprint.pprint(ntp_groups_list)
        # print '\n order_no_group_list'
        # pprint.pprint(order_no_group_list)

        # ~ # rank lines that have nothing to do with ntp.
        for line in order_no_group_list:
            line[1].write({'rank': line[0]})

        # ~ # rank ntp individual lines.
        for line in ntp_no_group_list:
            line[1].write({'rank': line[0], 'partner_name': 'No Contribuyente', 'partner_vat': False})

        # create consolidate line using ntp_groups_list list, move group lines
        # to Non-Tax Payer lines detail.
        for line_tuple in ntp_groups_list:
            consolidate_line_id = self.create_consolidate_line(fb_id, line_tuple)
            for rank, line_brw in enumerate(line_tuple[-1], 1):
                line_brw.write({'fb_id': False,
                                'ntp_fb_id': fb_id,
                                'parent_id': consolidate_line_id,
                                'rank': -1})

        return True

    def create_consolidate_line(self, fb_id, line_tuple):
        """ Create a new consolidate Non-Tax Payer line for a group of no tax
        payer operations.
        @param fb_id: fiscal book line id.
        @param line_tuple: tuple with the information for construct the
                          consolidate line (rank, [brws]).
                          # format [ ( rank, invoice_number, [line_brws] ) ]
        """

        fbl_obj = self.env['account.fiscal.book.line']
        float_colums = ['total_with_iva', 'vat_sdcf', 'vat_exempt',
                        'vat_reduced_base', 'vat_reduced_tax',
                        'vat_general_base', 'vat_general_tax',
                        'vat_additional_base', 'vat_additional_tax']

        rank, invoice_number, child_brws = line_tuple
        child_ids = [line_brw.id for line_brw in child_brws]
        first_item_brw = fbl_obj.browse(child_brws[0].id)
        # fill common value
        values = {
            'rank': rank,
            'invoice_number': invoice_number,
            'child_ids': [(6, 0, child_ids)],
            # 'fb_id': first_item_brw.fb_id.id,
            'partner_name': 'No Contribuyente',
            'people_type': first_item_brw.people_type.upper() if first_item_brw.people_type else '',
            'emission_date': first_item_brw.emission_date,
            'accounting_date': first_item_brw.accounting_date,
            'doc_type': first_item_brw.doc_type,
            'type': first_item_brw.type,
            'fiscal_printer': first_item_brw.fiscal_printer,
            'z_report': False,
        }
        # fill totalization values
        for col in float_colums:
            values[col] = sum([getattr(line_brw, col) for line_brw in child_brws])

        return fbl_obj.create(values)

    def update_book_taxes_summary(self):
        """ It update the summaroty of taxes by type for this book.
        @param fb_id: fiscal book id
        """

        self.clear_book_taxes_summary()
    #    ait_obj = self.env['account.invoice.tax']
        tax_types = ['exento', 'sdcf', 'reducido', 'general', 'adicional']
        op_types = self.type == 'sale' and ['ex', 'tp', 'ntp'] or ['im', 'do']
        base_sum = {}.fromkeys(op_types)
        base =0
        amount = 0
        tax_sum = base_sum.copy()
        for op_type in op_types:
            tax_sum[op_type] = {}.fromkeys(tax_types, 0.0)
            base_sum[op_type] = {}.fromkeys(tax_types, 0.0)


        for fbl in self.fbl_ids:
            # if fbl.report_z_id:
            #     hola = 'dfdfd'
            #     if fbl.report_z_id:
            #         if float(fbl.report_z_id.base_imponible_ventas_iva_g) != 0:
            #             base = float(fbl.report_z_id.base_imponible_ventas_iva_g) - float(fbl.report_z_id.bi_iva_g_en_nota_de_credito)
            #             amount =  float(fbl.report_z_id.impuesto_iva_g) - float(fbl.report_z_id.impuesto_iva_g_en_nota_de_credito)
            #             base_sum[fbl.type]['general'] += base
            #             tax_sum[fbl.type]['general'] += amount
            #         if float(fbl.report_z_id.base_imponible_ventas_iva_r) != 0:
            #             base = float(fbl.report_z_id.base_imponible_ventas_iva_r) - float(fbl.report_z_id.bi_iva_r_en_nota_de_credito)
            #             amount = float(fbl.report_z_id.impuesto_iva_r) - float(fbl.report_z_id.impuesto_iva_r_en_nota_de_credito)
            #             base_sum[fbl.type]['reducido'] += base
            #             tax_sum[fbl.type]['reducido'] += amount
            #         if float(fbl.report_z_id.base_imponible_ventas_iva_a) != 0:
            #             base = float(fbl.report_z_id.base_imponible_ventas_iva_a) - float(fbl.report_z_id.bi_iva_a_en_nota_de_credito)
            #             amount = float(fbl.report_z_id.impuesto_iva_a) - float(fbl.report_z_id.impuesto_iva_a_en_nota_de_credito)
            #             base_sum[fbl.type]['adicional'] += base
            #             tax_sum[fbl.type]['adicional'] += amount
            #         if  float(fbl.report_z_id.ventas_exento) != 0:
            #             base = float(fbl.report_z_id.ventas_exento) - float(fbl.report_z_id.nota_de_credito_exento)
            #             base_sum[fbl.type]['exento'] += base

            if fbl.iwdl_id.invoice_id:
                sign = 1 if fbl.doc_type != 'N/CR' else -1
                for ait in fbl.iwdl_id.tax_line:
                    busq = self.env['account.tax'].search([('id', '=', ait.id_tax)])
                    if busq:
                        if busq.appl_type:
                            base_sum[fbl.type][busq.appl_type] += ait.base * sign
                            tax_sum[fbl.type][busq.appl_type] += ait.amount * sign
                        else:
                            raise UserError("Advertencia! \nEn los impuestos no se encuentra el Tipo de Alicuota por favor colocar para proceder")

            elif fbl.invoice_id and fbl.invoice_id.state != 'cancel':
                tasa = 1
                # if fbl.invoice_id.currency_id.name == "USD":
                #     tasa = self.obtener_tasa(fbl.invoice_id)
                if not fbl.invoice_id.currency_id == fbl.invoice_id.company_id.currency_id:
                    module_dual_currency = self.env['ir.module.module'].sudo().search(
                        [('name', '=', 'account_dual_currency'), ('state', '=', 'installed')])
                    if module_dual_currency:
                        tasa = fbl.invoice_id.tax_today
                    else:
                        tasa = self.obtener_tasa(fbl.invoice_id)
                sign = 1 if fbl.doc_type != 'N/CR' else -1
                for line in fbl.invoice_id.invoice_line_ids:
                    for tax in line.tax_ids:
                        busq = tax.appl_type
                        if busq:
                            if fbl.invoice_id.partner_id.people_type_company:
                                if fbl.invoice_id.partner_id.people_type_company == 'pjnd':
                                    base_sum[fbl.type][busq] += (sum(fbl.invoice_id.invoice_import_id.line_ids.mapped('debit'))/1.16) * sign
                                    #tax_sum[fbl.type][busq] += (line.price_subtotal * sign * tasa) * 0.16
                                    tax_sum[fbl.type][busq] += sum(fbl.invoice_id.invoice_import_id.line_ids.mapped('debit')) - (sum(fbl.invoice_id.invoice_import_id.line_ids.mapped('debit'))/1.16)
                                else:
                                    base_sum[fbl.type][busq] += line.price_subtotal * sign * tasa
                                    tax_sum[fbl.type][busq] += (line.price_total - line.price_subtotal) * sign * tasa
                            else:
                                base_sum[fbl.type][busq] += line.price_subtotal * sign * tasa
                                tax_sum[fbl.type][busq] += (line.price_total - line.price_subtotal) * sign * tasa
                        else:
                            raise UserError("Advertencia! \nEn los impuestos no se encuentra el Tipo de Alicuota por favor colocar para proceder")




        data = [(0, 0, {'tax_type': ttype, 'op_type': optype,
                        'base_amount_sum': base_sum[optype][ttype],
                        'tax_amount_sum': tax_sum[optype][ttype]
                        })
                for ttype in tax_types
                for optype in op_types
                ]
        return data and self.write({'fbts_ids': data})

    def update_book_taxes_amount_fields(self):
        """ It update the base_amount and the tax_amount field for book, and
        extract data from the book tax summary to store fields inside the
        book model.
        @param fb_id: fiscal book id
        """
  #      ait_obj = self.env['account.invoice.tax']
        data = {}
        # totalization of book tax amount and base amount fields
        tax_amount = 0.0
        base_amount = 0.0
        for fbl_brw in self.fbl_ids:
            sign = 1 if fbl_brw.doc_type != 'N/CR' else -1

            # if fbl_brw.report_z_id:
            #     if float(fbl_brw.report_z_id.base_imponible_ventas_iva_g) != 0:
            #         base = float(fbl_brw.report_z_id.base_imponible_ventas_iva_g) - float(fbl_brw.report_z_id.bi_iva_g_en_nota_de_credito)
            #         amount = float(fbl_brw.report_z_id.impuesto_iva_g) - float(fbl_brw.report_z_id.impuesto_iva_g_en_nota_de_credito)
            #         base_amount += base
            #         tax_amount += amount



            if fbl_brw.iwdl_id.invoice_id:
                for ait in fbl_brw.iwdl_id.tax_line:
                    base_amount += ait.base * sign
                    tax_amount += ait.amount * sign
            if fbl_brw.invoice_id and fbl_brw.invoice_id.state != 'cancel':
                tasa = 1
                if not fbl_brw.invoice_id.currency_id == fbl_brw.invoice_id.company_id.currency_id:
                    module_dual_currency = self.env['ir.module.module'].sudo().search(
                        [('name', '=', 'account_dual_currency'), ('state', '=', 'installed')])
                    if module_dual_currency:
                        tasa = fbl_brw.invoice_id.tax_today
                    else:
                        tasa = self.obtener_tasa(fbl_brw.invoice_id)
                # if fbl_brw.invoice_id.currency_id.name == "USD":
                #     tasa = self.obtener_tasa(fbl_brw.invoice_id)
                for line in fbl_brw.invoice_id.invoice_line_ids:
                    base_amount += line.price_subtotal * sign * tasa
                    tax_amount += (line.price_total-line.price_subtotal) * sign * tasa

        data['tax_amount'] = tax_amount
        data['base_amount'] = base_amount

        # totalization of book taxable and taxed amount for every tax type and
        # operation type
        vat_fields = [
            'imex_exempt_vat_sum',
            'imex_sdcf_vat_sum',
            'imex_general_vat_base_sum',
            'imex_general_vat_tax_sum',
            'imex_additional_vat_base_sum',
            'imex_additional_vat_tax_sum',
            'imex_reduced_vat_base_sum',
            'imex_reduced_vat_tax_sum',
            'do_exempt_vat_sum',
            'do_sdcf_vat_sum',
            'do_general_vat_base_sum',
            'do_general_vat_tax_sum',
            'do_additional_vat_base_sum',
            'do_additional_vat_tax_sum',
            'do_reduced_vat_base_sum',
            'do_reduced_vat_tax_sum',
            'tp_exempt_vat_sum',
            'tp_sdcf_vat_sum',
            'tp_general_vat_base_sum',
            'tp_general_vat_tax_sum',
            'tp_additional_vat_base_sum',
            'tp_additional_vat_tax_sum',
            'tp_reduced_vat_base_sum',
            'tp_reduced_vat_tax_sum',
            'ntp_exempt_vat_sum',
            'ntp_sdcf_vat_sum',
            'ntp_general_vat_base_sum',
            'ntp_general_vat_tax_sum',
            'ntp_additional_vat_base_sum',
            'ntp_additional_vat_tax_sum',
            'ntp_reduced_vat_base_sum',
            'ntp_reduced_vat_tax_sum',
        ]
        for field_name in vat_fields:
            data[field_name] = self.update_vat_fields(field_name)

        # more complex totalization amounts.
        # fb_brw = self.browse( fb_id)

        data['do_sdcf_and_exempt_sum'] = self.type == 'sale' \
                                         and (data['tp_exempt_vat_sum'] + data['tp_sdcf_vat_sum'] +
                                              data['ntp_exempt_vat_sum'] + data['ntp_sdcf_vat_sum']) \
                                         or (data['do_exempt_vat_sum'] + data['do_sdcf_vat_sum'])

        for optype in ['imex', 'do', 'tp', 'ntp']:
            data[optype + '_vat_base_sum'] = sum([data[optype + '_' + ttax + "_vat_base_sum"]
                                                  for ttax in ["general", "additional", "reduced"]])

        data['imex_vat_base_sum'] += data['imex_exempt_vat_sum'] + data['imex_sdcf_vat_sum']

        # sale book domestic fields transformations (ntp and tp sums)
        if self.type == 'sale':
            data["do_vat_base_sum"] = data["tp_vat_base_sum"] + data["ntp_vat_base_sum"]

            for ttax in ["general", "additional", "reduced"]:
                for amttype in ["base", "tax"]:
                    data['do_' + ttax + '_vat_' + amttype + '_sum'] = sum(
                        [data[optype + "_" + ttax + "_vat_" + amttype + "_sum"]
                         for optype in ["ntp", "tp"]])
            for ttax in ["exempt", "sdcf"]:
                data['do_' + ttax + '_vat_sum'] = \
                    sum([data[optype + "_" + ttax + "_vat_sum"]
                         for optype in ["ntp", "tp"]
                         ])

        return self.write(data)

    def update_vat_fields(self, field_name):
        """ It returns summation of a fiscal book tax column (Using
        account.fiscal.book.taxes.summary).

        """

        res = 0.0
        fbts_obj = self.env['account.fiscal.book.taxes.summary']

        # Identifying the field
        field_info = field_name[:-4].split('_')
        field_info.remove('vat')

        field_op, field_tax, field_amount = (len(field_info) == 3) \
                                            and field_info \
                                            or field_info + ['base']

        # Translation between the fb fields names and the fbts records data.
        tax_type = {'exempt': 'exento', 'sdcf': 'sdcf', 'reduced': 'reducido',
                    'general': 'general', 'additional': 'adicional'}
        amount_type = {'base': 'base_amount_sum', 'tax': 'tax_amount_sum'}


        for fbts_brw in self.fbts_ids:

            if fbts_brw.tax_type == tax_type[field_tax]:
                res = getattr(fbts_brw, amount_type[field_amount])
        return res

    def link_book_lines_and_taxes(self, fb_id):
        """ Updates the fiscal book taxes. Link the tax with the corresponding
        book line and update the fields of sum taxes in the book.
        @param fb_id: the id of the current fiscal book """

        #        fbl_obj = self.env['account.fiscal.book.line']
 #       ait_obj = self.env['account.invoice.tax']
        ut_obj = self.env['account.ut']
        fbt_obj = self.env['account.fiscal.book.taxes']
        # write book taxes
        data = []
        tax_data = {}
        exento = 0.0
        base_exento = 0
        amount = 0
        name = ' '
        base = 0
        fiscal_book = self.browse(fb_id)
        for fbl in fiscal_book.fbl_ids:
            # if fbl.report_z_id:
            #     fiscal_taxes = self.env['account.fiscal.book.taxes']
            #     line_taxes = {'fb_id': fb_id, 'fbl_id': fbl.id, 'base_amount': 0.0, 'tax_amount': 0.0, 'name': ' ', 'exento':0 }
            #     sum_base_imponible = 0
            #     amount_field_data = {'total_with_iva':
            #                              0.0,
            #                          'vat_sdcf': 0.0, 'vat_exempt': 0.0, 'vat_general_base': 0.0, }
            #
            #
            #     if float(fbl.report_z_id.base_imponible_ventas_iva_g) != 0:
            #         base = float(fbl.report_z_id.base_imponible_ventas_iva_g) - float(fbl.report_z_id.bi_iva_g_en_nota_de_credito)
            #         amount = float(fbl.report_z_id.impuesto_iva_g) - float(fbl.report_z_id.impuesto_iva_g_en_nota_de_credito)
            #         name = 'IVA 16%'
            #     if float(fbl.report_z_id.ventas_exento) != 0:
            #         amount_field_data['vat_exempt'] += float(fbl.report_z_id.ventas_exento) - float(fbl.report_z_id.nota_de_credito_exento)
            #         base_exento = float(fbl.report_z_id.ventas_exento) - float(fbl.report_z_id.nota_de_credito_exento)
            #
            #
            #     if float(fbl.report_z_id.base_imponible_ventas_iva_r) != 0:
            #         base = float(fbl.report_z_id.base_imponible_ventas_iva_r) - float(fbl.report_z_id.bi_iva_r_en_nota_de_credito)
            #         amount = float(fbl.report_z_id.impuesto_iva_r) - float(fbl.report_z_id.impuesto_iva_r_en_nota_de_credito)
            #         name = 'IVA 8%'
            #     if float(fbl.report_z_id.base_imponible_ventas_iva_a) != 0:
            #         base = float(fbl.report_z_id.base_imponible_ventas_iva_a) - float(fbl.report_z_id.bi_iva_a_en_nota_de_credito)
            #         amount = float(fbl.report_z_id.impuesto_iva_a) - float(fbl.report_z_id.impuesto_iva_a_en_nota_de_credito)
            #         name = 'IVA 31%'
            #     amount_field_data['total_with_iva'] += (amount + base)
            #
            #     amount_field_data['vat_general_base'] += base
            #
            #
            #     line_taxes.update({'fb_id': fb_id,
            #                        'fbl_id': fbl.id,
            #                        'base_amount': amount_field_data['vat_general_base'],
            #                        'tax_amount': amount,
            #                        'name': name,
            #                        'exento': base_exento,
            #                        'type': fiscal_book.type})
            #
            #     fbl.write(amount_field_data)
            #
            #     if line_taxes:
            #         fiscal_taxes.create(line_taxes)
            #
            #     else:
            #         data.append((0, 0, {'fb_id': fb_id,
            #                             'fbl_id': fbl.id,
            #
            #                             }))
            #         self.write({'fbt_ids': data})
            #     amount = base = base_exento = 0
            #     name = ' '
            ####################################### antes es report z#########################

            if fbl.iwdl_id.invoice_id:

                fiscal_taxes = self.env['account.fiscal.book.taxes']
                line_taxes = {'fb_id': fb_id, 'fbl_id': fbl.id, 'base_amount': 0.0, 'tax_amount': 0.0, 'name': ' ', }
                fiscal_book = self.browse(fb_id)
                f_xc = ut_obj.sxc(
                    fbl.iwdl_id.invoice_id.currency_id.id,
                    fbl.iwdl_id.invoice_id.company_id.currency_id.id,
                    fbl.iwdl_id.invoice_id.invoice_date)
                if fbl.doc_type == 'N/CR' :
                    sign = -1
                else:
                    sign = 1
                sum_base_imponible = 0
                amount_field_data = {'total_with_iva':
                                        0.0,
                                     'vat_sdcf': 0.0, 'vat_exempt': 0.0, 'vat_general_base': 0.0,}

                for ait in fbl.iwdl_id.tax_line:
                    busq = self.env['account.tax'].search([('id', '=', ait.id_tax)])
                    if busq:
                        if ait.amount == 0:
                            base = ait.base
                            name = ait.name
                            amount_field_data['vat_exempt'] += exento * sign
                            if fbl.iwdl_id.invoice_id.partner_id.people_type_company:
                                if fbl.iwdl_id.invoice_id.partner_id.people_type_company == 'pjnd':
                                    amount = 16
                        else:
                            base = ait.base
                            amount = ait.amount
                            name = ait.name
                        if (ait.amount + ait.base) > 0:
                            amount_field_data['total_with_iva'] += (ait.amount + ait.base)* sign
                            if busq.appl_type == 'sdcf':
                                    amount_field_data['vat_sdcf'] += base * sign
                            if busq.appl_type == 'exento':
                                amount_field_data['vat_exempt'] += base * sign
                            if busq.appl_type == 'general':
                                amount_field_data['vat_general_base'] += base * sign

                        tax_data.update({'fb_id': fb_id,
                                         'fbl_id': fbl.id,
                                        # 'ait_id': busq.id,
                                         'base_amount': amount_field_data['vat_general_base'],
                                         'tax_amount': ait.amount})

                        line_taxes.update({'fb_id': fb_id,
                                           'fbl_id': fbl.id,
                                           'base_amount':  base,
                                           'tax_amount': amount,
                                           'name': name,
                                           'type': fiscal_book.type

                                           })
                    fbl.write(amount_field_data)
                    if line_taxes:
                        fiscal_taxes.create(line_taxes)
                    else:
                        data.append((0, 0, {'fb_id': fb_id,
                                            'fbl_id': fbl.id,

                                            }))
                        self.write({'fbt_ids': data})


            if fbl.invoice_id and fbl.invoice_id.state != 'cancel':
                tasa = 1
                print('Pasa por aqui 2 en carga de facturas')
                if not fbl.invoice_id.currency_id == fbl.invoice_id.company_id.currency_id:
                    module_dual_currency = self.env['ir.module.module'].sudo().search(
                        [('name', '=', 'account_dual_currency'), ('state', '=', 'installed')])
                    if module_dual_currency:
                        tasa = fbl.invoice_id.tax_today
                    else:
                        tasa = self.obtener_tasa(fbl.invoice_id)
                fiscal_book = self.browse(fb_id)
                fiscal_taxes = self.env['account.fiscal.book.taxes']
                line_taxes = {'fb_id': fb_id, 'fbl_id': fbl.id,'base_amount': 0.0 , 'tax_amount': 0.0, 'name': ' ',}
                f_xc = ut_obj.sxc(
                    fbl.invoice_id.currency_id.id,
                    fbl.invoice_id.company_id.currency_id.id,
                    fbl.invoice_id.invoice_date)
                busq = ' '
                if fbl.doc_type == 'N/CR':
                    sign = -1
                else:
                    sign = 1
                sum_base_imponible = 0
                amount_field_data = {'total_with_iva':
                                         0.0,
                                     'vat_sdcf': 0.0, 'vat_exempt': 0.0, 'vat_general_base': 0.0, }

                if fbl.invoice_id.partner_id.people_type_company == 'pjnd' and fbl.invoice_id.invoice_import_id:
                    base = (sum(fbl.invoice_id.invoice_import_id.line_ids.mapped('debit'))/1.16)
                    amount = sum(fbl.invoice_id.invoice_import_id.line_ids.mapped('debit')) - (sum(fbl.invoice_id.invoice_import_id.line_ids.mapped('debit'))/1.16)
                    tax_data.update({'fb_id': fb_id,
                                     'fbl_id': fbl.id,
                                     #     'ait_id': fbl.id,
                                     'base_amount': base,
                                     'tax_amount': amount})
                    line_taxes.update({'fb_id': fb_id,
                                       'fbl_id': fbl.id,
                                       'base_amount': base,
                                       'tax_amount': amount,
                                       'name': 'IVA (16.0%) compras',
                                       'type': fiscal_book.type

                                       })
                    fiscal_taxes.create(line_taxes)
                    amount_field_data['vat_general_base'] = base * sign
                    amount_field_data['total_with_iva'] = (base + amount) * sign
                    fbl.write(amount_field_data)
                else:
                    for line in fbl.invoice_id.invoice_line_ids:
                        amount = 0
                        base = 0
                        busq =  ''
                        tax = ' '

                        for tax in line.tax_ids:
                            busq = tax.appl_type
                            name = tax.name
                        if busq:
                            if (line.price_total - line.price_subtotal) == 0:
                                base = line.price_subtotal * tasa
                                amount = 0
                                amount_field_data['vat_exempt'] += exento * sign
                                if fbl.invoice_id.partner_id.people_type_company:
                                    if fbl.invoice_id.partner_id.people_type_company == 'pjnd':
                                        amount = line.price_subtotal * tasa * 0.16
                            else:
                                base = (line.price_subtotal) * tasa
                                amount = (line.price_total - line.price_subtotal) * tasa

                            if ((line.price_total - line.price_subtotal) == 0 or (line.price_total - line.price_subtotal) > 0) and line.price_total > 0:
                                if fbl.invoice_id.partner_id.people_type_company:
                                    if fbl.invoice_id.partner_id.people_type_company == 'pjnd':
                                        amount_field_data['total_with_iva'] += (line.price_total * sign * tasa) * 1.16
                                    else:
                                        amount_field_data['total_with_iva'] += line.price_total * sign * tasa
                                else:
                                    amount_field_data['total_with_iva'] += line.price_total * sign * tasa
                                if busq == 'sdcf':
                                    amount_field_data['vat_sdcf'] += base * sign
                                if busq == 'exento':
                                    amount_field_data['vat_exempt'] += base * sign
                                if busq == 'general':
                                    amount_field_data['vat_general_base'] += base * sign

                            tax_data.update({'fb_id': fb_id,
                                             'fbl_id': fbl.id,
                                        #     'ait_id': fbl.id,
                                             'base_amount': base,
                                             'tax_amount': amount})

                            line_taxes.update({'fb_id': fb_id,
                                               'fbl_id': fbl.id,
                                               'base_amount': base,
                                               'tax_amount':amount,
                                               'name': name,
                                               'type': fiscal_book.type

                            })

                        fbl.write(amount_field_data)
                        if line_taxes:
                            fiscal_taxes.create(line_taxes)
                        else:
                            data.append((0, 0, {'fb_id': fb_id,
                                                'fbl_id': fbl.id,

                                                }))
                            self.write({'fbt_ids': data})

            # Handle cancelled invoices - set all values to 0
            if fbl.invoice_id and fbl.invoice_id.state == 'cancel':
                amount_field_data = {
                    'total_with_iva': 0.0,
                    'vat_sdcf': 0.0, 
                    'vat_exempt': 0.0, 
                    'vat_general_base': 0.0,
                    'vat_general_tax': 0.0,
                    'vat_reduced_base': 0.0,
                    'vat_reduced_tax': 0.0,
                    'vat_additional_base': 0.0,
                    'vat_additional_tax': 0.0,
                }
                fbl.write(amount_field_data)

        self.update_book_taxes_summary()
        self.update_book_lines_taxes_fields()
        self.update_book_taxes_amount_fields()
        return True

    def update_book_lines_taxes_fields(self):
        """ Update taxes data for every line in the fiscal book given,
        extrating de data from the fiscal book taxes associated.
        @param fb_id: fiscal book line id.
        """
        tax_amount = 0
        fbl_obj = self.env['account.fiscal.book.line']
        field_names = ['vat_reduced_base', 'vat_reduced_tax',
                       'vat_general_base', 'vat_general_tax',
                       'vat_additional_base', 'vat_additional_tax']
        tax_type = {'reduced': 'reducido', 'general': 'general',
                    'additional': 'adicional'}
        for fbl_brw in self.fbl_ids:
            if fbl_brw.doc_type == 'N/CR':
                sign = -1
            else:
                sign = 1
            data = {}.fromkeys(field_names, 0.0)
            busq = ' '
            # if fbl_brw.report_z_id:
            #
            #     for field_name in field_names:
            #         field_tax, field_amount = field_name[4:].split('_')
            #
            #         if field_tax == 'general' and (field_amount == 'base' or field_amount == 'tax'):
            #             if float(fbl_brw.report_z_id.base_imponible_ventas_iva_g) != 0:
            #                 base = float(fbl_brw.report_z_id.base_imponible_ventas_iva_g) - float(fbl_brw.report_z_id.bi_iva_g_en_nota_de_credito)
            #                 tax_amount = float(fbl_brw.report_z_id.impuesto_iva_g) - float(fbl_brw.report_z_id.impuesto_iva_g_en_nota_de_credito)
            #                 data[field_name] += field_amount == 'base' and base \
            #                                 or tax_amount
            #         if field_tax  == 'reduced' and (field_amount == 'base' or field_amount == 'tax'):
            #             if float(fbl_brw.report_z_id.base_imponible_ventas_iva_r) != 0:
            #                 base = float(fbl_brw.report_z_id.base_imponible_ventas_iva_r) - float(fbl_brw.report_z_id.bi_iva_r_en_nota_de_credito)
            #                 tax_amount = float(fbl_brw.report_z_id.impuesto_iva_r) - float(fbl_brw.report_z_id.impuesto_iva_r_en_nota_de_credito)
            #                 data[field_name] += field_amount == 'base' and base \
            #                                     or tax_amount
            #         if field_tax == 'additional' and (field_amount == 'base' or field_amount == 'tax'):
            #             if float(fbl_brw.report_z_id.base_imponible_ventas_iva_a) != 0:
            #                 base = float(fbl_brw.report_z_id.base_imponible_ventas_iva_a) - float(fbl_brw.report_z_id.bi_iva_a_en_nota_de_credito)
            #                 tax_amount = float(fbl_brw.report_z_id.impuesto_iva_a) - float(fbl_brw.report_z_id.impuesto_iva_a_en_nota_de_credito)
            #                 data[field_name] += field_amount == 'base' and base \
            #                                     or tax_amount
            #     fbl_brw.write(data)

            if fbl_brw.iwdl_id.invoice_id:

               for line in fbl_brw.iwdl_id.invoice_id.invoice_line_ids:
                   for tax in line.tax_ids:
                       busq = tax.appl_type
                   tasa = 1
                   if not line.currency_id == line.move_id.company_id.currency_id:
                       module_dual_currency = self.env['ir.module.module'].sudo().search(
                           [('name', '=', 'account_dual_currency'), ('state', '=', 'installed')])
                       if module_dual_currency:
                           tasa = line.move_id.tax_today
                       else:
                           tasa = self.obtener_tasa(line)
                   # if line.currency_id.name == "USD":
                   #     tasa = self.obtener_tasa(line)
                   for field_name in field_names:
                        field_tax, field_amount = field_name[4:].split('_')
                        base = line.price_subtotal * tasa
                        tax_amount = (line.price_total - line.price_subtotal) * tasa
                        if fbl_brw.iwdl_id.invoice_id.partner_id.people_type_company:
                            if fbl_brw.iwdl_id.invoice_id.partner_id.people_type_company == 'pjnd':
                                tax_amount = line.price_subtotal * tasa * 0.16
                        if busq:
                            if busq == tax_type[field_tax]:
                                    data[field_name] += field_amount == 'base' and base * sign \
                                                        or tax_amount * sign
               fbl_brw.write(data)

            if fbl_brw.invoice_id and fbl_brw.invoice_id.state != 'cancel':
                tasa = 1
                if not fbl_brw.invoice_id.currency_id == fbl_brw.invoice_id.company_id.currency_id:
                    module_dual_currency = self.env['ir.module.module'].sudo().search(
                        [('name', '=', 'account_dual_currency'), ('state', '=', 'installed')])
                    if module_dual_currency:
                        tasa = fbl_brw.invoice_id.tax_today
                    else:
                        tasa = self.obtener_tasa(fbl_brw.invoice_id)
                if fbl_brw.invoice_id.partner_id.people_type_company == 'pjnd' and fbl_brw.invoice_id.invoice_import_id:
                    #cargar datos de la factura importacion nuvo metodo
                    data['vat_general_base'] = (sum(fbl_brw.invoice_id.invoice_import_id.line_ids.mapped('debit'))/1.16)
                    data['vat_general_tax'] = sum(fbl_brw.invoice_id.invoice_import_id.line_ids.mapped('debit')) - (sum(fbl_brw.invoice_id.invoice_import_id.line_ids.mapped('debit'))/1.16)
                else:
                    for line in fbl_brw.invoice_id.invoice_line_ids:
                        for tax in line.tax_ids:
                            busq = tax.appl_type
                        for field_name in field_names:
                            field_tax, field_amount = field_name[4:].split('_')
                            base = line.price_subtotal * tasa
                            tax_amount = (line.price_total - line.price_subtotal) * tasa
                            if fbl_brw.invoice_id.partner_id.people_type_company:
                                if fbl_brw.invoice_id.partner_id.people_type_company == 'pjnd':
                                    tax_amount = line.price_total * tasa * 0.16
                            if busq:
                                if busq == tax_type[field_tax]:  # account.tax
                                    # if not fbt_brw.fbl_id.iwdl_id.invoice_id.name: #facura de account.wh.iva.line
                                    #     data[field_name] += field_amount == 'base' and (
                                    #         fbt_brw.fbl_id.invoice_id.factura_id.amount_gravable if fbt_brw.base_amount == 0 else fbt_brw.base_amount) * sign \
                                    #                         or fbt_brw.tax_amount * sign
                                    # else:
                                    data[field_name] += field_amount == 'base' and base * sign \
                                                        or tax_amount * sign

                fbl_brw.write(data)
        return True

    # clear book methods

    
    def clear_book(self):
        """ It delete all book data information.
        @param fb_id: fiscal book line id
        """
        self.clear_book_taxes_amount_fields()
        # delete data
        self.clear_book_lines()
        self.clear_book_taxes()
        self.clear_book_taxes_summary()
        # unrelate data
        self.clear_book_invoices()
        self.clear_book_issue_invoices()  # <--- ¡¡AQUÍ ESTÁ EL ERROR!!
        self.clear_book_iwdl_ids()

    def clear_book_lines(self):
        """ It delete all book lines loaded in the book """
        for fbl in self.fbl_ids:
            fbl.unlink()
        # self.clear_book_taxes_amount_fields()
        return True

    
    def clear_book_taxes(self):
        """ It delete all book taxes loaded in the book """
        for fbt in self.fbt_ids:
            fbt.unlink()
        # self.clear_book_taxes_amount_fields()
        return

    
    def clear_book_taxes_summary(self):
        """ It delete fiscal book taxes summary data for the book """
        # context = self.env.context and {k:v for k,v in self.env.context.items()} or {}
        # cr = self.env.cr
        # ids = self.ids
        # uid = self.env.uid
        fbts_obj = self.env['account.fiscal.book.taxes.summary']
        # fb_id = isinstance(fb_id, (int, long)) and [fb_id] or fb_id
        fbts_ids = fbts_obj.search([('fb_id', 'in', [self.id])])
        # fbts_obj.unlink(fbts_ids)
        for fbts in fbts_ids:
            # if fbts_ids:
            fbts.unlink()
        return

    
    def clear_book_taxes_amount_fields(self):
        # def clear_book_taxes_amount_fields(self,  fb_id):
        """ Clean amount taxes fields in fiscal book """
        vat_fields = [
            'tax_amount',
            'base_amount',
            'imex_vat_base_sum',
            'imex_exempt_vat_sum',
            'imex_sdcf_vat_sum',
            'imex_general_vat_base_sum',
            'imex_general_vat_tax_sum',
            'imex_additional_vat_base_sum',
            'imex_additional_vat_tax_sum',
            'imex_reduced_vat_base_sum',
            'imex_reduced_vat_tax_sum',
            'do_vat_base_sum',
            'do_exempt_vat_sum',
            'do_sdcf_vat_sum',
            'do_general_vat_base_sum',
            'do_general_vat_tax_sum',
            'do_additional_vat_base_sum',
            'do_additional_vat_tax_sum',
            'do_reduced_vat_base_sum',
            'do_reduced_vat_tax_sum',
            'tp_vat_base_sum',
            'tp_exempt_vat_sum',
            'tp_sdcf_vat_sum',
            'tp_general_vat_base_sum',
            'tp_general_vat_tax_sum',
            'tp_additional_vat_base_sum',
            'tp_additional_vat_tax_sum',
            'tp_reduced_vat_base_sum',
            'tp_reduced_vat_tax_sum',
            'ntp_vat_base_sum',
            'ntp_exempt_vat_sum',
            'ntp_sdcf_vat_sum',
            'ntp_general_vat_base_sum',
            'ntp_general_vat_tax_sum',
            'ntp_additional_vat_base_sum',
            'ntp_additional_vat_tax_sum',
            'ntp_reduced_vat_base_sum',
            'ntp_reduced_vat_tax_sum',
        ]

        # return self.write( fb_id, {}.fromkeys(vat_fields, 0.0))
        return self.write({}.fromkeys(vat_fields, 0.0))

    
    def clear_book_invoices(self):
        """ Unrelate all invoices of the book. And delete fiscal book taxes """
        self.clear_book_taxes()
        for inv in self.invoice_ids:
            inv.write({'fb_id': False})
        return True

    
    def clear_book_issue_invoices(self):
        """ Unrelate all issue invoices of the book """
        for is_inv in self.issue_invoice_ids:
            is_inv.write({'issue_fb_id': False})
        return True


    
    def clear_book_iwdl_ids(self):
        """ Unrelate all wh iva lines of the book. """
        for iwdl in self.iwdl_ids:
            iwdl.write({'fb_id': False})
        return True

    def get_doc_type(self, inv_id=None, iwdl_id=None, cf_id=None):
        """ Returns a string that indicates de document type. For withholding
        returns 'AJST' and for invoice docuemnts returns different values
        depending of the invoice type: Debit Note 'N/DB', Credit Note 'N/CR',
        Invoice 'FACT'.
        @param inv_id : invoice id
        @param iwdl_id: wh iva line id
        """

        res = False
        # if fb_id:
        #    obj_fb = self.env['account.fiscal.book']
        #    fb_brw = obj_fb.browse( fb_id)
        if inv_id:
            inv_obj = self.env['account.move']
            inv_brw = inv_obj.browse(inv_id)
            if inv_brw.move_type in ["in_invoice", "out_invoice"]:
                if inv_brw.debit_origin_id :
                    res = "N/DB"
                else:
                    res = "FACT"
            elif inv_brw.move_type in ["out_refund", "in_refund"]:
                res = "N/CR"


            assert res, str(inv_brw) + ": Error in the definition \
                of the document type. \n There is not type category definied for \
                your invoice."
        elif iwdl_id:
            res = 'AJST' if self.type == 'sale' else 'RET'
        # TODO CONDICION RELACIONADO CON ELMODELO customs.form DEL MODULO l10n_ve_imex
        #        elif cf_id:
        #            res = 'F/IMP'

        return res

    def get_invoice_import_form(self, inv_id):
        """ Returns the Invoice reference
        @param inv_id: invoice id
        """

        inv_obj = self.env['account.move']
        inv_brw = inv_obj.browse(inv_id)
        return inv_brw.reference or False



    # TODO FUNCION RELACIONADO CON MODULO l10n_ve_imex (importaciones)
    def get_transaction_type(self, fb_id, inv_id):
        """ Method that returns the type of the fiscal book line related to the
        given invoice by cheking the customs form associated and the fiscal
        book type.
        @param fb_id: fiscal book id
        @param inv_id: invoice id
        """

        inv_obj = self.env['account.move']
        inv_brw = inv_obj.browse(inv_id)
        fb_brw = self.browse(fb_id)
        # TODO VALOR RELACIONADO CON MODULO l10n_ve_imex (importaciones)
        # if inv_brw.customs_form_id:
        #    return 'ex' if fb_brw.type == 'sale' else 'im'
        # else:
        if fb_brw.type == 'purchase':
            t = 'do'
            if not inv_brw.partner_id.country_id == self.env.ref('base.ve'):
                t = 'im'
            return t
        else:
            return 'tp' if inv_brw.partner_id.vat_subjected else 'ntp'

    
    def unlink(self):
        """ Overwrite the unlink method to throw an exception if the book is
        not in cancel state."""
        
        for fb_brw in self.browse(self.ids):
            if fb_brw.state != 'cancel':
                raise UserError(_("Invalid Procedure!! \nYour book needs to be in cancel state to be deleted."))
            else:
                res = super(AccountFiscalBook, self).unlink()
        return res

    def obtener_tasa(self, invoice):
        fecha = invoice.date
        tasa_id = invoice.currency_id
        tasa = self.env['res.currency.rate'].search([('currency_id', '=', tasa_id.id), ('name', '<=', fecha)],
                                                 order='id desc', limit=1)
        if not tasa:
            raise UserError("Advertencia! \nNo hay referencia de tasas registradas para moneda USD en la fecha igual o inferior de la factura %s" % (invoice.name))
        return 1 / tasa.rate


class AccountFiscalBookLines(models.Model):
    TYPE = [('im', 'Imports'),
            ('do', 'Domestic'),
            ('ex', 'Exports'),
            ('tp', 'Tax Payer'),
            ('ntp', 'Non-Tax Payer')]

    
    def _get_wh_vat(self, fb_id):
        """ For a given book line it returns the vat withholding amount.
        """

        res = {}.fromkeys(self._ids, 0.0)
        for fbl_brw in self.search([('fb_id', '=', fb_id)]):
            sign = 1 if fbl_brw.doc_type != 'AJST' else -1
            if fbl_brw.iwdl_id:
                res[fbl_brw.id] = fbl_brw.iwdl_id.total_tax_ret * sign
        return res

    @api.model
    def _get_based_tax_debit(self):
        """ It Returns the sum of all tax amount for the taxes realeted to the
        wh iva line.
        @param field_name: ['get_based_tax_debit'].
        """
        # TODO: for all taxes realted? only a tax type group?

        res = {}.fromkeys(self._ids, 0.0)

        for fbl_brw in self.browse():
            if fbl_brw.create_date != False:
                if fbl_brw.iwdl_id:
                    sign = 1 if fbl_brw.doc_type != 'AJST' else -1
                    for tax in fbl_brw.iwdl_id.tax_line:
                        res[fbl_brw.id] += tax.amount * sign
        return res

    def _compute_vat_rates(self, ids, field_name, arg):
        res = {}
        for item in self.browse(ids):
            res[item.id] = {
                'vat_reduced_rate': item.vat_reduced_base and
                                    item.vat_reduced_tax * 100 / item.vat_reduced_base,
                'vat_general_rate': item.vat_general_base and
                                    item.vat_general_tax * 100 / item.vat_general_base,
                'vat_additional_rate': item.vat_additional_base and
                                       item.vat_additional_tax * 100 / item.vat_additional_base,
            }
        return res


    _description = "Venta y compra de líneas de libros fiscales en Venezuela"
    _name = 'account.fiscal.book.line'
    _rec_name = 'rank'
    _order = 'accounting_date asc'

    numero_debit_credit = fields.Char()
    base = fields.Float('base')
    amount =fields.Float('amount')
    name = fields.Char("Líneas de libros fiscales")
    fb_id = fields.Many2one('account.fiscal.book', 'Fiscal Book',
                            help='Libro fiscal que posee esta línea de libro', ondelete='cascade', index=True)
    ntp_fb_id = fields.Many2one("account.fiscal.book", "Detalle no contribuyente",
                                help="Detalle no contribuyente"
                                     " Este libro es solo para líneas que no pagan impuestos")
    fbt_ids = fields.One2many('account.fiscal.book.taxes', 'fbl_id', string='Lineas de impuestos',
                              help="Líneas fiscales que se registran en un libro fiscal")
    invoice_id = fields.Many2one('account.move', 'Factura',
                                 help="Factura relacionada con esta línea de libro")
    iwdl_id = fields.Many2one('account.wh.iva.line', 'Retencion de IVA',
                              help="Retención de la línea iva relacionada con esta línea del libro")
    #report_z_id = fields.Many2one('datos.zeta.diario', 'reportes z ids')
    n_ultima_factZ = fields.Char('Numero de Ultima Factura')
    # TODO CAMPO RELACIONADO CON EL MODELO customs.form DEL MODULO l10n_ve_imex
    # cf_id = fields.Many2one('customs.form', 'Customs Form',
    #        help="Customs Form being recorded to this book line")
    parent_id = fields.Many2one("account.fiscal.book.line", string="Linea consolidada",
                                ondelete='cascade', help="Línea consolidada no contribuyente. Indique la identificación de la"
                                                         "línea consolidada a la que pertenece esta línea de contribuyente")
    parent_left = fields.Integer('Padre izquierdo', select=1)
    parent_right = fields.Integer('Padre Derecho', select=1)
    child_ids = fields.One2many("account.fiscal.book.line", "parent_id", string="Línea de detalle para no contribuyentes",
                                help="Grupo no contribuyente de líneas de libros que representa esta línea")

    #  Invoice and/or Document Data
    rank = fields.Integer("Line", required=True, default=0, help="Line Position")
    emission_date = fields.Date(string='Fecha de emisión', help='Fecha del documento de factura / Fecha del comprobante de línea de IVA')
    accounting_date = fields.Date(string='Fecha Contable',
                                  help="El día del registro contable [(factura, fecha de factura), "
                                       "(línea de retencion de IVA, Fecha de retencion)]")
    doc_type = fields.Char('Tipo de Documento', size=9, help='Tipo de Documento')
    partner_name = fields.Char(size=128, string='Nombre de la Empresa', help='')
    people_type = fields.Char(string='Tipo de Persona', help='')
    partner_vat = fields.Char(size=128, string='Nro. RIF', help='')
    affected_invoice = fields.Char(string='Factura Afectada', size=64,
                                   help="Para un tipo de línea de factura significa factura principal para un Débito "
                                        "o Nota de crédito. Para un tipo de línea de retención se entiende la factura"
                                        "número relacionado con la retención")
    # Apply for wh iva lines
    get_wh_vat = fields.Float(string="Retención de IVA", help="Retención de IVA")
    wh_number = fields.Char(string='Nro de  Comprobante de Retención', size=64, help="")
    wh_date = fields.Date(string='Fecha de Comprobante', help='Fecha del documento de factura / Fecha del comprobante de línea de IVA')
    affected_invoice_date = fields.Date(string="Fecha de factura Afectada", help="")
    wh_rate = fields.Float(string="Porcentaje de retención", help="")
    get_wh_debit_credit = fields.Float(compute='_get_based_tax_debit',
                                        store=True,
                                       string="Base Debito Fiscal",
                                       help="Suma de toda la cantidad de impuestos para los impuestos relacionados con la línea de retencion de IVA")

    # Apply for invoice lines
    ctrl_number = fields.Char(string='Nro de Control de Factura', size=64, help='')
    invoice_number = fields.Char(string='Nro de Factura', size=64, help='')
    # TODO chequear la necesidad de este camp. Esta reñacionado con imex?
    imex_date = fields.Date(string='Fecha Imex', help='Fecha de importacion/exportacion de Facturas')
    debit_affected = fields.Char(string='Notas de débito afectadas', size=256, help='Notas de débito afectadas')
    credit_affected = fields.Char(string='Notas de crédito afectadas', size=256, help='Notas de crédito afectadas')
    type = fields.Selection(TYPE, string='Tipo de Transaccion', required=True, help="")
    void_form = fields.Char(string='Tipo de Transaccion', size=192, help="Tipo de Operacion")
    fiscal_printer = fields.Char(string='Nro de Maquina Fiscal', size=192, help="")
    z_report = fields.Char(string='Reporte Z', size=64, help="")
    custom_statement = fields.Char(string="Declaracion Personalizada",
                                   size=192, help="")
    # -- taxes fields
    total_with_iva = fields.Float('Total con IVA', help="Sub Total of the invoice (untaxed amount) plus"
                                                         " all tax amount of the related taxes")
    vat_sdcf = fields.Float("SDCF", help="Not entitled to tax credit (The field name correspond to the"
                                         " spanih acronym for 'Sin Derecho a Credito Fiscal')")
    vat_exempt = fields.Float("Exento", help="Exempt is a Tax with 0 tax percentage")
    vat_reduced_base = fields.Float("Base Reducido", help="Vat Reduced Base Amount")
    vat_reduced_tax = fields.Float("IVA Reducido", help="Vat Reduced Tax Amount")
    vat_general_base = fields.Float("Base Imponible", help="Vat General Base Amount")
    vat_general_tax = fields.Float("IVA", help="Vat General Tax Amount")
    vat_additional_base = fields.Float("Base Adicional", help="Vat Generald plus Additional Base Amount")
    vat_additional_tax = fields.Float("IVA Adicional", help="Vat General plus Additional Tax Amount")
    vat_reduced_rate = fields.Float(compute='_compute_vat_rates',
                                     string='Alicuota Reducida', #multi='all',
                                    help="IVA reducido tipo impositivo")
    vat_general_rate = fields.Float(compute='_compute_vat_rates',
                                    string='Alicuota general', # multi='all',
                                    help="Tasa de impuesto general del IVA")
    vat_additional_rate = fields.Float(compute='_compute_vat_rates',
                                       string='Alicuota Adicional', #multi='all',
                                       help="IVA más tasa impositiva adicional ")


class AccountFiscalBookTaxes(models.Model):
    _description = "Venezuela's Sale & Purchase Fiscal Book Taxes"
    _name = 'account.fiscal.book.taxes'
  #  _rec_name = 'ait_id'

    fb_id = fields.Many2one('account.fiscal.book', 'Fiscal Book', help='Fiscal Book where this tax is related to')
    fbl_id = fields.Many2one('account.fiscal.book.line', 'Fiscal Book Lines',
                             help='Fiscal Book Lines where this tax is related to')
   # ait_id = fields.Many2one('account.wh.iva.line.tax', 'Impuestos', help='Tax where is related to')
    type = fields.Char(string='tipo de libro')
    exento = fields.Float(string='Monto Exento',
                                  help='Monto exento',
                                  store=True)
    base_amount = fields.Float(#related='ait_id.base',
                                  string='Base Imponible',
                                  help='Amount used as Taxing Base',
                                  store=True)
    tax_amount = fields.Float(#related='ait_id.amount',
                                 string='Monto Gravado',
                                 help='Taxed Amount on Taxing Base',
                                 store=True)
    name = fields.Char(#related='ait_id.name',
                       string='Descripcion', store=True)
    currency_id = fields.Many2one('res.currency', string='Moneda')



class AccountFiscalBookTaxesSummary(models.Model):
    TAX_TYPE = [('exento', '0% Exento'),
                ('sdcf', 'No tiene derecho a crédito fiscal'),
                ('general', 'Alicuota General'),
                ('reducido', 'Alicuota Reducida'),
                ('adicional', 'Alicuota General + Adicional')]

    OP_TYPE = [('im', 'Importaciones'),
               ('do', 'Nacionales'),
               ('ex', 'Exportaciones'),
               ('tp', 'Contribuyente'),
               ('ntp', 'no Contribuyente')]

    _description = "Venezuela's Sale & Purchase Fiscal Book Taxes Summary"
    _name = 'account.fiscal.book.taxes.summary'
    _order = 'op_type, tax_type asc'

    fb_id = fields.Many2one('account.fiscal.book', 'Fiscal Book')
    tax_type = fields.Selection(TAX_TYPE, 'Tipo de Impuesto')
    op_type = fields.Selection(OP_TYPE, string='Tipo de Operacion',
                               help="Tipo de Operacion:"
                                    " - Compra: Import or Domestic."
                                    " - Sales: Expertation, Tax Payer, Non-Tax Payer.")
    base_amount_sum = fields.Float('suma base impobible')
    tax_amount_sum = fields.Float('Suma del monto gravado')
    currency_id = fields.Many2one('res.currency', string='moneda')
    _rec_rame = 'Fiscal_book_taxes_summary_rec'


class AdjustmentBookLine(models.Model):
    TYPE_DOC = [('F', 'Factura'),
                ('ND', 'Nota de Debito'),
                ('NC', 'Nota de Credito'), ]

    _name = 'adjustment.book.line'

    date_accounting = fields.Date('Fecha Contable', required=True, help="Date accounting for adjustment book")
    date_admin = fields.Date('Date Administrative', required=True,
                             help="Date administrative for adjustment book")
    vat = fields.Char('RIF', size=10, required=True, help="Vat of partner for adjustment book")
    partner = fields.Char('Empresa', size=256, required=True, help="Partner for adjustment book")
    invoice_number = fields.Char('Nro de Factura', size=256, required=True, help="Invoice number for adjustment book")
    control_number = fields.Char('Nro de Control de Factura', size=256, required=True, help="")
    amount = fields.Float('Documento de importe en retención de IVA', # digits=(16, 2),
                          required=True,
                          help="Documento de importe en retención de IVA")
    type_doc = fields.Selection(TYPE_DOC, 'Tipo de Documento', select=True, required=True,
                                help="Tipo de documento para libro de ajustes"
                                     " -Invoice(F),-Debit Note(dn),-Credit Note(cn)")
    doc_affected = fields.Char('Affected Document', size=256, required=True,
                               help="Affected Document for adjustment book")
    uncredit_fiscal = fields.Float('Sin derecho a Credito Fiscal', #digits=(16, 2),
                                   # required=True,
                                   help="Sin derechoa credito fiscal")
    amount_untaxed_n = fields.Float('Amount Untaxed', #digits=(16, 2), required=True,
                                    help="Amount untaxed for national operations")
    percent_with_vat_n = fields.Float('VAT Withholding (%)', #digits=(16, 2), required=True,
                                      help="VAT percent (%) for national operations")
    amount_with_vat_n = fields.Float('VAT Withholding Amount', # digits=(16, 2), required=True,
                                     help="Percent(%) VAT for national operations")
    amount_untaxed_i = fields.Float('Amount Untaxed', # digits=(16, 2), required=True,
                                    help="Amount untaxed for international operations")
    percent_with_vat_i = fields.Float('VAT Withholding (%)', #digits=(16, 2), required=True,
                                      help="VAT percent (%) for international operations")
    amount_with_vat_i = fields.Float('VAT Withholding Amount', # digits=(16, 2), required=True,
                                     help="VAT amount for international operations")
    amount_with_vat = fields.Float('VAT Withholding Total Amount',
                                  # digits=(16, 2), required=True,
                                   help="VAT withholding total amount")
    voucher = fields.Char('VAT Withholding Voucher', size=256, required=True, help="VAT withholding voucher")
    fb_id = fields.Many2one('account.fiscal.book', 'Fiscal Book', help='Fiscal Book where this line is related to')

    _rec_rame = 'partner'