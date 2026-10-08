from odoo import _, api, models
from odoo.exceptions import ValidationError


class AccountMoveLine(models.Model):
	_inherit = "account.move.line"

	@api.onchange("move_id")
	def _onchange_restrict_product_domain_customer_docs(self):
		"""Force service-only product picker on customer invoice documents.
		Restriction only applies when invoice is not from a sale order."""
		customer_move_types = {"out_invoice", "out_refund", "out_receipt"}
		if (
			self.move_id
			and self.move_id.move_type in customer_move_types
			and not self.sale_line_ids
		):
			return {"domain": {"product_id": [("type", "=", "service")]}}
		return {}

	@api.constrains("product_id", "move_id", "display_type")
	def _check_customer_invoice_service_only_products(self):
		"""Keep restriction enforced even if a custom view bypasses the domain.
		Restriction only applies when invoice is not from a sale order."""
		customer_move_types = {"out_invoice", "out_refund", "out_receipt"}
		for line in self:
			is_product_line = not line.display_type or line.display_type == "product"
			product_type = getattr(line.product_id, "type", False)
			if (
				line.product_id
				and is_product_line
				and line.move_id.move_type in customer_move_types
				and product_type != "service"
				and not line.sale_line_ids
			):
				raise ValidationError(
					_("Solo se permiten productos de tipo servicio en facturas de cliente.")
				)

