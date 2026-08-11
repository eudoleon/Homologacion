# -*- coding: utf-8 -*-
from odoo import fields, models, tools, api, _
from collections import defaultdict
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_is_zero


class StockLandedCost(models.Model):
    _inherit = 'stock.landed.cost'

    currency_id = fields.Many2one(
        comodel_name="res.currency",
        required=True,
        default=lambda self: self.env.user.company_id.currency_id,
    )

    company_currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id'
    )

    amount_total = fields.Monetary(
        'Total',
        compute='_compute_total_amount',
        store=True,
        tracking=True,
        currency_field="company_currency_id"
    )

    move_ids = fields.Many2many('account.move', readonly=True)

    # ---------------------------------------------------------
    # ONCHANGE
    # ---------------------------------------------------------

    @api.onchange("account_journal_id")
    def _onchange_account_journal_id(self):
        if self.account_journal_id and self.account_journal_id.currency_id:
            self.currency_id = self.account_journal_id.currency_id

    @api.onchange("currency_id", "tax_today")
    def _onchange_currency_id(self):
        if self.currency_id:
            self.cost_lines._onchange_currency_price_unit()

    # ---------------------------------------------------------
    # VALIDACIÓN (COMPATIBLE V19)
    # ---------------------------------------------------------

    def button_validate(self):
        self._check_can_validate()

        cost_without_adjustment_lines = self.filtered(
            lambda c: not c.valuation_adjustment_lines
        )
        if cost_without_adjustment_lines:
            cost_without_adjustment_lines.compute_landed_cost()

        if not self._check_sum():
            raise UserError(_(
                'Cost and adjustments lines do not match. '
                'You should maybe recompute the landed costs.'
            ))

        # Ejecutar comportamiento estándar v19
        res = super(StockLandedCost, self).button_validate()

        # =====================================================
        # LÓGICA PERSONALIZADA USD (SIN STOCK.VALUATION.LAYER)
        # =====================================================

        for cost in self:
            cost_to_add_byproduct_usd = defaultdict(lambda: 0.0)

            for line in cost.valuation_adjustment_lines.filtered(lambda l: l.move_id):
                product = line.move_id.product_id

                if not line.move_id.product_qty:
                    continue

                # Prorrateo proporcional como en v18
                proportion = line.quantity / line.move_id.product_qty
                cost_to_add_usd = proportion * line.additional_landed_cost_usd

                if product.cost_method == 'average':
                    cost_to_add_byproduct_usd[product] += cost_to_add_usd

            # -------------------------------------------------
            # ACTUALIZAR COSTO PROMEDIO USD (AVCO)
            # -------------------------------------------------

            products = self.env['product.product'].browse(
                p.id for p in cost_to_add_byproduct_usd.keys()
            )

            for product in products:
                if not float_is_zero(
                    product.quantity_svl,
                    precision_rounding=product.uom_id.rounding
                ):
                    product.with_company(cost.company_id).sudo().with_context(
                        disable_auto_svl=True
                    ).standard_price_usd += (
                        cost_to_add_byproduct_usd[product] / product.quantity_svl
                    )

            # -------------------------------------------------
            # AJUSTAR ASIENTOS CONTABLES USD
            # -------------------------------------------------

            for move in cost.move_ids.filtered(lambda m: m.state == 'posted'):
                for line in move.line_ids:
                    # Campo personalizado asumido: amount_currency_usd
                    if hasattr(line, 'amount_currency_usd'):
                        if line.debit:
                            line.amount_currency_usd = line.debit
                        elif line.credit:
                            line.amount_currency_usd = -line.credit

        return res