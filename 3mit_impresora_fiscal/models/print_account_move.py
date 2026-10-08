from odoo import fields, models

class Impresoraadaptacioninvoices(models.Model):
    _inherit = 'account.move'

    estado_impreso = fields.Boolean('Estado_impresion', default=False)

    def reimprimir_orden(self):
        self.estado_impreso = False