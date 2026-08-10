# coding: utf-8
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.exceptions import Warning
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
from datetime import datetime, date
from dateutil import relativedelta
import logging

_DATETIME_FORMAT = "%Y-%m-%d"
_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    supplier_invoice_number = fields.Char(string='Supplier Invoice Number', store=True,
                                          help="The reference of this invoice as provided by the supplier.")

    sin_cred = fields.Boolean(string='Excluir este documento del libro fiscal', readonly=False,
                              help="Configúrelo verdadero si la factura está exenta de IVA (exención de impuestos)")

    date_document = fields.Date(string='Document Date', states={'draft': [('readonly', False)]},
                                help="Fecha administrativa, generalmente es la fecha impresa en factura, esta fecha se"
                                     " utiliza para mostrar en la compra fiscal libro")
    invoice_printer = fields.Char(string='Número de factura de impresora fiscal', size=64, required=False,
                                  help="Fiscal printer invoice number, is the number of the invoice"
                                       " on the fiscal printer")
    invoice_reverse_purchase_id = fields.Many2one('account.move', string="Reversal invoice purchase", copy=False)
    fiscal_printer = fields.Char(string='Número Impresora Fiscal', size=64, required=False,
                                 help="Fiscal printer number, generally is the id number of the printer.")

    comment_paper = fields.Char(string='Comentario')
    paper_anu = fields.Boolean(string='Papel Dañado', default=False)
    marck_paper = fields.Boolean(default=False)
    maq_fiscal_p = fields.Boolean(string='Maquina Fiscal', default=False)

    nro_ctrl = fields.Char(string='Número de Control', size=32,
                           help="Número utilizado para gestionar facturas preimpresas, por ley Necesito poner aquí este"
                                " número para poder declarar Informes fiscales correctamente.", copy=False, store=True,
                           domain="['|',('move_type', '=', 'out_invoice'),('move_type', '=', 'out_refund')]")

    # Campos proveedores##########################
    nro_planilla_impor = fields.Char(string='Nro de Planilla de Importacion')
    nro_expediente_impor = fields.Char(string='Nro de Expediente de Importacion')
    fecha_importacion = fields.Date(string='Fecha de la planilla de Importación')
    supplier_rank1 = fields.Integer(related='partner_id.supplier_rank')
    # Campos clientes##########################
    customer_rank1 = fields.Integer(related='partner_id.customer_rank')
    # Campos para ambas retenciones##########################
    partner_id = fields.Many2one('res.partner', readonly=True,
                                 domain="['|',('customer_rank', '>=', 0),('supplier_rank', '>=', 0)]",
                                 string='Partner')
    rif = fields.Char(string="RIF", related='partner_id.rif', store=True, states={'draft': [('readonly', True)]})
    identification_id1 = fields.Char(string='Documento de Identidad', related='partner_id.identification_id',
                                     store=True, states={'draft': [('readonly', True)]})
    nationality1 = fields.Selection([('V', 'Venezolano'), ('E', 'Extranjero'), ('P', 'Pasaporte')],
                                    string="Tipo Documento", related='partner_id.nationality', store=True,
                                    states={'draft': [('readonly', True)]})
    people_type_company1 = fields.Selection([('pjdo', 'PJDO Persona Jurídica Domiciliada'),
                                             ('pjnd', 'PJND Persona Jurídica No Domiciliada')],
                                            string='Tipo de Persona compañía val')
    people_type_individual1 = fields.Selection([('pnre', 'PNRE Persona Natural Residente'),
                                                ('pnnr', 'PNNR Persona Natural No Residente')],
                                               string='Tipo de Persona individual val')
    company_type1 = fields.Selection(string='Company Type',
                                     selection=[('person', 'Individual'), ('company', 'Company')])
    create_invoice = fields.Boolean(string='Crear factura', default=False)

    ### retencion de Iva##########################
    rela_wh_iva = fields.Many2one('account.wh.iva', copy=False)
    wh_iva = fields.Boolean('¿Ya se ha retenido esta factura con el IVA?',
                            # compute='_compute_retenida',
                            copy=False, help="Los movimientos de la cuenta de la factura han sido retenidos con "
                                             "movimientos de cuenta de los pagos.",tracking=True)
    wh_iva_id = fields.Many2one(
        'account.wh.iva', string='Documento de Retención de IVA',
        compute='_compute_wh_iva_id', store=True,
        help="Este es el documento de retención de IVA donde en esta factura "
             "está siendo retenida.",tracking=True, copy=False)
    vat_apply = fields.Boolean(
        string='Excluir este documento de la retención del IVA',
        states={'draft': [('readonly', False)]},
        help="Esta selección indica si generar la factura "
             "documento de retención",tracking=True)

    islr_wh_doc_id = fields.Many2one(
        'account.wh.islr.doc', string='Documento de retención de ingresos',
        help="Documentación de la retención de ingresos del impuesto generado a partir de esta factura",tracking=True, copy=False)

    wh_xml_id = fields.Many2one('account.wh.islr.xml.line',string='XML Id',default=0,help="XML withhold line id",tracking=True)

    status = fields.Selection([
        ('pro', 'Retención procesada, línea xml generada'),
        ('no_pro', 'Retención no procesada'),
        ('tasa', 'No exceda la tasa, línea xml generada'),
    ], string='Estatus retención ISLR', readonly=True, default='no_pro',
        help=''' * La \'Retención procesada, línea xml generada\'
               es usada cuando el usuario procesa la Retencion de ISLR.
               * La 'Retencion no Procesada\' state es cuando un usuario realiza una factura y se genera el documento de retencion de islr y aun no esta procesado.
               * \'No exceda la tasa, línea XML generada\' se utiliza cuando el usuario crea la factura, una factura no supera la tarifa mínima.''',tracking=True)

    fb_id = fields.Many2one('account.fiscal.book', 'Fiscal Book',
                            help='Libro fiscal donde esta línea está relacionada con')
    issue_fb_id = fields.Many2one('account.fiscal.book', 'Fiscal Book',
                                  help='Libro fiscal donde se debe agregar esta factura')

    alicuota_line_ids = fields.One2many('account.move.line.resumen', 'invoice_id', string='Resumen')

    iva_number_asignado = fields.Char(string="Número retención IVA", copy=False)
    islr_number_asignado = fields.Char(string="Número retención ISLR", copy=False)

    invoice_import_id = fields.Many2one('account.move', string='Factura SENIAT', copy=False)

        ##RETENCIONES MUNICIPALES##

    apply_municipal_withholding = fields.Boolean(
        string="Aplicar Retención Municipal",
        help="Si está activado, al confirmar la factura se generará una retención municipal en estado Borrador.",
        copy=False,
        tracking="1"
    )

    wh_municipal = fields.Boolean(string="Retenido", readonly=True, copy=False, tracking="1")
    wh_municipal_id = fields.Many2one('account.wh.municipal', string="Retención Municipal", readonly=True, tracking="1", copy=False)
    municipal_number_asignado = fields.Char(string="Número de Retención Municipal", readonly=True, tracking="1", copy=False)
    municipal_apply = fields.Boolean(
        string="Excluir este documento de la retención municipal",
        help="Si se activa, este documento no será tomado en cuenta en la retención municipal."
    )

    @api.onchange('journal_id')
    def _onchange_journal_id(self):
        super(AccountMove, self)._onchange_journal_id()
        for rec in self:
            if rec.journal_id.eliminar_impuestos:
                for l in rec.invoice_line_ids:
                    l.tax_ids = [(5)]

    def _get_company(self):
        res_company = self.env['res.company'].search([('id', '=', self.company_id.id)])
        return res_company

    def action_post(self):
        # Solo lógica informativa o de asignación de conceptos
        for res in self:
            for concep in res.invoice_line_ids:
                if concep.product_id.concept_id:
                    concep.concept_id = concep.product_id.concept_id
            # NUNCA recalcular montos/líneas aquí
            res.suma_alicuota_iguales_iva()

        # Deja que Odoo maneje el asiento, la diferencia de cambio y la validación de monedas y montos
        var = super(AccountMove, self).action_post()
        
        # 3. Lógica post-posteo (solo para documentos adicionales, retenciones, notificaciones, etc.)
        for res in self:
            if not res.journal_id.eliminar_impuestos:
                resul = res._withholdable_tax()
                monto_tax = 0
                hay_iva_gravado = False
                for inv in res.line_ids:
                    for tax in inv.tax_ids:
                        if tax.amount > 0:  # puedes agregar and tax.appl_type in ['general', 'reducido', 'adicional']
                            hay_iva_gravado = True
                            break
                if res.company_id.partner_id.wh_iva_agent and res.partner_id.wh_iva_agent and resul and hay_iva_gravado:
                    if res.state == 'posted':
                        for ilids in res.invoice_line_ids:
                            res.check_document_date()
                            res.check_invoice_dates()
                            apply = res.check_wh_apply()
                            if apply:
                                res.check_withholdable()
                                res.action_wh_iva_supervisor()
                                res.action_wh_iva_create()
            if res.company_id.partner_id.islr_withholding_agent and res.partner_id.islr_withholding_agent:
                for concep in res.invoice_line_ids:
                    if concep.concept_id.withholdable is True:
                        if res.state == 'posted' and not res.islr_wh_doc_id:
                            for ilids in res.invoice_line_ids:
                                res.check_invoice_type()
                                res.check_withholdable_concept()
                                islr_wh_doc_id = res._create_islr_wh_doc()
                                if islr_wh_doc_id:
                                    res.write({'islr_wh_doc_id': islr_wh_doc_id.id})

            # Aplicar Retención Municipal si está activado
            if res.apply_municipal_withholding and not res.municipal_apply and res.state == 'posted':
                # Determinar la base imponible correcta según la moneda de la factura
                if res.currency_id.name != "VEF":
                    base_imponible = res.amount_untaxed_bs  # Si la moneda es distinta de VEF (ejemplo: USD), usar el monto en Bs
                else:
                    base_imponible = res.amount_untaxed  # Si la moneda es VEF, usar el monto normal sin impuestos


                # Calcular el monto de la retención (1% de la base imponible)
                retencion_municipal = base_imponible * (res.partner_id.porcentaje / 100)  # 1% de la base imponible

                # Crear la retención municipal
                retencion = res.env['account.wh.municipal'].create({
                    'move_id': res.id,
                    'date': fields.Date.context_today(res),
                    'amount': retencion_municipal,
                    'state': 'draft',
                })

                # Guardar la retención en la factura
                res.write({
                    'wh_municipal': True,
                    'wh_municipal_id': retencion.id,
                    'municipal_number_asignado': retencion.municipal_number_asignado
                })

        return var
    
    def action_generate_municipal_withholding(self):
        for res in self:
            if (
                res.apply_municipal_withholding
                and not res.municipal_apply
                and res.state == 'posted'
            ):
                # Determinar la base imponible correcta según la moneda de la factura
                base_imponible = res.amount_untaxed_bs if res.currency_id.name != "VEF" else res.amount_untaxed

                # Calcular el monto de la retención
                retencion_municipal = base_imponible * (res.partner_id.porcentaje / 100)

                # Crear el registro de retención municipal
                retencion = self.env['account.wh.municipal'].create({
                    'move_id': res.id,
                    'date': fields.Date.context_today(res),
                    'amount': retencion_municipal,
                    'state': 'draft',
                })

                # Guardar la retención en la factura
                res.write({
                    'wh_municipal': True,
                    'wh_municipal_id': retencion.id,
                    'municipal_number_asignado': retencion.municipal_number_asignado
                })

    def _get_sequence_code(self):
        # metodo que crea la secuencia del número de control, si no esta creada crea una con el
        # nombre: 'l10n_nro_control
        self.ensure_one()
        sequence_code = 'l10n_nro_control_sale'
        company_id = self._get_company()
        #ir_sequence = self.env['ir.sequence'].with_context(force_company=company_id.id)
        ir_sequence = self.env['ir.sequence'].with_company(company_id)
        self.nro_ctrl = ir_sequence.next_by_code(sequence_code)
        return self.nro_ctrl

    @api.model
    def _get_default_invoice_date(self):
        return fields.Date.today() if self._context.get('default_move_type', 'entry') in \
                                      ('in_invoice', 'in_refund', 'in_receipt') else False

    def button_cancel(self):
        super().button_cancel()
        self.suma_alicuota_iguales_iva()
        self.state='cancel'

    def generate_islr(self):
        for rec in self:
            for concep in rec.invoice_line_ids:
                if concep.product_id.concept_id:
                    concep.concept_id = concep.product_id.concept_id

            for concep in rec.invoice_line_ids:
                if concep.concept_id.withholdable:
                    if self.state == 'posted' and not rec.islr_wh_doc_id:
                        for ilids in self.invoice_line_ids:
                            self.check_invoice_type()
                            self.check_withholdable_concept()
                            islr_wh_doc_id = self._create_islr_wh_doc()
                            islr_wh_doc_id and self.write({'islr_wh_doc_id': islr_wh_doc_id.id})

    @api.model_create_multi
    def create(self, values):


        res = super(AccountMove, self).create(values)
        for r in res:
            if r.invoice_date and r.date:
                if r.invoice_date > r.date:
                    raise Warning(_('La fecha contable no puede ser menor a la fecha de la factura'))
        return res

    def write(self, vals):
        for move_account in self:
            if move_account.move_type == 'in_invoice' and move_account.invoice_origin:
                order_purchase = self.env['purchase.order'].search([('name', '=', self.invoice_origin)])
                if order_purchase:
                    vals.update({'partner_id': order_purchase.partner_id.id})
        if vals.get('partner_id'):
            partner_id = vals.get('partner_id')
            partner_obj = self.env['res.partner'].search([('id', '=', partner_id)])
            if partner_obj.company_type == 'person' and not partner_obj.identification_id:
                raise UserError("Advertencia! \nEl Proveedor no posee Documento Fiscal. Por favor diríjase a la configuación de %s, y realice el registro correctamente para poder continuar" % (partner_obj.name))
            if partner_obj.company_type == 'company':
                if partner_obj.people_type_company == 'pjdo' and not partner_obj.rif:
                    raise UserError("Advertencia! \nEl Proveedor no posee Documento Fiscal. Por favor diríjase a la configuación de %s, y realice el registro correctamente para poder continuar" % (partner_obj.name))
        if vals.get('move_type') in ('out_invoice', 'out_refund') and \
                vals.get('date') and not vals.get('date_document'):
            vals['date_document'] = vals['date']
        if vals.get('supplier_invoice_number', False):
            supplier_invoice_number_id = self._unique_invoice_per_partner('supplier_invoice_number',
                                                                          vals.get('supplier_invoice_number', False))
            if not supplier_invoice_number_id:
                self.supplier_invoice_number = False
                return {'warning': {'title': "Advertencia!",
                                    'message': "  El Numero de la Factura del Proveedor ya Existe  "}}
        if vals.get('nro_ctrl', False):
            if not self.maq_fiscal_p:
                nro_ctrl_id = self._unique_invoice_per_partner('nro_ctrl', vals.get('nro_ctrl', False))
                if not nro_ctrl_id:
                    self.nro_ctrl = False
                    return {'warning': {'title': "Advertencia!",
                                        'message': "  El Numero de control de la Factura del Proveedor ya Existe  "}}
        if not vals.get('check_fiscal'):
            if vals.get('invoice_date') and isinstance(vals.get('invoice_date'), str):
                fecha_factura = datetime.strptime(vals.get('invoice_date'), '%Y-%m-%d').date()
            else:
                if vals.get('invoice_date'):
                    fecha_factura = vals.get('invoice_date')
                elif len(self) < 2:
                    fecha_factura = self.invoice_date
                else:
                    fecha_factura = False
            if vals.get('date') and isinstance(vals.get('invoice_date'), str):
                fecha = datetime.strptime(vals.get('date'), '%Y-%m-%d').date()
            else:
                if vals.get('date'):
                    fecha = vals.get('date')
                elif len(self) < 2:
                    fecha = self.date
                else:
                    fecha = False
            # if fecha and fecha_factura:
            #     if fecha_factura > fecha:
            #         raise Warning(_('La fecha contable no puede ser menor a la fecha de la factura'))
        else:
            del vals['check_fiscal']
        return super(AccountMove, self).write(vals)

    def _get_journal(self, context):
        """ Return the journal which is
        used in the current user's company, otherwise
        it does not exist, return false
        """
        context = context or {}
        res = super(AccountMove, self)._get_journal(context)
        if res:
            return res
        type_inv = context.get('type', 'sale')
        if type_inv in ('sale_debit', 'purchase_debit'):
            user = self.env['res.users'].browse(context)
            company_id = context.get('company_id', user.company_id.id)
            journal_obj = self.env['account.journal']
            domain = [('company_id', '=', company_id), ('type', '=', type_inv)]
            res = journal_obj.search(domain, limit=1)
        return res and res[0] or False

    def _unique_invoice_per_partner(self, field, value):
        """ Return false when it is found
        that the bill is not out_invoice or out_refund,
        and it is not unique to the partner.
        """
        ids_ivo = []
        for inv in self:
            ids_ivo.append(inv.id)
            if inv.move_type in ('out_invoice', 'out_refund'):
                return True
            inv_ids = (self.search([(field, '=', value), ('move_type', '=', inv.move_type), ('partner_id', '=', inv.partner_id.id),('state','=','posted')]))

            if [True for i in inv_ids if i not in ids_ivo] and inv_ids:
                return False
        return True

    # Validaciónn de Fecha
    @api.onchange('date_document')
    def onchange_date_document(self):
        fecha = self.date_document
        if fecha:
            fecha2 = str(fecha)
            age = self._calculate_date(fecha2)
            if age:
                if age.days >= 0 and age.months >= 0 and age.years >= 0:
                    self.date_document = fecha
                else:
                    self.date_document = False
                    return {'warning': {'title': "Advertencia!",
                                        'message': "La fecha ingresada es mayor que la fecha actual"}}

    @staticmethod
    def _calculate_date(value):
        age = 0
        if value:
            ahora = datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT)

            age = relativedelta.relativedelta(datetime.strptime(ahora, _DATETIME_FORMAT),
                                              datetime.strptime(value, _DATETIME_FORMAT))
        return age

    # def copy(self, default=None):
    #     res = super(AccountMove, self).copy(default)
    #     return res

    @api.onchange('supplier_invoice_number')
    def onchange_supplier_invoice_number(self):
        if self.supplier_invoice_number:
            supplier_invoice_number_id = self._unique_invoice_per_partner('supplier_invoice_number', self.supplier_invoice_number)
            if not supplier_invoice_number_id:
                self.supplier_invoice_number = False
                return {'warning': {'title': "Advertencia!",
                                    'message': "  El Numero de la Factura del Proveedor ya Existe  "}}

    @api.onchange('nro_ctrl')
    def onchange_nro_ctrl(self):
        if self.nro_ctrl:
            if not self.maq_fiscal_p:
                nro_ctrl_id = self._unique_invoice_per_partner('nro_ctrl', self.nro_ctrl)
                if not nro_ctrl_id:
                    self.nro_ctrl = False
                    return {'warning': {'title': "Advertencia!",
                                        'message': "  El Numero de control de la Factura del Proveedor ya Existe  "}}

    @api.onchange('partner_id')
    def _compute_partner(self):
        # self.people_type = self.partner_id.people_type_company
        self.customer_rank1 = self.partner_id.customer_rank
        self.supplier_rank1 = self.partner_id.supplier_rank
        self.people_type_company1 = self.partner_id.people_type_company
        self.people_type_individual1 = self.partner_id.people_type_individual
        self.company_type1 = self.partner_id.company_type
        return

    def ret_and_reconcile(self, pay_amount, pay_account_id,
                        pay_journal_id, writeoff_acc_id,
                        writeoff_journal_id, date,
                        name, to_wh, type_retencion):
        """ Make the payment of the invoice """
        rp_obj = self.env['res.partner']
        move_obj = self.env['account.move']
        if self.ids:
            assert len(self.ids) == 1, "Solo puede pagar una factura a la vez"
        else:
            assert len(to_wh) == 1, "Solo puede pagar una factura a la vez"
        invoice = self.browse(self.ids)
        src_account_id = pay_account_id.id

        types = {'out_invoice': -1, 'in_invoice': 1, 'out_refund': 1, 'in_refund': -1}
        direction = types[invoice.move_type]
        l1 = {
            'debit': direction * pay_amount > 0 and direction * pay_amount,
            'credit': direction * pay_amount < 0 and - direction * pay_amount,
            'account_id': src_account_id,
            'partner_id': rp_obj._find_accounting_partner(invoice.partner_id).id,
            'ref': invoice.name,
            'date': date,
            'currency_id': invoice.company_id.currency_id.id,
            'name': name
        }
        lines = [(0, 0, l1)]

        if type_retencion == 'wh_iva':
            l2 = self._get_move_lines1(to_wh, pay_journal_id, writeoff_acc_id, writeoff_journal_id, date, name)
        elif type_retencion == 'wh_islr':
            l2 = self._get_move_lines2(to_wh, pay_journal_id, writeoff_acc_id, writeoff_journal_id, date, name)
        elif type_retencion == 'wh_muni':
            l2 = self._get_move_lines3(to_wh, pay_journal_id, writeoff_acc_id, writeoff_journal_id, date, name)
        else:
            l2 = []

        if not l2:
            raise UserError("Advertencia! \nNo se crearon movimientos contables.\n Por favor, verifique si hay impuestos / conceptos para retener en las facturas!")

        deb = l2[0][2]['debit']
        cred = l2[0][2]['credit']
        if deb < 0: l2[0][2].update({'debit': deb * direction})
        if cred < 0: l2[0][2].update({'credit': cred * direction})

        lines += l2

        move = {
            'ref': name + ' de ' + str(invoice.name),
            'line_ids': lines,
            'journal_id': pay_journal_id,
            'date': date,
            'state': 'draft',
            'type_name': 'entry'
        }

        move_id = move_obj.create(move)
        move_id._post(soft=False)

        to_reconcile = invoice.line_ids.filtered_domain([('account_id', '=', src_account_id), ('reconciled', '=', False)])
        payment_lines = move_id.line_ids.filtered_domain([('account_id', '=', src_account_id), ('reconciled', '=', False)])
        results = (payment_lines + to_reconcile).reconcile()

        return move_id

    @api.depends('wh_iva_id.wh_lines')
    def _compute_wh_iva_id(self):
        for record in self:
            lines = self.env['account.wh.iva.line'].search([
                ('invoice_id', '=', record.id)])
            record.wh_iva_id = lines and lines[0].retention_id.id or False

    def already_posted_iva(self):
        monto_tax = 0
        if self:
            #  self._compute_retenida()
            resul = self._withholdable_tax()
            for inv in self.line_ids:
                if len(self.line_ids.tax_ids) == 1:
                    for tax in inv.tax_ids:
                        if tax.amount == 0:
                            monto_tax = 2000

        if self.company_id.partner_id.wh_iva_agent and self.partner_id.wh_iva_agent and resul and monto_tax == 0:
            if self.state == 'posted':
                for ilids in self.invoice_line_ids:
                    self.check_document_date()
                    self.check_invoice_dates()
                    apply = self.check_wh_apply()
                    if apply == True:
                        self.check_withholdable()
                        self.action_wh_iva_supervisor()
                        self.action_wh_iva_create()

    def check_document_date(self):
        """
        check that the invoice in open state have the document date defined.
        @return True or raise an orm exception.
        """
        for inv_brw in self:
            if (inv_brw.move_type in ('in_invoice', 'in_refund', 'out_invoice', 'out_refund') and
                    inv_brw.state == 'posted' and not inv_brw.date):
                raise UserError("Advertencia \nLa fecha del documento no puede estar vacía cuando la factura se encuentra en estado publicado.")
        return True


    def check_invoice_dates(self):
        """
        check that the date document is less or equal than the date invoice.
        @return True or raise and osv exception.
        """
        for inv_brw in self:
            if (inv_brw.move_type in ('in_invoice', 'in_refund', 'out_invoice', 'out_refund') and
                    inv_brw.date and not inv_brw.invoice_date <= inv_brw.date):
                raise UserError("Warning \nThe document date must be less or equal than the invoice date.")
        return True

    def wh_iva_line_create(self):
        """ Creates line with iva withholding """
        wil_obj = self.env['account.wh.iva.line']
        values = {}
        type_invoice = ''
        for inv_brw in self:
            # Toma la tasa según el tipo de factura
            if inv_brw.move_type in ('in_invoice', 'in_refund', 'in_debit'):
                wh_iva_rate = inv_brw.partner_id.wh_iva_purchase_rate  or 0.0
            else:
                wh_iva_rate = inv_brw.company_id.wh_iva_sale_rate or 0.0

            if inv_brw.move_type in ('in_invoice', 'out_invoice', 'out_refund', 'in_refund'):
                if inv_brw.debit_origin_id and inv_brw.move_type == 'out_invoice':
                    type_invoice = 'out_debit'
                elif inv_brw.move_type == 'in_invoice' and  inv_brw.debit_origin_id:
                    type_invoice = 'in_debit'
                elif not inv_brw.debit_origin_id and inv_brw.move_type in ('out_invoice','in_invoice','in_refund','out_refund'):
                    type_invoice = inv_brw.move_type

            values = {
                'name': _('IVA WH - ORIGIN %s' % (inv_brw.name)),
                'invoice_id': inv_brw.id,
                'wh_iva_rate': wh_iva_rate,
                'type': type_invoice,
            }

        return values and wil_obj.create(values)


    def action_wh_iva_supervisor(self):
        """ Validate the currencys are equal
        """
        for inv in self:
            if inv.amount_total == 0.0:
                raise UserError(
                    _('Acción Invalida!\nEsta factura tiene una cantidad total% s% s verifique el '
                      'precio de los productos') % (inv.amount_total,
                                            inv.currency_id.symbol))
        return True


    def get_fortnight_wh_id(self):
        """ Returns the id of the acc.wh.iva in draft state that correspond to
        the invoice fortnight. If not exist return False.
        """
        wh_iva_obj = self.env['account.wh.iva']
        partner = self.env['res.partner']
        for inv_brw in self:
            invoice_date = inv_brw.invoice_date
            acc_part_id = partner._find_accounting_partner(inv_brw.partner_id)
            #inv_period, inv_fortnight = period.find_fortnight(invoice_date)
            ttype = (inv_brw.move_type in ["in_refund", "out_refund"])

            for wh_iva in wh_iva_obj.search([
                    ('state', '=', 'draft'), ('type', '=', ttype), '|',
                    ('partner_id', '=', acc_part_id.id),
                    ('partner_id', 'child_of', acc_part_id.id)]):
                    #('fortnight', '=', inv_fortnight):
                return wh_iva.id
        return False


    def create_new_wh_iva(self):
        """ Create a Withholding VAT document.
        @param ids: only one id.
        @return id of the new wh vat document created.
        """
        ret_iva = []
        wh_iva_obj = self.env['account.wh.iva']
        rp_obj = self.env['res.partner']
        values = {}
        acc_id = 0
        for inv_brw in self:
            acc_id = 0
            acc_part_id = rp_obj._find_accounting_partner(inv_brw.partner_id)
            if inv_brw.move_type in ('out_invoice', 'out_refund','_out_debit'):
                acc_id = acc_part_id.property_account_receivable_id.id
                wh_type = 'out_invoice'
            else:
                acc_id = acc_part_id.property_account_payable_id.id
                wh_type = 'in_invoice'
                if not acc_id:
                    raise UserError(
                        _('Accion Invalida\nSe debe configurar el partner'
                          'Con las Cuentas Contables'))
            values = {'name': _('IVA WH - ORIGIN %s' % (inv_brw.name)),
                      'type': wh_type,
                      'account_id': acc_id,
                      'partner_id': acc_part_id.id,
                      }
                # 'date_ret': inv_brw.invoice_date,
                # 'period_id': inv_brw.invoice_date,
                # 'date': inv_brw.invoice_date,

            if inv_brw.company_id.propagate_invoice_date_to_vat_withholding:
                ret_iva['date'] = inv_brw.invoice_date
                ret_iva['date_ret'] = ret_iva['date']
                ret_iva['period_id'] = ret_iva['date']
        return values and wh_iva_obj.create(values)


    def action_wh_iva_create(self):
        """ Create withholding objects """
        ret_iva = []
        for inv in self:
            if inv.wh_iva_id:
                if inv.wh_iva_id.state == 'draft':
                    pass
                    #inv.wh_iva_id.compute_amount_wh()
                else:
                    raise UserError(
                        _('Advertencia!\nYa tiene un documento de retención asociado a '
                          'su factura, pero este documento de retención no está en'
                          'estado cancelado.'))
            else:
                # Create Lines Data
                ret_id = {}
                journal = 0
                acc_id = 0
                ret_line_id = inv.wh_iva_line_create()
                fortnight_wh_id = inv.get_fortnight_wh_id()
                # Add line to a WH DOC
                if fortnight_wh_id:
                    # Add to an exist WH Doc
                    ret_id = fortnight_wh_id
                    if not ret_id:
                        raise UserError(
                            _('Error!\nNo se puede encontrar el documento de retención'))
                    wh_iva = self.env['account.wh.iva'].browse(ret_id)
                    wh_iva.write({'wh_lines': [(4, ret_line_id.id)]})
                else:
                    # Create a New WH Doc and add line
                    type_invoice = ''
                    wh_iva_obj = self.env['account.wh.iva']
                    rp_obj = self.env['res.partner']
                    values = {}

                    for inv_brw in self:
                        acc_part_id = rp_obj._find_accounting_partner(inv_brw.partner_id)
                        if inv_brw.move_type in ('out_invoice', 'out_refund', '_out_debit'):
                            acc_id = acc_part_id.property_account_receivable_id.id
                        elif inv_brw.move_type in ('in_invoice', 'in_refund', '_in_debit'):
                            acc_id = acc_part_id.property_account_payable_id.id

                        if inv_brw.move_type in ('out_invoice', 'out_refund'):
                            if inv_brw.debit_origin_id and inv_brw.move_type == 'out_invoice':
                                type_invoice = 'out_debit'
                                journal = acc_part_id.purchase_sales_id.id
                            elif not inv_brw.debit_origin_id and inv_brw.move_type in ('out_invoice', 'out_refund'):
                                type_invoice = inv_brw.move_type
                                journal = acc_part_id.purchase_sales_id.id
                            values = {'name': _('IVA WH CLIENTE - ORIGIN %s' % (inv_brw.name)),
                                      'type': type_invoice,
                                      'account_id': acc_id,
                                      'partner_id': acc_part_id.id,
                                      'journal_id': journal,
                                      'date_ret': inv_brw.date,
                                      'period_id': inv_brw.date,
                                      'date': inv_brw.date,
                                      }
                        else:
                            if inv_brw.move_type in ('in_invoice', 'in_refund'):
                                if inv_brw.move_type == 'in_invoice' and inv_brw.debit_origin_id:
                                    type_invoice = 'in_debit'
                                    journal = acc_part_id.purchase_journal_id.id
                                elif not inv_brw.debit_origin_id and inv_brw.move_type in ('in_refund', 'in_invoice'):
                                    type_invoice = inv_brw.move_type
                                    journal = acc_part_id.purchase_journal_id.id

                            if not acc_id:
                                raise UserError(
                                    _('Invalid Action !\nYou need to configure the partner with'
                                      ' withholding accounts!'))
                            values = {'name': _('IVA WH - ORIGIN %s' % (inv_brw.supplier_invoice_number)),
                                      'type': type_invoice,
                                      'account_id': acc_id,
                                      'journal_id': journal,
                                      'partner_id': acc_part_id.id,
                                      'date_ret': inv_brw.date,
                                      'period_id': inv_brw.date,
                                      'date': inv_brw.date,
                                     }
                        if inv_brw.company_id.propagate_invoice_date_to_vat_withholding:
                            ret_iva['date'] = inv_brw.invoice_date
                            ret_iva['date_ret'] = ret_iva['date']
                            ret_iva['period_id'] = ret_iva['date']


                    ret_id =  wh_iva_obj.create(values)


                    ret_id.write({'wh_lines': [(4, ret_line_id.id)]})
                    if hasattr(ret_id, 'id'): ret_id = ret_id.id
                    if ret_id:
                        inv.write({'wh_iva_id': ret_id})
                        inv.wh_iva_id.compute_amount_wh()

        return True


    def button_reset_taxes_ret(self):
        """ Recalculate taxes in invoice
        """
        account_invoice_tax = self.env['account.tax']
        for inv in self:
            compute_taxes_ret = account_invoice_tax.compute_amount_ret(inv)
            for tax in account_invoice_tax.browse(compute_taxes_ret.keys()):
                tax.write(compute_taxes_ret[tax.id])
        return True


    def button_reset_taxes(self):
        """ It makes two function calls related taxes reset
        """
        res = super(AccountMove, self).button_reset_taxes()
        self.button_reset_taxes_ret()
        return res


    def _withholding_partner(self):
        """ I verify that the provider retains or not
        """
        # No VAT withholding Documents are created for customer invoice &
        # refunds
        for inv in self:
            if inv.move_type in ('in_invoice', 'in_refund', 'out_invoice', 'out_refund') and \
                    self.env['res.partner']._find_accounting_partner(
                        inv.company_id.partner_id).wh_iva_agent:
                return True
        return False


    def _withholdable_tax(self):
        """ Verify that existing withholding in invoice
        """
        is_withholdable = False
        for inv in self.line_ids:
            for tax in inv.tax_ids:
                if tax.type_tax == 'iva':
                    is_withholdable = True
        return is_withholdable
    
    def check_withholdable(self):

        #period = self.env['account.period']
        for inv in self:
            if inv.move_type == 'in_invoice':
                return True
            if inv.move_type == 'out_invoice':
                return True

            '''
            if inv.move_type == 'in_refund' and inv.parent_id:
                dt_refund = inv.invoice_date or time.strftime('%Y-%m-%d')
                dt_invoice = inv.parent_id.invoice_date
                return period.find_fortnight(dt_refund) == period.find_fortnight(dt_invoice)
            '''
        return False


    def check_wh_apply(self):
        """ Apply withholding to the invoice
        """
        wh_apply = []
        for inv in self:
            if inv.vat_apply or inv.sin_cred:
                return False
            wh_apply.append(inv._withholdable_tax())
            wh_apply.append(inv._withholding_partner())
        return all(wh_apply)

    def _get_move_lines1(self, to_wh, journal_id, writeoff_account_id, writeoff_journal_id,
                          date,name):

        res = []
        acc = None
        for invoice in self:
            acc_part_id = \
                self.env['res.partner']._find_accounting_partner(
                    invoice.partner_id)

            types = {'out_invoice': -1,
                     'in_invoice': 1,
                     'out_refund': 1,
                     'in_refund': -1}
            direction = types[invoice.move_type]

            amount_ret2 = 0
            for tax_brw in to_wh:

                acc = (tax_brw.wh_vat_line_id.retention_id.journal_id.default_iva_account.id and
                           tax_brw.wh_vat_line_id.retention_id.journal_id.default_iva_account.id or
                           False)
                if not acc:
                    raise UserError(
                        ("¡Falta una cuenta en impuestos!\n El impuesto [% s] tiene una cuenta faltante. Por favor, complete el "
                          "campos faltantes") % (tax_brw.name))
                amount_ret2 += tax_brw.amount_ret
            res.append((0, 0, {
                'debit':
                    direction * amount_ret2 < 0 and
                    direction * amount_ret2,
                'credit':
                    direction * amount_ret2 > 0 and
                    direction * amount_ret2,
                'account_id': acc,
                'partner_id': acc_part_id.id,
                'ref': invoice.name,
                'date': date,
                'name': name,
                'amount_residual': direction * amount_ret2,
                'currency_id': invoice.company_id.currency_id.id,
            }))

        return res

    def validate_wh_iva_done(self):
        """ Method that check if wh vat is validated in invoice refund.
        @params: ids: list of invoices.
        return: True: the wh vat is validated.
                False: the wh vat is not validated.
        """
        for inv in self:
            if inv.move_type in ('out_invoice', 'out_refund') and not inv.wh_iva_id:
                riva = True
            else:
                riva = (not inv.wh_iva_id and True or
                        inv.wh_iva_id.state in ('posted') and True or False)
                if not riva:
                    raise UserError(
                        _('Error !\n¡La retención de IVA "% s" no está validada!' %
                          inv.wh_iva_id.code))
        return True


    def button_generate_wh_doc(self):
        context = dict(self._context)
        partner = self.env['res.partner']
        res = {}
        for inv in self:
            view_id = self.env['ir.ui.view'].search([
                ('name', '=', 'account.move._invoice,'
                              'wh.iva.customer')])
            context.update({
                'invoice_id': inv.id,
                'type': inv.move_type,
                'default_partner_id': partner._find_accounting_partner(
                    inv.partner_id).id,
                'default_name': inv.name,
                'view_id': view_id.id,
                'date_ret': inv.invoice_date,
                'date': inv.date,
            })
            res = {
                'name': _('Withholding vat customer'),
                'type': 'ir.actions.act_window',
                'res_model': 'account.wh.iva',
                'view_type': 'form',
                'view_id': False,
                'view_mode': 'form',
                'nodestroy': True,
                'target': 'current',
                'domain': "[('type', '=', '" + inv.move_type + "')]",
                'context': context
            }
        return res


    def action_cancel(self):
        """ Verify first in the invoice have a fiscal book associated and if
                        the state of the book is in cancel. """

        for inv_brw in self.browse():
            if not (not inv_brw.fb_id or (inv_brw.fb_id and inv_brw.fb_id.state == 'cancel')):
                raise UserError(
                    "Error! \n No puede cancelar una factura cargada en un Libro Fiscal procesado (%s). Necesitas ir a Libro fiscal y configure el libro en Cancelar. Entonces se podría cancelar la factura." % (
                        inv_brw.fb_id.state))


        """ Verify first if the invoice have a non cancel withholding iva doc.
        If it has then raise a error message. """
        for inv in self:
            if ((not inv.wh_iva_id) or (
                    inv.wh_iva_id and
                    inv.wh_iva_id.state == 'cancel')):
                super(AccountMove, self).action_cancel()
            else:
                raise UserError(
                    _("Error!\nNo puede cancelar una factura que no se encuentra cancelado"
                      "el doocumento de retención. Primero debe cancelar la factura"
                      "documento de retención y luego puede cancelar esto"
                      "factura"))
        return True

    # BEGIN OF REWRITING ISLR
    def check_invoice_type(self):
        """ This method check if the given invoice record is from a supplier
        """
        context = self._context or {}
        ids = isinstance(self.ids, (int)) and [self.ids] or self.ids
        inv_brw = self.browse(ids)
        return inv_brw.move_type in ('in_invoice', 'in_refund')

    def check_withholdable_concept(self):
        """ Check if the given invoice record is ISLR Withholdable
        """
        context = self._context or {}
        ids = isinstance(self.ids, (int)) and [self.ids] or self.ids
        '''Generate a new windows to change the income wh concept in current
        invoice line'''
        iwdi_obj = self.env['account.wh.islr.doc.invoices']
        return iwdi_obj._get_concepts(ids)

    @api.model
    def _create_doc_invoices(self, islr_wh_doc_id):
        """ This method link the invoices to be withheld
        with the withholding document.
        """
        # TODO: CHECK IF THIS METHOD SHOULD BE HERE OR IN THE ISLR WH DOC
        context = self._context or {}
        ids = isinstance(self.ids, (int)) and [self.ids] or self.ids
        doc_inv_obj = self.env['account.wh.islr.doc.invoices']
        iwhdi_ids = []
        for inv_id in ids:
            iwhdi_ids.append(doc_inv_obj.create(
                {'invoice_id': inv_id,
                 'islr_wh_doc_id': islr_wh_doc_id.id}))
        return iwhdi_ids

    @api.model
    def _create_islr_wh_doc(self):
        """ Function to create in the model islr_wh_doc
        """
        context = dict(self._context or {})
        ids = isinstance(self.ids, (int)) and [self.ids] or self.ids

        wh_doc_obj = self.env['account.wh.islr.doc']
        rp_obj = self.env['res.partner']

        # row = self.browse(ids)
        acc_part_id = rp_obj._find_accounting_partner(self.partner_id)

        res = False
        if not (self.move_type in ('out_invoice', 'in_invoice','out_refund', 'in_refund') and rp_obj._find_accounting_partner(
                self.company_id.partner_id).islr_withholding_agent):
            return True

        context['type'] = self.move_type
        wh_ret_code = wh_doc_obj.retencion_seq_get()
        if wh_ret_code:
            if self.move_type in ('out_invoice', 'out_refund'):
                journal = self.company_id.wh_islr_sale_journal_id
                acc_id = acc_part_id.property_account_receivable_id.id
                wh_type = 'out_invoice'
            else:  # ('in_invoice', 'in_refund')
                journal = self.company_id.wh_islr_purchase_journal_id
                acc_id = acc_part_id.property_account_payable_id.id
                wh_type = 'in_invoice'

            if not journal:
                raise UserError(_("Debe configurar un Diario de Retención ISLR en la compañía para el tipo de documento."))

            values = {
                'name': wh_ret_code,
                'partner_id': acc_part_id.id,
                'account_id': acc_id,
                'type': self.move_type,
                'journal_id': journal.id,
                'date_uid': self.date,
                'company_id': self.company_id.id,
                'date_ret': self.date
            }
            if self.company_id.propagate_invoice_date_to_income_withholding:
                values['date_uid'] = self.invoice_date

            islr_wh_doc_id = wh_doc_obj.create(values)
            iwdi_id = self._create_doc_invoices(islr_wh_doc_id)
            self.env['account.wh.islr.doc'].compute_amount_wh([islr_wh_doc_id])

            if self.company_id.automatic_income_wh is True:
                wh_doc_obj.write({'automatic_income_wh': True})
        else:
            raise UserError("Invalid action! \nNo se ha encontrado el numero de secuencia.")

        return islr_wh_doc_id

    def _refund_cleanup_lines(self, lines):
        """ Initializes the fields of the lines of a refund invoice
        """
        result = super(AccountMove, self)._refund_cleanup_lines(lines)
        for i, line in enumerate(lines):
            for name, field in line._fields.items():
                if name == 'concept_id' or name == 'apply_wh' or name == 'wh_xml_id':
                    result[i][2][name] = False

        return result

    def validate_wh_income_done(self):

        for inv in self.browse():
            if inv.move_type in ('out_invoice', 'out_refund') \
                    and not inv.islr_wh_doc_id:
                rislr = True
            else:
                rislr = not inv.islr_wh_doc_id and True or \
                        inv.islr_wh_doc_id.state in (
                            'done') and True or False
                if not rislr:
                    raise UserError(
                        "Error! \nThe Document you are trying to refund has a income withholding %s which is not yet validated!" % (
                            inv.islr_wh_doc_id.code))
        return True

    @api.model
    def _get_move_lines2(self,
                         to_wh,
                         pay_journal_id,
                         writeoff_acc_id,
                         writeoff_journal_id,
                         date,
                         name):

        context = self._context or {}
        rp_obj = self.env['res.partner']
        ids = isinstance(self.ids, (int)) and [self.ids] or self.ids

        res = []
        if not context.get('income_wh', False):
            return res

        inv_brw = self.browse(ids)
        acc_part_id = rp_obj._find_accounting_partner(inv_brw.partner_id)

        types = {'out_invoice': -1, 'in_invoice': 1, 'out_refund': 1,
                 'in_refund': -1, 'entry': 1}
        direction = types[inv_brw.move_type]

        for iwdl_brw in to_wh:
            rec = iwdl_brw.islr_wh_doc_id.journal_id.default_islr_account
            # concept_id.property_retencion_islr_receivable
            pay = iwdl_brw.islr_wh_doc_id.journal_id.default_islr_account
            if inv_brw.move_type in ('out_invoice', 'out_refund'):
                acc = rec and rec.id or False
            else:
                acc = pay and pay.id or False
            if not acc:
                raise UserError(
                    "Falta la cuenta en el impuesto! \nEl diario de [%s] tiene las cuentas faltantes. Por favor, rellene los campos que faltan para poder continuar" % (
                        iwdl_brw.islr_wh_doc_id.journal_id.name))

            res.append((0, 0, {
                'debit': direction * iwdl_brw.amount < 0 and - direction *
                         iwdl_brw.amount,
                'credit': direction * iwdl_brw.amount > 0 and direction *
                          iwdl_brw.amount,
                'account_id': acc,
                'partner_id': acc_part_id.id,
                'ref': inv_brw.display_name,
                'date': date,
                'currency_id': inv_brw.company_id.currency_id.id,
                'name': name.strip() + ' - ISLR: ' + iwdl_brw.iwdi_id.islr_wh_doc_id.name.strip()
            }))
        return res

    def llenar(self):
        temporal = self.env['account.move.line.resumen'].search([])
        temporal.with_context(force_delete=True).unlink()

        movimientos = self.env['account.move'].search([('move_type', '!=', 'entry'), ('state', '=', 'posted')])
        for det_m in movimientos:

            if det_m.move_type in ['in_invoice', 'in_refund', 'in_receipt']:
                type_tax_use = 'purchase'
                porcentaje_ret = det_m.partner_id.wh_iva_purchase_rate    # Tasa configurada en el proveedor
            elif det_m.move_type in ['out_invoice', 'out_refund', 'out_receipt']:
                type_tax_use = 'sale'
                porcentaje_ret = det_m.company_id.wh_iva_sale_rate  # Tasa configurada en la compañía
            else:
                type_tax_use = False
                porcentaje_ret = 0
            if det_m.move_type == 'in_invoice' or det_m.move_type == 'out_invoice':
                tipo_doc = "01"
            if det_m.move_type == 'in_refund' or det_m.move_type == 'out_refund':
                tipo_doc = "03"
            if det_m.move_type == 'in_receipt' or det_m.move_type == 'out_receipt':
                tipo_doc = "02"

            if det_m.move_type in ('in_invoice', 'in_refund', 'in_receipt', 'out_receipt', 'out_refund', 'out_invoice'):
                lista_impuesto = det_m.env['account.tax'].search([('type_tax_use', '=', type_tax_use)])
                # ('aliquot','not in',('general','exempt')
                base = 0
                total = 0
                total_impuesto = 0
                total_exento = 0
                alicuota_adicional = 0
                alicuota_reducida = 0
                alicuota_general = 0
                base_general = 0
                base_reducida = 0
                base_adicional = 0
                retenido_general = 0
                retenido_reducida = 0
                retenido_adicional = 0
                valor_iva = 0

                for det_tax in lista_impuesto:
                    tipo_alicuota = det_tax.appl_type

                    # raise UserError(_('tipo_alicuota: %s')%tipo_alicuota)
                    det_lin = det_m.invoice_line_ids.search([('tax_ids', '=', det_tax.id), ('move_id', '=', det_m.id)])
                    if det_lin:
                        for det_fac in det_lin:  # USAR AQUI ACOMULADORES
                            if det_m.state != "cancel":
                                base = base + det_fac.price_subtotal
                                total = total + det_fac.price_total
                                id_impuesto = det_fac.tax_ids.id
                                total_impuesto = total_impuesto + (det_fac.price_total - det_fac.price_subtotal)
                                if tipo_alicuota == "general":
                                    alicuota_general = alicuota_general + (det_fac.price_total - det_fac.price_subtotal)
                                    base_general = base_general + det_fac.price_subtotal
                                    valor_iva = det_fac.tax_ids.amount
                                if tipo_alicuota == "exento":
                                    total_exento = total_exento + det_fac.price_subtotal
                                if tipo_alicuota == "reducido":
                                    alicuota_reducida = alicuota_reducida + (
                                                det_fac.price_total - det_fac.price_subtotal)
                                    base_reducida = base_reducida + det_fac.price_subtotal
                                if tipo_alicuota == "adicional":
                                    alicuota_adicional = alicuota_adicional + (
                                                det_fac.price_total - det_fac.price_subtotal)
                                    base_adicional = base_adicional + det_fac.price_subtotal
                        total_ret_iva = (total_impuesto * porcentaje_ret) / 100
                        retenido_general = (alicuota_general * porcentaje_ret) / 100
                        retenido_reducida = (alicuota_reducida * porcentaje_ret) / 100
                        retenido_adicional = (alicuota_adicional * porcentaje_ret) / 100
                if det_m.move_type == 'in_refund' or det_m.move_type == 'out_refund':
                    base = -1 * base
                    total = -1 * total
                    total_impuesto = -1 * total_impuesto
                    alicuota_general = -1 * alicuota_general
                    valor_iva = -1 * valor_iva
                    total_exento = -1 * total_exento
                    alicuota_reducida = -1 * alicuota_reducida
                    alicuota_adicional = -1 * alicuota_adicional
                    total_ret_iva = -1 * total_ret_iva
                    base_adicional = -1 * base_adicional
                    base_reducida = -1 * base_reducida
                    base_general = -1 * base_general
                    retenido_general = -1 * retenido_general
                    retenido_reducida = -1 * retenido_reducida
                    retenido_adicional = -1 * retenido_adicional

                values = {
                    'total_con_iva': total,
                    'total_base': base,
                    'total_valor_iva': total_impuesto,
                    'tax_id': det_fac.tax_ids.id,
                    'invoice_id': det_m.id,
                    'vat_ret_id': det_m.vat_ret_id.id,
                    'nro_comprobante': det_m.vat_ret_id.name,
                    'porcentaje_ret': porcentaje_ret,
                    'total_ret_iva': total_ret_iva,
                    'type': det_m.move_type,
                    'state': det_m.state,
                    'state_voucher_iva': det_m.vat_ret_id.state,
                    'tipo_doc': tipo_doc,
                    'total_exento': total_exento,
                    'alicuota_reducida': alicuota_reducida,
                    'alicuota_adicional': alicuota_adicional,
                    'alicuota_general': alicuota_general,
                    'fecha_fact': det_m.invoice_date,
                    'fecha_comprobante': det_m.vat_ret_id.voucher_delivery_date,
                    'base_adicional': base_adicional,
                    'base_reducida': base_reducida,
                    'base_general': base_general,
                    'retenido_general': retenido_general,
                    'retenido_reducida': retenido_reducida,
                    'retenido_adicional': retenido_adicional,
                }
                det_m.env['account.move.line.resumen'].create(values)

    def suma_alicuota_iguales_iva(self):
        # raise UserError(_('xxx = %s')%self.wh_iva_id)
        for rec in self:
            if rec.move_type in ['in_invoice', 'in_refund', 'in_receipt']:
                type_tax_use = 'purchase'
                porcentaje_ret = rec.partner_id.wh_iva_purchase_rate          # Proveedor
            elif rec.move_type in ['out_invoice', 'out_refund', 'out_receipt']:
                type_tax_use = 'sale'
                porcentaje_ret = rec.company_id.wh_iva_sale_rate    # Compañía
            else:
                type_tax_use = False
                porcentaje_ret = 0
            if rec.move_type == 'in_invoice' or rec.move_type == 'out_invoice':
                tipo_doc = "01"
            if rec.move_type == 'in_refund' or rec.move_type == 'out_refund':
                tipo_doc = "03"
            if rec.move_type == 'in_receipt' or rec.move_type == 'out_receipt':
                tipo_doc = "02"

            if rec.move_type in ('in_invoice', 'in_refund', 'in_receipt', 'out_receipt', 'out_refund', 'out_invoice'):
                # ****** AQUI VERIFICA SI LAS LINEAS DE FACTURA TIENEN ALICUOTAS *****
                verf = self.invoice_line_ids.filtered(
                lambda line: line.display_type not in ('line_section', 'line_note'))
                # raise UserError(_('verf= %s')%verf)
                for det_verf in verf:
                    # raise UserError(_('det_verf.tax_ids.id= %s')%det_verf.tax_ids.id)
                    if not det_verf.tax_ids:
                        raise UserError(_('Las Lineas de la Factura deben tener un tipo de alicuota o impuestos'))
                # ***** FIN VERIFICACION
                lista_impuesto = self.env['account.tax'].search([('type_tax_use', '=', type_tax_use),('type_tax','=','iva')])
                # ('aliquot','not in',('general','exempt')
                base = 0
                total = 0
                total_impuesto = 0
                total_exento = 0
                alicuota_adicional = 0
                alicuota_reducida = 0
                alicuota_general = 0
                base_general = 0
                base_reducida = 0
                base_adicional = 0
                retenido_general = 0
                retenido_reducida = 0
                retenido_adicional = 0
                valor_iva = 0

                for det_tax in lista_impuesto:
                    tipo_alicuota = det_tax.appl_type

                    # raise UserError(_('tipo_alicuota: %s')%tipo_alicuota)
                    if det_tax.type_tax == 'iva':
                        det_lin = self.invoice_line_ids.search([('tax_ids', 'in', det_tax.id)])
                        if det_lin:
                            for det_fac in det_lin:  # USAR AQUI ACOMULADORES
                                if self.state != "cancel":
                                    base = base + det_fac.price_subtotal
                                    total = total + det_fac.price_total
                                    total_impuesto = total_impuesto + (det_fac.price_total - det_fac.price_subtotal)
                                    if tipo_alicuota == "general":
                                        alicuota_general = alicuota_general + (det_fac.price_total - det_fac.price_subtotal)
                                        base_general = base_general + det_fac.price_subtotal
                                        valor_iva = det_tax.amount
                                    if tipo_alicuota == "exento":
                                        total_exento = total_exento + det_fac.price_subtotal
                                    if tipo_alicuota == "reducido":
                                        alicuota_reducida = alicuota_reducida + (det_fac.price_total - det_fac.price_subtotal)
                                        base_reducida = base_reducida + det_fac.price_subtotal
                                    if tipo_alicuota == "adicional":
                                        alicuota_adicional = alicuota_adicional + (det_fac.price_total - det_fac.price_subtotal)
                                        base_adicional = base_adicional + det_fac.price_subtotal
                            total_ret_iva = (total_impuesto * porcentaje_ret) / 100
                            retenido_general = (alicuota_general * porcentaje_ret) / 100
                            retenido_reducida = (alicuota_reducida * porcentaje_ret) / 100
                            retenido_adicional = (alicuota_adicional * porcentaje_ret) / 100

                            if self.move_type == 'in_refund' or self.move_type == 'out_refund':
                                base = -1 * base
                                total = -1 * total
                                total_impuesto = -1 * total_impuesto
                                alicuota_general = -1 * alicuota_general
                                valor_iva = -1 * valor_iva
                                total_exento = -1 * total_exento
                                alicuota_reducida = -1 * alicuota_reducida
                                alicuota_adicional = -1 * alicuota_adicional
                                total_ret_iva = -1 * total_ret_iva
                                base_adicional = -1 * base_adicional
                                base_reducida = -1 * base_reducida
                                base_general = -1 * base_general
                                retenido_general = -1 * retenido_general
                                retenido_reducida = -1 * retenido_reducida
                                retenido_adicional = -1 * retenido_adicional

                            values = {
                                'total_con_iva': total,  # listo
                                'total_base': base,  # listo
                                'total_valor_iva': total_impuesto,  # listo
                                'tax_id': det_tax.id,
                                'invoice_id': self.id,
                                'vat_ret_id': self.wh_iva_id.id,
                                'nro_comprobante': self.wh_iva_id.name,
                                'porcentaje_ret': porcentaje_ret,
                                'total_ret_iva': total_ret_iva,
                                'type': self.move_type,
                                'state': self.state,
                                'state_voucher_iva': self.wh_iva_id.state,
                                'tipo_doc': tipo_doc,
                                'total_exento': total_exento,  # listo
                                'alicuota_reducida': alicuota_reducida,  # listo
                                'alicuota_adicional': alicuota_adicional,  # listo
                                'alicuota_general': alicuota_general,  # listo
                                'fecha_fact': self.invoice_date,
                                'fecha_comprobante': self.wh_iva_id.date,
                                'base_adicional': base_adicional,  # listo
                                'base_reducida': base_reducida,  # listo
                                'base_general': base_general,  # listo
                                'retenido_general': retenido_general,
                                'retenido_reducida': retenido_reducida,
                                'retenido_adicional': retenido_adicional,
                            }
                            self.env['account.move.line.resumen'].create(values)

                # raise UserError(_('valor_iva= %s')%valor_iva)

    def button_draft(self):
        super().button_draft()
        for selff in self:
            temporal = selff.env['account.move.line.resumen'].search([('invoice_id', '=', selff.id)])
            temporal.with_context(force_delete=True).unlink()


    def action_generate_wh_iva_manual(self):
            for inv in self:
                if inv.state != 'posted':
                    raise UserError(_("La factura debe estar publicada para generar la retención de IVA."))

                if inv.wh_iva_id:
                    raise UserError(_("Ya existe una retención de IVA asociada a esta factura."))

                if not inv.company_id.partner_id.wh_iva_agent or not inv.partner_id.wh_iva_agent:
                    raise UserError(_("La compañía o el proveedor no están configurados como agentes de retención de IVA."))

                hay_iva_gravado = any(
                    tax.amount > 0
                    for line in inv.line_ids
                    for tax in line.tax_ids
                )

                if not hay_iva_gravado:
                    raise UserError(_("La factura no tiene impuestos gravables para retención de IVA."))

                if not inv._withholdable_tax():
                    raise UserError(_("La factura no es retenible según la lógica definida."))

                inv.check_document_date()
                inv.check_invoice_dates()

                if inv.check_wh_apply():
                    inv.check_withholdable()
                    inv.action_wh_iva_supervisor()
                    inv.action_wh_iva_create()
                else:
                    raise UserError(_("La retención de IVA no aplica a esta factura."))

    @api.model
    def cron_sync_withholding_currency_rates(self):
        """
        Método para sincronizar las tasas de cambio de las retenciones con las tasas de sus facturas.
        Este método puede ser ejecutado por una acción planificada (cron).
        
        Busca retenciones de IVA, ISLR y Municipales que tengan una tasa diferente a la de su factura
        y actualiza los asientos contables correspondientes.
        """
        processed_count = 0
        error_count = 0
        
        try:
            _logger.info('Iniciando sincronización de tasas de retención...')
            
            # Procesar retenciones de IVA
            processed_iva, errors_iva = self._sync_iva_withholding_rates()
            processed_count += processed_iva
            error_count += errors_iva
            _logger.info('IVA: %s procesadas, %s errores', processed_iva, errors_iva)
            
            # Procesar retenciones de ISLR
            processed_islr, errors_islr = self._sync_islr_withholding_rates()
            processed_count += processed_islr
            error_count += errors_islr
            _logger.info('ISLR: %s procesadas, %s errores', processed_islr, errors_islr)
            
            # Procesar retenciones Municipales
            processed_municipal, errors_municipal = self._sync_municipal_withholding_rates()
            processed_count += processed_municipal
            error_count += errors_municipal
            _logger.info('Municipal: %s procesadas, %s errores', processed_municipal, errors_municipal)
            
            message = _(
                'Sincronización de tasas de retención completada. '
                'Retenciones procesadas: %s, Errores: %s'
            ) % (processed_count, error_count)
            
            _logger.info(message)
            
            return True
            
        except Exception as e:
            error_msg = _('Error en sincronización de tasas de retención: %s') % str(e)
            _logger.error(error_msg)
            raise UserError(error_msg)

    def _sync_iva_withholding_rates(self):
        """
        Sincroniza las tasas de cambio de las retenciones de IVA con sus facturas.
        """
        processed = 0
        errors = 0
        
        # Buscar líneas de retención de IVA con asientos contables
        wh_iva_line_obj = self.env['account.wh.iva.line']
        wh_lines = wh_iva_line_obj.search([
            ('move_id', '!=', False),
            ('invoice_id', '!=', False),
        ])
        
        _logger.info('IVA: Encontradas %s líneas de retención para revisar', len(wh_lines))
        
        checked_count = 0
        for wh_line in wh_lines:
            try:
                invoice = wh_line.invoice_id
                wh_move = wh_line.move_id
                
                if not invoice or not wh_move:
                    continue
                
                # Obtener tax_today de la factura
                if not hasattr(invoice, 'tax_today') or not invoice.tax_today:
                    continue
                
                invoice_rate = invoice.tax_today
                
                # Obtener tax_today del asiento de retención
                wh_rate = wh_move.tax_today if hasattr(wh_move, 'tax_today') else False
                
                # Mostrar información de las primeras 5 para debug
                if checked_count < 5:
                    _logger.info('IVA [%s/%s] - Factura: %s, tax_today Factura: %s, Asiento: %s, tax_today Retención: %s', 
                                 checked_count + 1, len(wh_lines), invoice.name, invoice_rate, 
                                 wh_move.name, wh_rate)
                    checked_count += 1
                
                # Si las tasas son diferentes (o el asiento no tiene tax_today), actualizar
                if not wh_rate or abs(invoice_rate - wh_rate) > 0.01:
                    _logger.info('IVA - Actualizando tax_today del asiento %s de %s a %s', 
                                wh_move.name, wh_rate, invoice_rate)
                    wh_move.write({'tax_today': invoice_rate})
                    processed += 1
                    
            except Exception as e:
                _logger.error('Error procesando retención IVA %s: %s', wh_line.id, str(e))
                errors += 1
                continue
        
        return processed, errors

    def _sync_islr_withholding_rates(self):
        """
        Sincroniza las tasas de cambio de las retenciones de ISLR con sus facturas.
        """
        processed = 0
        errors = 0
        
        # Buscar documentos de retención ISLR con facturas asociadas
        islr_doc_inv_obj = self.env['account.wh.islr.doc.invoices']
        islr_doc_invs = islr_doc_inv_obj.search([
            ('move_id', '!=', False),
            ('invoice_id', '!=', False),
        ])
        
        _logger.info('ISLR: Encontrados %s documentos de retención para revisar', len(islr_doc_invs))
        
        checked_count = 0
        for islr_inv in islr_doc_invs:
            try:
                invoice = islr_inv.invoice_id
                wh_move = islr_inv.move_id
                
                if not invoice or not wh_move:
                    continue
                
                # Obtener tax_today de la factura
                if not hasattr(invoice, 'tax_today') or not invoice.tax_today:
                    continue
                
                invoice_rate = invoice.tax_today
                
                # Obtener tax_today del asiento de retención
                wh_rate = wh_move.tax_today if hasattr(wh_move, 'tax_today') else False
                
                # Mostrar información de las primeras 5 para debug
                if checked_count < 5:
                    _logger.info('ISLR [%s/%s] - Factura: %s, tax_today Factura: %s, Asiento: %s, tax_today Retención: %s', 
                                 checked_count + 1, len(islr_doc_invs), invoice.name, invoice_rate, 
                                 wh_move.name, wh_rate)
                    checked_count += 1
                
                # Si las tasas son diferentes (o el asiento no tiene tax_today), actualizar
                if not wh_rate or abs(invoice_rate - wh_rate) > 0.01:
                    _logger.info('ISLR - Actualizando tax_today del asiento %s de %s a %s', 
                                wh_move.name, wh_rate, invoice_rate)
                    wh_move.write({'tax_today': invoice_rate})
                    processed += 1
                    
            except Exception as e:
                _logger.error('Error procesando retención ISLR %s: %s', islr_inv.id, str(e))
                errors += 1
                continue
        
        return processed, errors

    def _sync_municipal_withholding_rates(self):
        """
        Sincroniza las tasas de cambio de las retenciones Municipales con sus facturas.
        """
        processed = 0
        errors = 0
        
        # Buscar retenciones municipales con asientos contables
        wh_municipal_obj = self.env['account.wh.municipal']
        wh_municipals = wh_municipal_obj.search([
            ('move_id', '!=', False),
        ])
        
        _logger.info('Municipal: Encontradas %s retenciones para revisar', len(wh_municipals))
        
        checked_count = 0
        for wh_municipal in wh_municipals:
            try:
                invoice = wh_municipal.move_id
                
                if not invoice:
                    continue
                
                # Obtener tax_today de la factura
                if not hasattr(invoice, 'tax_today') or not invoice.tax_today:
                    continue
                
                invoice_rate = invoice.tax_today
                
                # Buscar el asiento de la retención
                if hasattr(wh_municipal, 'wh_move_id') and wh_municipal.wh_move_id:
                    wh_move = wh_municipal.wh_move_id
                else:
                    # Si no hay un campo directo, buscar asientos relacionados por fecha y partner
                    wh_move = self.env['account.move'].search([
                        ('partner_id', '=', invoice.partner_id.id),
                        ('date', '=', wh_municipal.date),
                        ('ref', 'ilike', 'Municipal'),
                    ], limit=1)
                
                if not wh_move:
                    continue
                
                # Obtener tax_today del asiento de retención
                wh_rate = wh_move.tax_today if hasattr(wh_move, 'tax_today') else False
                
                # Mostrar información de las primeras 5 para debug
                if checked_count < 5:
                    _logger.info('Municipal [%s/%s] - Factura: %s, tax_today Factura: %s, Asiento: %s, tax_today Retención: %s', 
                                 checked_count + 1, len(wh_municipals), invoice.name, invoice_rate, 
                                 wh_move.name, wh_rate)
                    checked_count += 1
                
                # Si las tasas son diferentes (o el asiento no tiene tax_today), actualizar
                if not wh_rate or abs(invoice_rate - wh_rate) > 0.01:
                    _logger.info('Municipal - Actualizando tax_today del asiento %s de %s a %s', 
                                wh_move.name, wh_rate, invoice_rate)
                    wh_move.write({'tax_today': invoice_rate})
                    processed += 1
                    
            except Exception as e:
                _logger.error('Error procesando retención Municipal %s: %s', wh_municipal.id, str(e))
                errors += 1
                continue
        
        return processed, errors

    def _get_invoice_currency_rate(self, invoice):
        """
        Obtiene la tasa de cambio de una factura.
        Intenta obtenerla de diferentes campos según la configuración del módulo.
        """
        if not invoice:
            return False
        
        # Intentar obtener la tasa de diferentes campos posibles
        rate = False
        source = None
        
        # Si hay módulo de dual currency, usar tax_today
        if hasattr(invoice, 'tax_today') and invoice.tax_today:
            rate = invoice.tax_today
            source = 'tax_today'
        # Si hay campo manual_currency_rate
        elif hasattr(invoice, 'manual_currency_rate') and invoice.manual_currency_rate:
            rate = invoice.manual_currency_rate
            source = 'manual_currency_rate'
        # Si hay campo currency_rate
        elif hasattr(invoice, 'currency_rate') and invoice.currency_rate:
            rate = invoice.currency_rate
            source = 'currency_rate'
        # Obtener de las líneas del asiento
        elif invoice.line_ids:
            for line in invoice.line_ids:
                if line.currency_id != line.company_currency_id and line.amount_currency and line.balance:
                    if line.amount_currency != 0:
                        calculated_rate = abs(line.balance / line.amount_currency)
                        if calculated_rate > 0:
                            rate = calculated_rate
                            source = 'calculated_from_lines'
                            break
        
        if rate:
            _logger.debug('Factura %s - Tasa obtenida: %s (fuente: %s)', invoice.name, rate, source)
        else:
            _logger.debug('Factura %s - No se pudo obtener tasa', invoice.name)
            
        return rate

    def _get_move_currency_rate(self, move):
        """
        Obtiene la tasa de cambio actual de un asiento contable.
        """
        if not move or not move.line_ids:
            return False
        
        rate = False
        for line in move.line_ids:
            if line.currency_id != line.company_currency_id and line.amount_currency and line.balance:
                if line.amount_currency != 0:
                    calculated_rate = abs(line.balance / line.amount_currency)
                    if calculated_rate > 0:
                        rate = calculated_rate
                        break
        
        if rate:
            _logger.debug('Asiento %s - Tasa obtenida: %s', move.name, rate)
        else:
            _logger.debug('Asiento %s - No se pudo obtener tasa', move.name)
            
        return rate

    def _update_move_currency_rate(self, move, new_rate):
        """
        Actualiza la tasa de cambio de un asiento contable.
        Recalcula todos los importes en moneda base según la nueva tasa.
        """
        if not move or not new_rate or move.state != 'posted':
            return False
        
        try:
            # Desbloquear el asiento para editarlo
            move.button_draft()
            
            # Actualizar las líneas del asiento
            for line in move.line_ids:
                if line.currency_id != line.company_currency_id and line.amount_currency:
                    # Recalcular el balance con la nueva tasa
                    new_balance = line.amount_currency * new_rate
                    
                    # Mantener el signo correcto
                    if line.balance < 0:
                        new_balance = -abs(new_balance)
                    else:
                        new_balance = abs(new_balance)
                    
                    line.write({
                        'debit': new_balance if new_balance > 0 else 0.0,
                        'credit': abs(new_balance) if new_balance < 0 else 0.0,
                        'balance': new_balance,
                    })
            
            # Volver a publicar el asiento
            move.action_post()
            
            return True
            
        except Exception as e:
            # Si hay error, intentar revertir a posted si es posible
            if move.state == 'draft':
                try:
                    move.action_post()
                except:
                    pass
            raise UserError(_('Error al actualizar tasa del asiento %s: %s') % (move.name, str(e)))

    def _recalculate_move_with_rate(self, move, invoice, new_rate):
        """
        Recalcula un asiento de retención que está en moneda local
        pero debe reflejar la tasa de la factura en moneda extranjera.
        """
        if not move or not new_rate or move.state != 'posted':
            return False
        
        try:
            _logger.info('Recalculando asiento %s con tasa %s de factura %s', 
                        move.name, new_rate, invoice.name)
            
            # Desbloquear el asiento para editarlo
            move.button_draft()
            
            # Obtener los montos en USD de la factura (si es que los hay)
            # Buscar si hay líneas con moneda extranjera que necesiten ajuste
            has_foreign_currency = False
            for line in move.line_ids:
                if line.currency_id and line.currency_id != line.company_currency_id:
                    has_foreign_currency = True
                    break
            
            # Si el asiento ya tiene moneda extranjera, actualizar con la nueva tasa
            if has_foreign_currency:
                for line in move.line_ids:
                    if line.currency_id != line.company_currency_id and line.amount_currency:
                        # Recalcular el balance con la nueva tasa
                        new_balance = line.amount_currency * new_rate
                        
                        # Mantener el signo correcto
                        if line.balance < 0:
                            new_balance = -abs(new_balance)
                        else:
                            new_balance = abs(new_balance)
                        
                        line.write({
                            'debit': new_balance if new_balance > 0 else 0.0,
                            'credit': abs(new_balance) if new_balance < 0 else 0.0,
                            'balance': new_balance,
                        })
            else:
                # Si no tiene moneda extranjera, calcular los montos USD basados en la tasa de la factura
                # y actualizar los montos en Bs
                for line in move.line_ids:
                    if line.balance != 0:
                        # Calcular el monto en USD dividiendo por la tasa actual (estimada)
                        # y luego recalcular con la nueva tasa
                        # Por ahora, solo lo dejamos como está ya que no tenemos el monto original en USD
                        _logger.debug('Línea %s sin moneda extranjera, balance actual: %s', 
                                     line.name, line.balance)
            
            # Volver a publicar el asiento
            move.action_post()
            
            return True
            
        except Exception as e:
            # Si hay error, intentar revertir a posted si es posible
            if move.state == 'draft':
                try:
                    move.action_post()
                except:
                    pass
            _logger.error('Error al recalcular asiento %s: %s', move.name, str(e))
            return False