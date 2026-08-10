# -*- coding: utf-8 -*-
from odoo import models, fields, _

class AccountMoveReversalInherit(models.TransientModel):
    _inherit = 'account.move.reversal'

    correlative = fields.Char(
        'Número de Control', 
        size=32,
        help="Número de control asociado a la factura original. Se generará uno nuevo si es necesario.",
        store=True
    )

    supplier_invoice_number = fields.Char(
        string='Número de factura del proveedor',
        size=64,
        store=True
    )

    def reverse_moves(self):
        moves = self.env['account.move'].browse(self.env.context['active_ids']) if self.env.context.get('active_model') == 'account.move' else self.move_id

        # Crear valores por defecto para la reversión.
        default_values_list = []
        for move in moves:
            default_vals = self._prepare_default_reversal(move)
            default_vals['correlative'] = ""  # Se deja en blanco en la reversión
            default_vals['supplier_invoice_number'] = move.supplier_invoice_number  # Transferimos el número de factura del proveedor
            default_values_list.append(default_vals)

        batches = [
            [self.env['account.move'], [], True],   # Movimientos a cancelar.
            [self.env['account.move'], [], False],  # Otros.
        ]
        for move, default_vals in zip(moves, default_values_list):
            is_auto_post = bool(default_vals.get('auto_post'))
            is_cancel_needed = not is_auto_post and self.refund_method in ('cancel', 'modify')
            batch_index = 0 if is_cancel_needed else 1
            batches[batch_index][0] |= move
            batches[batch_index][1].append(default_vals)

        # Manejo de reversión
        moves_to_redirect = self.env['account.move']
        for moves, default_values_list, is_cancel_needed in batches:
            new_moves = moves._reverse_moves(default_values_list, cancel=is_cancel_needed)

            if new_moves.state != 'draft':
                new_moves.already_posted_iva()

            if self.refund_method == 'modify':
                moves_vals_list = []
                for move in moves.with_context(include_business_fields=True):
                    vals = move.copy_data({'date': self.date or move.date})[0]
                    vals['correlative'] = ""
                    vals['supplier_invoice_number'] = move.supplier_invoice_number
                    moves_vals_list.append(vals)

                new_moves = self.env['account.move'].create(moves_vals_list)

                # ✅ Ajuste también para movimientos creados manualmente
                for move in new_moves:
                    for line in move.line_ids:
                        if line.currency_id and line.amount_currency:
                            if (line.debit and line.amount_currency < 0) or (line.credit and line.amount_currency > 0):
                                line.amount_currency *= -1

            moves_to_redirect |= new_moves

        # Crear acción para redirigir a la vista de los movimientos creados
        action = {
            'name': _('Reverse Moves'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
        }
        if len(moves_to_redirect) == 1:
            action.update({
                'view_mode': 'form',
                'res_id': moves_to_redirect.id,
            })
        else:
            action.update({
                'view_mode': 'tree,form',
                'domain': [('id', 'in', moves_to_redirect.ids)],
            })
        return action
