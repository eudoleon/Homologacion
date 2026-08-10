from odoo import models
from odoo.exceptions import UserError

class ReportAccountWhMunicipal(models.AbstractModel):
    _name = 'report.l10n_ve_full.report_account_wh_municipal'
    _description = 'Reporte de Retención Municipal'

    def _get_report_values(self, docids, data=None):
        docs = self.env['account.wh.municipal'].browse(docids)
        for doc in docs:
            if doc.move_id.move_type not in ['in_invoice', 'in_refund']:
                raise UserError("Solo se puede emitir el comprobante al proveedor.")
        return {
            'doc_ids': docids,
            'doc_model': 'account.wh.municipal',
            'docs': docs,
        }

def print_report_account_wh_municipal(self):
        return self.env.ref('l10n_ve_full.action_report_account_wh_municipal').report_action(self)