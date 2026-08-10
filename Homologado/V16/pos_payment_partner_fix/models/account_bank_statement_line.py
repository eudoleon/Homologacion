from odoo import models

class AccountBankStatementLine(models.Model):
    _inherit = 'account.bank.statement.line'

    def _prepare_move_line_vals(self, amount):
        res = super()._prepare_move_line_vals(amount)

        # Si hay partner, forzar que ambas líneas del asiento lo lleven
        partner_id = self.partner_id.id if self.partner_id else False
        if partner_id and 'line_ids' in res:
            for line in res['line_ids']:
                if isinstance(line, (list, tuple)) and len(line) == 3:
                    line_data = line[2]
                    line_data['partner_id'] = partner_id

        return res
