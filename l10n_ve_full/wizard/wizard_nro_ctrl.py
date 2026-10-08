# coding: utf-8

from odoo import models, fields, _
from odoo.exceptions import UserError


class WizNroctrl(models.TransientModel):
    _name = 'wiz.nroctrl'
    _description = "Wizard que cambia el número de control de la factura."

    name = fields.Char(string='Número de Control', required=True)
    sure = fields.Boolean(string='¿Estas seguro?')

    def set_noctrl(self):
        """ Change control number of the invoice
        """
        self.ensure_one()
        if not self.sure:
            raise UserError("Error! \nConfirme que desea hacer esto marcando la casilla opción")

        inv_obj = self.env['account.move']
        n_ctrl = self.name

        active_ids = self.env.context.get('active_ids', [])
        active_moves = inv_obj.browse(active_ids).exists()
        if not active_moves:
            raise UserError("Error! \nNo se encontró ninguna factura para actualizar")

        duplicate_count = inv_obj.search_count([
            ('correlative', '=', n_ctrl),
            ('id', 'not in', active_moves.ids),
        ])
        if duplicate_count:
            raise UserError("Error! \nEl Numero de Control ya Existe")

        vals = {'correlative': n_ctrl}
        # Keep backward compatibility if another inherited module still defines this field.
        if 'nro_ctrl' in inv_obj._fields:
            vals['nro_ctrl'] = n_ctrl

        active_moves.write(vals)
        return {'type': 'ir.actions.act_window_close'}
