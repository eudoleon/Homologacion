# coding: utf-8
from odoo import fields, models, api
from odoo.exceptions import ValidationError, UserError


class ProductProduct(models.Model):
    _inherit = "product.product"

    @api.onchange('type')
    def _onchange_type(self):
        #res = super(ProductProduct, self)._onchange_type()
        concept_id = False
        if self.type == 'service':
            concept_obj = self.env['account.wh.islr.concept']

            concept_id = concept_obj.search([('withholdable', '=', False)])
            concept_id = concept_id and concept_id[0] or False
            if not concept_id:
                raise UserError("Invalid action! \nDebe crear el concepto de retención de ingresos")
        #self.concept_id = concept_id or False
        return {'value': {'concept_id': concept_id or False}}

    # @api.constrains('list_price', 'standard_price')
    # def _check_sale_price_not_lower_than_cost(self):
    #     for product in self:
    #         if product.list_price < product.standard_price:
    #             raise ValidationError(
    #                 f"El precio de venta ({product.list_price}) no puede ser menor al costo ({product.standard_price}) para el producto '{product.name}'."
    #             )