from odoo import models, fields, api
from datetime import date
from odoo.exceptions import UserError

class PosOrderVatRetention(models.Model):
    _name = 'pos.order.vat.retention'
    _description = 'Retención de IVA en Pedido POS'

    order_id = fields.Many2one('pos.order', string='Pedido POS', required=True, ondelete='cascade')
    retention_date = fields.Date(string='Fecha de Retención', default=fields.Date.context_today)
    comprobante_number = fields.Char(string='Nro de Comprobante')
    amount_retained = fields.Monetary(string='Monto Retenido')
    currency_id = fields.Many2one(related='order_id.currency_id', store=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            order = self.env['pos.order'].browse(vals.get('order_id'))
            if order.vat_retention_move_id and order.vat_retention_move_id.state != 'draft':
                raise UserError("No se pueden agregar líneas de retención si el asiento ya está confirmado.")
        return super().create(vals_list)

    def write(self, vals):
        for rec in self:
            if rec.order_id.vat_retention_move_id and rec.order_id.vat_retention_move_id.state != 'draft':
                raise UserError("No se pueden modificar líneas de retención si el asiento ya está confirmado.")
        return super().write(vals)

    def unlink(self):
        for rec in self:
            if rec.order_id.vat_retention_move_id and rec.order_id.vat_retention_move_id.state != 'draft':
                raise UserError("No se pueden eliminar líneas de retención si el asiento ya está confirmado.")
        return super().unlink()

class PosOrder(models.Model):
    _inherit = 'pos.order'

    vat_retention_ids = fields.One2many('pos.order.vat.retention', 'order_id', string='Retenciones de IVA')
    vat_retention_move_id = fields.Many2one('account.move', string='Asiento de Retención IVA')
    vat_retention_move_state = fields.Selection(
        related='vat_retention_move_id.state',
        string='Estado del Asiento de Retención',
        store=True
    )

    def action_generate_vat_retention(self):
        for order in self:
            if order.vat_retention_move_id:
                raise UserError("Ya existe un asiento de retención asociado a este pedido.")

            # Validación para ticket_fiscal
            if not order.ticket_fiscal:
                raise UserError("No se puede generar la retención porque el ticket fiscal no está establecido.")

            company = order.company_id
            if not company or not company.vat_retention_rate:
                raise UserError("La compañía no tiene porcentaje de retención definido.")

            retention_rate = company.vat_retention_rate / 100.0
            vat_tax = order.amount_tax  # Usar el campo de la orden directamente

            retained_amount = vat_tax * retention_rate

            # Crear la retención
            retention = self.env['pos.order.vat.retention'].create({
                'order_id': order.id,
                'amount_retained': retained_amount,
                'retention_date': date.today(),
                # El número de comprobante se puede completar después
            })

            # Crear el asiento contable en borrador con la fecha de la retención
            company = order.company_id
            account_iva = company.account_vat_retention_id
            account_payable = company.account_payable_retention_id

            if not account_iva or not account_payable:
                raise UserError("Debe configurar las cuentas de IVA Retenido y Cuenta por Pagar en la compañía.")
            
            partner = order.partner_id

            move_vals = {
                'ref': f'Retención IVA POS {order.name}',
                'date': retention.retention_date,  # Usar la fecha de la retención
                'journal_id': order.session_id.config_id.journal_id.id,
                'state': 'draft',
                'line_ids': [
                    (0, 0, {
                        'account_id': account_payable.id,
                        'partner_id': None,
                        'name': 'IVA RETENIDO POR CLIENTE',
                        'debit': retained_amount,
                        'credit': 0.0,
                    }),
                    (0, 0, {
                        'account_id': account_iva.id,
                        'partner_id': partner.id,
                        'name': 'IVA RETENIDO POR CLIENTE',
                        'debit': 0.0,
                        'credit': retained_amount,
                    }),
                ],
            }
            move = self.env['account.move'].create(move_vals)
            order.vat_retention_move_id = move.id  # Relacionar el asiento al pedido

    def action_confirm_vat_retention(self):
        for order in self:
            move = order.vat_retention_move_id
            if not move:
                raise UserError("No hay asiento de retención generado para confirmar.")
            if move.state != 'draft':
                raise UserError("El asiento de retención ya está publicado.")
            if order.vat_retention_ids:
                # Tomar la última retención (o la que corresponda según tu lógica)
                retention = order.vat_retention_ids[-1]
                # Validar que el comprobante esté establecido
                if not retention.comprobante_number:
                    raise UserError("Debe establecer el número de comprobante antes de confirmar la retención.")
                # Actualizar la fecha y la etiqueta del asiento con el número de comprobante
                move.date = retention.retention_date
                move.ref = f"Retención IVA POS FAC {order.ticket_fiscal} - Comprobante: {retention.comprobante_number}"
            move.action_post()
