from odoo import models, fields, api, _
import logging
_logger = logging.getLogger(__name__)


class BankHolidaysBcv(models.Model):
    _name = 'bank.holidays.bcv'

    name = fields.Char(string='Description')
    date = fields.Date(
        string='Bank holidays',
        default=fields.Date.context_today,
    )


class DaysBcv(models.Model):
    _name = 'days.bcv'

    code = fields.Integer(string='Code')
    name = fields.Char(string='Name')