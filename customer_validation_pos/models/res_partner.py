import re
from odoo import models, api, _
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.constrains('name', 'phone', 'email', 'vat', 'street')
    def _check_pos_customer_validation(self):
        for partner in self:
            # Solo validar si se está creando/editando desde el flujo de POS
            if not self.env.context.get('in_pos_partner_edit'):
                continue

            pos_config = None
            pos_config_id = self.env.context.get('pos_config_id')
            if pos_config_id:
                pos_config = self.env['pos.config'].browse(pos_config_id)
            if not pos_config or not pos_config.exists():
                session = self.env['pos.session'].search([
                    ('user_id', '=', self.env.uid),
                    ('state', '=', 'opened'),
                ], limit=1)
                if session:
                    pos_config = session.config_id

            if not pos_config:
                continue

            # 1. Nombre
            if pos_config.required_name and (not partner.name or not partner.name.strip()):
                raise ValidationError(_("¡Se requiere el nombre del cliente!"))
            if pos_config.unique_name and partner.name:
                duplicate = self.search([
                    ('name', '=ilike', partner.name.strip()),
                    ('id', '!=', partner.id),
                ], limit=1)
                if duplicate:
                    raise ValidationError(_("El nombre '%s' ya está registrado en otro cliente.") % partner.name)

            # 2. Teléfono (permite formato local de 10-11 dígitos e ignora prefijo país +58)
            if pos_config.required_phone and (not partner.phone or not partner.phone.strip()):
                raise ValidationError(_("¡Se requiere el número de teléfono del cliente!"))
            if partner.phone:
                clean_phone = re.sub(r'\D', '', partner.phone)
                digits = clean_phone[2:] if clean_phone.startswith('58') else clean_phone
                if len(digits) < 10:
                    raise ValidationError(_("¡El número de teléfono debe contener al menos 10 u 11 dígitos numéricos! (Dígitos ingresados: %s)") % len(digits))
            if pos_config.unique_phone and partner.phone:
                clean_phone = re.sub(r'\D', '', partner.phone)
                digits = clean_phone[2:] if clean_phone.startswith('58') else clean_phone
                duplicate = self.search([
                    '|', ('phone', 'in', [partner.phone, clean_phone, digits]),
                    ('phone', 'like', digits),
                    ('id', '!=', partner.id),
                ], limit=1)
                if duplicate:
                    raise ValidationError(_("El teléfono '%s' ya está registrado en el cliente %s.") % (partner.phone, duplicate.name))

            # 3. Correo
            if pos_config.required_email and (not partner.email or not partner.email.strip()):
                raise ValidationError(_("¡Se requiere el correo electrónico del cliente!"))
            if pos_config.unique_email and partner.email:
                duplicate = self.search([
                    ('email', '=ilike', partner.email.strip()),
                    ('id', '!=', partner.id),
                ], limit=1)
                if duplicate:
                    raise ValidationError(_("El correo electrónico '%s' ya está registrado en el cliente %s.") % (partner.email, duplicate.name))

            # 4. Cédula / RIF (Validación venezolana y sincronización de VAT)
            is_person = partner.company_type == 'person'
            if is_person:
                ci = getattr(partner, 'identification_id', False) or partner.vat
                if pos_config.required_vat and (not ci or not str(ci).strip()):
                    raise ValidationError(_("¡Se requiere la Cédula de Identidad del cliente!"))
                if ci:
                    clean_ci = re.sub(r'\D', '', str(ci))
                    if not (6 <= len(clean_ci) <= 9):
                        raise ValidationError(_("¡La Cédula '%s' no es válida! Debe tener entre 6 y 9 dígitos numéricos.") % ci)
                    nat = getattr(partner, 'nationality', 'V') or 'V'
                    partner.vat = f"{nat}-{clean_ci}"
                    if hasattr(partner, 'people_type_individual') and not partner.people_type_individual:
                        partner.people_type_individual = 'pnre'
                if pos_config.unique_vat and ci:
                    clean_ci = re.sub(r'\D', '', str(ci))
                    duplicate = self.search([
                        '|', ('identification_id', '=', str(ci).strip()),
                        '|', ('vat', 'ilike', clean_ci),
                        ('identification_id', '=', clean_ci),
                        ('id', '!=', partner.id),
                    ], limit=1)
                    if duplicate:
                        raise ValidationError(_("La Cédula '%s' ya está registrada en el cliente %s.") % (ci, duplicate.name))
            else:
                rif = getattr(partner, 'rif', False) or partner.vat
                if pos_config.required_vat and (not rif or not str(rif).strip()):
                    raise ValidationError(_("¡Se requiere el RIF de la empresa!"))
                if rif:
                    clean_rif = str(rif).strip().upper()
                    partner.vat = clean_rif
                    if hasattr(partner, 'people_type_company') and not partner.people_type_company:
                        partner.people_type_company = 'pjdo'
                if pos_config.unique_vat and rif:
                    duplicate = self.search([
                        '|', ('rif', '=ilike', str(rif).strip()),
                        ('vat', '=ilike', str(rif).strip()),
                        ('id', '!=', partner.id),
                    ], limit=1)
                    if duplicate:
                        raise ValidationError(_("El RIF '%s' ya está registrado en el cliente %s.") % (rif, duplicate.name))

            # 5. Dirección (Street)
            if pos_config.required_street and (not partner.street or not partner.street.strip()):
                raise ValidationError(_("¡Se requiere la dirección fiscal del cliente!"))
            if pos_config.unique_street and partner.street:
                duplicate = self.search([
                    ('street', '=ilike', partner.street.strip()),
                    ('id', '!=', partner.id),
                ], limit=1)
                if duplicate:
                    raise ValidationError(_("La dirección '%s' ya está registrada en el cliente %s.") % (partner.street, duplicate.name))
