from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo import _

class CreditNoteMotivoConfirm(models.TransientModel):
    _name = 'credit.note.motivo.confirm'
    _description = 'Confirmar motivos de NC existentes'

    motivo_list = fields.Text('Motivos ya utilizados')
    credit_notes = fields.Text('Notas de Crédito Asociadas')
    move_id = fields.Many2one('account.move', string='Factura')
    
    @api.depends('move_id')
    def _compute_credit_notes(self):
        for wizard in self:
            lines = []
            credit_notes = wizard.env['account.move'].search([
                ('reversed_entry_id', '=', wizard.move_id.id),
                ('move_type', 'in', ['out_refund', 'in_refund']),
                ('state', '!=', 'cancel'),
            ])
            for nc in credit_notes:
                motivo = nc.x_studio_motivo_de_devolucion or ''
                if nc.state == 'draft':
                    nc_label = "PENDIENTE POR APROBACIÓN"
                else:
                    nc_label = nc.name
                lines.append(f"{nc_label}: {motivo}")
            wizard.credit_notes = '\n'.join(lines)

    def action_confirm(self):
        # Llama al método original para crear la NC
        return self.move_id.with_context(skip_motivo_check=True).action_add_credit_note()