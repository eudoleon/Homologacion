from odoo import models, fields, api

class PosOrder(models.Model):
    _inherit = 'pos.order'

    @api.model
    def _get_default_tasa_usd(self):
        try:
            # Intentar obtener la tasa del módulo account_dual_currency si está instalado
            if hasattr(self.env['res.currency'], 'get_trm_systray'):
                rate = self.env['res.currency'].get_trm_systray()
                if rate:
                    return rate
        except Exception:
            pass
            
        try:
            company = self.env.company
            if hasattr(company, 'currency_id_dif') and company.currency_id_dif:
                return company.currency_id_dif.inverse_rate or 1.0
                
            usd_currency = self.env['res.currency'].search([('name', '=', 'USD')], limit=1)
            if usd_currency:
                if hasattr(usd_currency, 'inverse_company_rate') and usd_currency.inverse_company_rate:
                    return usd_currency.inverse_company_rate
                elif hasattr(usd_currency, 'inverse_rate') and usd_currency.inverse_rate:
                    return usd_currency.inverse_rate
                elif usd_currency.rate:
                    return 1.0 / usd_currency.rate
        except Exception:
            pass
            
        return 1.0

    tasa_usd = fields.Float(string="Tasa USD", default=_get_default_tasa_usd)

    @api.model
    def _order_fields(self, ui_order):
        res = super(PosOrder, self)._order_fields(ui_order)
        if 'tasa_usd' in ui_order:
            res['tasa_usd'] = ui_order['tasa_usd']
        return res
