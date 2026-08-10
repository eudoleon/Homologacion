from odoo import models, fields, api
from odoo.exceptions import ValidationError

class ResPartner(models.Model):
    _inherit = 'res.partner'

    identification_id = fields.Char(string='Document ID')

    @api.constrains('identification_id')
    def _check_unique_identification_id(self):
        for rec in self:
            if rec.identification_id:
                cedula = ''.join(filter(str.isdigit, rec.identification_id))
                domain = [
                    ('identification_id', '!=', False),
                    ('active', '=', True),
                    ('id', '!=', rec.id)
                ]
                partners = self.search(domain)
                for partner in partners:
                    partner_cedula = ''.join(filter(str.isdigit, partner.identification_id or ''))
                    if partner_cedula == cedula:
                        raise ValidationError('Ya existe un contacto activo con este documento fiscal: %s (Asignado a: %s)' % (partner.identification_id, partner.name)) 