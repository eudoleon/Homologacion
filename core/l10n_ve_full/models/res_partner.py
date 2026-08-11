# -*- coding: UTF-8 -*-
# from email.policy import default

from odoo import fields, models, api
from odoo.exceptions import UserError
# from odoo.addons import decimal_precision as dp
import re

class ResPartner(models.Model):
    _inherit = 'res.partner'

    nationality = fields.Selection([
        ('V', 'Venezolano'),
        ('E', 'Extranjero'),
        ('P', 'Pasaporte')], string="Tipo Documento", default='V')
    identification_id = fields.Char(string='Documento de Identidad')
    value_parent = fields.Boolean(string='Valor parent_id', compute='compute_value_parent_id')
    people_type_individual = fields.Selection([
        ('pnre', 'PNRE Persona Natural Residente'),
        ('pnnr', 'PNNR Persona Natural No Residente')
    ], string='Tipo de Persona individual', default='pnre')
    people_type_company = fields.Selection([
        ('pjdo', 'PJDO Persona Jurídica Domiciliada'),
        ('pjnd', 'PJND Persona Jurídica No Domiciliada')], string='Tipo de Persona compañía', default='pjdo')
    rif = fields.Char(string='RIF')

    wh_iva_agent = fields.Boolean(
        '¿Es Agente de Retención (IVA)?',
        help="Indique si el socio es un agente de retención de IVA", default=True)

    wh_iva_rate = fields.Float(
        string='% Retención de IVA',
        help="Se coloca el porcentaje de la Tasa de retención de IVA", default=75.0) # Corregido 'default'

    vat_subjected = fields.Boolean('Declaración legal de IVA',
    help="Marque esta casilla si el socio está sujeto al IVA. Se utilizará para la declaración legal del IVA.", default=True)

    purchase_journal_id = fields.Many2one('account.journal','Diario de Compra para IVA', company_dependent=True,
                                        domain="[('is_iva_journal','=', True), ('company_id', '=', current_company_id)]")
    purchase_sales_id = fields.Many2one('account.journal', 'Diario de Venta para IVA', company_dependent=True,
                                        domain="[('is_iva_journal','=', True), ('company_id', '=', current_company_id)]")

    ## ISLR #######################
    islr_withholding_agent = fields.Boolean(
        '¿Agente de retención de ingresos?', default=True,
        help="Verifique si el partner es un agente de retención de ingresos")
    spn = fields.Boolean(
        '¿Es una sociedad de personas físicas?',
        help='Indica si se refiere a una sociedad de personas físicas.')
    islr_exempt = fields.Boolean(
        '¿Está exento de retención de ingresos?',
        help='Si el individuo está exento de retención de ingresos')
    purchase_islr_journal_id = fields.Many2one('account.journal', 'Diario de Compra para ISLR', company_dependent=True,
                                        domain="[('is_islr_journal','=', True), ('company_id', '=', current_company_id)]")
    sale_islr_journal_id = fields.Many2one('account.journal', 'Diario de Venta para ISLR', company_dependent=True,
                                        domain="[('is_islr_journal','=', True), ('company_id', '=', current_company_id)]")

    same_vat_partner_id = fields.Many2one('res.partner', string='Contacto con el mismo RIF',
                                          compute='_compute_same_rif_partner_id', store=False)

    # Municipal
    RIM = fields.Char(string="Registro de Información Municipal (RIM)", help="Campo para añadir el Registro de Información Municipal")
    porcentaje = fields.Float(string="% Retención Municipal", help="Campo para añadir el porcentaje de retención municipal.")
    purchase_municipal_journal_id = fields.Many2one('account.journal', 'Diario de Compra para Impuesto Municipal', company_dependent=True,
                                        domain="[('is_municipal_journal','=', True), ('company_id', '=', current_company_id)]", readonly=False)
    sale_municipal_journal_id = fields.Many2one('account.journal', 'Diario de Venta para Impuesto Municipal', company_dependent=True,
                                domain="[('is_municipal_journal','=', True), ('company_id', '=', current_company_id)]", readonly=False)


    contribuyente_seniat = fields.Selection([
        ('ordinario', 'Ordinario'),
        ('especial', 'Especial'),
        ('formal', 'Formal'),
        ('gobernamental', 'Gubernamental')], string="Contribuyente", default='ordinario')

    municipality_id = fields.Many2one('res.country.state.municipality', string='Municipio')
    parish_id = fields.Many2one('res.country.state.municipality.parish', 'Parroquia')

    @api.model
    def _address_fields(self):
        address_fields = set(super(ResPartner, self)._address_fields())
        address_fields.add('municipality_id')
        address_fields.add('parish_id')
        return list(address_fields)

    def _run_vat_checks(self, country, vat, partner_name='', validation='error'):
        country_code = country.code if country else False
        partner = self[:1]
        raw_vat = (vat or '').strip().upper()
        ve_prefix = bool(re.match(r'^[VEJGCP]', raw_vat))

        # En Venezuela la localización usa rif / identification_id y no la validación base_vat.
        if country_code == 'VE' or ve_prefix:
            if partner.company_type == 'company':
                return vat, country_code
            if partner.company_type == 'person':
                return vat, country_code

        return super()._run_vat_checks(country, vat, partner_name=partner_name, validation=validation)

    @staticmethod
    def _normalize_rif(field_value):
        if not field_value:
            return False
            
        cleaned = re.sub(r"[^a-zA-Z0-9]", "", field_value).upper()
        if not cleaned or cleaned[0] not in 'VEJGC':
            return re.sub(r"\s+", "", field_value).upper()
            
        letter = cleaned[0]
        digits = cleaned[1:]
        
        if len(digits) >= 2:
            return f"{letter}-{digits[:-1]}-{digits[-1]}"
            
        return f"{letter}-{digits}"

    @staticmethod
    def _normalize_identification(field_value, nationality=None):
        if not field_value:
            return nationality, False

        value = re.sub(r"\s+", "", field_value).upper()
        if nationality in ('V', 'E') or (value and value[0] in ('V', 'E')):
            detected_nationality = value[0] if value and value[0] in ('V', 'E') else nationality
            numeric_value = re.sub(r"\D", "", value)
            return detected_nationality, numeric_value

        return nationality, value


    @api.model_create_multi
    def create(self, vals_list):
        for val in vals_list:
            company_type = val.get('company_type')

            if company_type == 'person':
                nationality, ident_value = self._normalize_identification(
                    val.get('identification_id') or (val.get('vat') if not val.get('rif') else False),
                    val.get('nationality'),
                )
                if nationality:
                    val['nationality'] = nationality
                val['identification_id'] = ident_value
                
                if val.get('rif'):
                    rif_val = self._normalize_rif(val.get('rif'))
                    val['rif'] = rif_val
                    val['vat'] = rif_val
                else:
                    val['vat'] = False
                    val['rif'] = False

                if ident_value and val.get('nationality'):
                    self.validation_document_ident(ident_value, val['nationality'])
                    if not self.validate_ci_duplicate(ident_value, True):
                        raise UserError('El cliente o proveedor ya se encuentra registrado con el Documento: %s' % ident_value)

            if company_type == 'company':
                rif_val = self._normalize_rif(val.get('rif') or val.get('vat'))
                val['rif'] = rif_val
                if rif_val:
                    if self.validate_rif_duplicate(rif_val, self):
                        raise UserError('El cliente o proveedor ya se encuentra registrado con el rif: %s' % rif_val)
                val['vat'] = rif_val

            if val.get('email'):
                if not self.validate_email_addrs(val.get('email'), 'email'):
                    raise UserError('El email es incorrecto.')
        return super(ResPartner, self).create(vals_list)

    def write(self, vals):
        company_type = vals.get('company_type') or (self[:1].company_type if self else False)

        if company_type == 'person':
            raw_identification = vals.get('identification_id')
            if not raw_identification and 'vat' in vals and 'rif' not in vals:
                raw_identification = vals.get('vat')

            if raw_identification or 'identification_id' in vals:
                nationality, ident_value = self._normalize_identification(
                    raw_identification,
                    vals.get('nationality') or (self[:1].nationality if self else False),
                )
                if nationality:
                    vals['nationality'] = nationality
                vals['identification_id'] = ident_value
                
            if 'rif' in vals:
                if vals.get('rif'):
                    rif_val = self._normalize_rif(vals.get('rif'))
                    vals['rif'] = rif_val
                    vals['vat'] = rif_val
                else:
                    vals['rif'] = False
                    vals['vat'] = False
            elif 'vat' in vals:
                if not vals.get('vat'):
                    vals['rif'] = False
                    vals['vat'] = False
        else:
            raw_rif = vals.get('rif') or vals.get('vat')
            if raw_rif:
                rif_val = self._normalize_rif(raw_rif)
                vals['rif'] = rif_val
                vals['vat'] = rif_val

        if vals.get('email'):
            if not self.validate_email_addrs(vals.get('email'), 'email'):
                raise UserError('El email es incorrecto.')

        return super(ResPartner, self).write(vals)

    @api.depends('rif', 'company_id')
    def _compute_same_rif_partner_id(self):
        for partner in self:
            partner_id = partner._origin.id
            Partner = self.with_context(active_test=False).sudo()
            domain = [
                ('rif', '=', partner.rif),
                ('company_id', 'in', [False, partner.company_id.id]),
            ]
            if partner_id:
                domain += [('id', '!=', partner_id), '!', ('id', 'child_of', partner_id)]
            partner.same_vat_partner_id = bool(partner.rif) and not partner.parent_id and Partner.search(domain, limit=1)

    @api.constrains('rif')
    def _check_rif_format(self):
        for rec in self:
            if not rec.rif:
                continue
            if not self.validate_rif_er(rec.rif):
                raise UserError(
                    'El RIF tiene el formato incorrecto o está incompleto (debe incluir el dígito final). '
                    'Ej: J-01234567-8, V-01234567-8, E-01234567-8'
                )

    @api.constrains('vat', 'country_id')
    def check_vat(self):
        # Solo delegar a base_vat empresas con país extranjero explícito y sin RIF venezolano
        partners_to_check = self.browse()
        for rec in self:
            # Personas: usan cédula de identidad, no RIF
            if rec.company_type == 'person':
                continue
            # Sin país definido: no hay forma de determinar el validador
            if not rec.country_id:
                continue
            # País venezolano: validación propia mediante validate_rif_er
            if rec.country_id.code == 'VE':
                continue
            # Empresa con RIF venezolano (V/E/J/G/C prefix): validación propia
            if rec.rif:
                continue
            partners_to_check |= rec
        if partners_to_check:
            super(ResPartner, partners_to_check).check_vat()

    @api.onchange('rif')
    def _onchange_rif(self):
        for rec in self:
            if rec.rif:
                rec.vat = rec.rif.upper()
            else:
                rec.vat = ''

    @api.onchange('identification_id', 'nationality')
    def _onchange_identification_id(self):
        for rec in self:
            if rec.company_type != 'person':
                continue
            if rec.identification_id:
                nationality, ident_value = rec._normalize_identification(rec.identification_id, rec.nationality)
                rec.nationality = nationality or rec.nationality
                rec.identification_id = ident_value

    @api.depends('company_type', 'parent_id.active')
    def compute_value_parent_id(self):
        for rec in self:
            rec.value_parent = rec.parent_id.active if rec.parent_id else False

    @staticmethod
    def validation_document_ident(valor, nationality):
        if valor:
            if nationality in ('V', 'E'):
                if len(valor) in (7, 8):
                    if not valor.isdigit():
                        raise UserError('La Cédula solo debe ser numérica.')
                else:
                    raise UserError('La Cedula de Identidad no puede ser menor que 7 cifras ni mayor a 8.')
            if nationality == 'P':
                if not (10 <= len(valor) <= 20):
                    raise UserError('El Pasaporte debe tener entre 10 y 20 caracteres.')

    def validate_ci_duplicate(self, valor, create=False):
        if not valor: return True
        partner_2 = self.search([('identification_id', '=', valor)])
        if partner_2:
            return False
        return True

    @api.onchange('company_type')
    def change_country_id_partner(self):
        if self.company_type == 'person':
            venezuela = self.env.ref('base.ve', raise_if_not_found=False)
            if venezuela:
                self.country_id = venezuela.id
            else:
                self.country_id = 238
        elif self.company_type == 'company':
            self.country_id = False

    @staticmethod
    def validate_rif_er(field_value):
        normalized_value = ResPartner._normalize_rif(field_value)
        if not normalized_value:
            return {}
        rif_obj = re.compile(r"^[VEJGC]-[0-9]{9}-[0-9]{1}$", re.X)
        rif_obj_2 = re.compile(r"^[VEJGC]-[0-9]{8}-[0-9]{1}$", re.X)
        if rif_obj.search(normalized_value) or rif_obj_2.search(normalized_value):
            return {'rif': normalized_value}
        return {}

    def validate_rif_duplicate(self, valor, res):
        domain = [('rif', '=', valor)]
        if self.ids:
            domain.append(('id', 'not in', self.ids))
        elif res and res.ids:
            domain.append(('id', 'not in', res.ids))
            
        partner = self.env['res.partner'].search(domain)
        return bool(partner)

    @staticmethod
    def validate_email_addrs(email, field):
        if not email: return {}
        mail_obj = re.compile(r"[\w.%+-]+@[\w.-]+\.[a-zA-Z]{2,3}")
        if mail_obj.search(email):
            return {field: email}
        return {}