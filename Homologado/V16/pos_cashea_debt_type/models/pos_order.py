from odoo import api, fields, models


class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    # Permite dejar el diario vacío para que el método actúe como "pago diferido"
    # y genere cuenta por cobrar en lugar de registrar cobro inmediato.
    journal_id = fields.Many2one(required=False)

    is_cashea = fields.Boolean(string='Pagado por Cashea')

    @api.onchange('is_cashea', 'journal_id')
    def _onchange_is_cashea(self):
        if 'split_transactions' in self._fields and self.is_cashea and not self.journal_id:
            self.split_transactions = True

    def _sync_cashea_to_pos_configs(self):
        PosConfig = self.env['pos.config']
        for method in self:
            if not method.is_cashea:
                continue
            domain = []
            if 'company_id' in PosConfig._fields and method.company_id:
                domain = [('company_id', '=', method.company_id.id)]
            configs = PosConfig.search(domain)
            for config in configs:
                # Never force-write payment methods on configs with active sessions.
                # Odoo raises a UserError in that case.
                if getattr(config, 'current_session_id', False) and config.current_session_id.state != 'closed':
                    continue
                if method.id not in config.payment_method_ids.ids:
                    try:
                        config.write({'payment_method_ids': [(4, method.id)]})
                    except Exception:
                        # Keep payment-method save flow resilient; user can assign manually in config.
                        continue

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('is_cashea') and not vals.get('journal_id'):
                vals.setdefault('type', 'pay_later')
                if 'split_transactions' in self._fields:
                    vals.setdefault('split_transactions', True)
        records = super().create(vals_list)
        records._sync_cashea_to_pos_configs()
        return records

    def write(self, vals):
        if 'journal_id' in vals and not vals.get('journal_id'):
            for method in self:
                local_vals = dict(vals)
                if local_vals.get('is_cashea', method.is_cashea):
                    local_vals.setdefault('type', 'pay_later')
                    if 'split_transactions' in self._fields:
                        local_vals.setdefault('split_transactions', True)
                super(PosPaymentMethod, method).write(local_vals)
            self._sync_cashea_to_pos_configs()
            return True

        if vals.get('is_cashea') and not vals.get('journal_id'):
            vals = dict(vals)
            vals.setdefault('type', 'pay_later')
            if 'split_transactions' in self._fields:
                vals.setdefault('split_transactions', True)
        res = super().write(vals)
        self._sync_cashea_to_pos_configs()
        return res


class AccountMove(models.Model):
    _inherit = 'account.move'

    tipo_de_deuda = fields.Selection(
        selection=[
            ('cashea', 'Cashea'),
            ('ventas_internas', 'Ventas Internas'),
        ],
        string='Tipo de Deuda',
        readonly=True,
        tracking=True,
    )



class PosOrder(models.Model):
    _inherit = 'pos.order'

    tipo_de_deuda = fields.Selection(
        selection=[
            ('cashea', 'Cashea'),
            ('ventas_internas', 'Ventas Internas'),
        ],
        string='Tipo de Deuda',
        compute='_compute_tipo_de_deuda',
        store=False,
    )

    @api.depends('payment_ids', 'payment_ids.payment_method_id', 'payment_ids.payment_method_id.is_cashea', 'payment_ids.amount')
    def _compute_tipo_de_deuda(self):
        for order in self:
            payments = order.payment_ids
            if not payments:
                order.tipo_de_deuda = False
                continue
            cashea = False
            for p in payments:
                pm = p.payment_method_id
                if not pm:
                    continue
                # Primary detection: explicit flag
                if getattr(pm, 'is_cashea', False):
                    cashea = True
                    break
                # Fallback detection: method named 'CASHEA'
                name = (pm.name or '').upper()
                if 'CASHEA' in name:
                    cashea = True
                    break
            order.tipo_de_deuda = 'cashea' if cashea else 'ventas_internas'

    def _prepare_invoice_vals(self):
        vals = super()._prepare_invoice_vals()
        vals['tipo_de_deuda'] = self.tipo_de_deuda
        return vals