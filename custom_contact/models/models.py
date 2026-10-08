# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    id_type = fields.Selection([
        ('J', 'J'),
        ('V', 'V'),
        ('G', 'G'),
        ('P', 'P'),
        ('C', 'C'),
        ('E', 'E')
    ], string='Tipo de Identificación')

    @api.constrains('id_type', 'vat')
    def _check_unique_id_type_vat(self):
        for partner in self:
            if partner.id_type and partner.vat:
                domain = [
                    ('id_type', '=', partner.id_type),
                    ('vat', '=', partner.vat),
                    ('id', '!=', partner.id),
                ]
                if self.search_count(domain, limit=1):
                    raise ValidationError(
                        _('Ya existe un contacto con el mismo tipo de identificación (%s) y número de documento (%s).')
                        % (partner.id_type, partner.vat)
                    )