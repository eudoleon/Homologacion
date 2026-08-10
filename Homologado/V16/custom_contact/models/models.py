# -*- coding: utf-8 -*-
from odoo import models, fields

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

    def write(self, vals):
        if 'id_type' in vals and 'vat' in vals:
            existing_partner = self.env['res.partner'].search([
                ('id_type', '=', vals['id_type']),
                ('vat', '=', vals['vat']),
                ('id', '!=', self.id)
            ], limit=1)
            if existing_partner:
                raise models.ValidationError('Ya existe un cliente con el mismo tipo de identificación y número de documento.')
        return super(ResPartner, self).write(vals)
    #prueba  