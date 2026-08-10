from odoo import tools
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class ResCompany(models.Model):
	_inherit = 'res.company'

	is_igtf = fields.Boolean(string='Retencion de IGTF Divisa')
	igtf_percentage = fields.Float(string='% IGTF Divisa')
	receivable_account_id = fields.Many2one('account.account', string='Cuenta Recibos IGTF',  ondelete='restrict')
	payable_account_id = fields.Many2one('account.account', string='Cuenta Pagos IGTF',  ondelete='restrict')
	
