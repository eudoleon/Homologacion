# -*- coding: utf-8 -*-
from odoo import api, fields, models

class ProductTemplate(models.Model):
    _inherit = "product.template"

    currency_usd_id = fields.Many2one(
        "res.currency",
        string="USD Currency",
        compute="_compute_currency_usd_id",
        store=False,
    )

    margin_cost_usd = fields.Monetary(
        string="Costo Margen $",
        currency_field="currency_usd_id",
        help="standard_price convertido a USD usando la tasa del día.",
        compute="_compute_margin_cost_usd",
        store=False,
        readonly=True,
    )

    def _get_usd_currency(self):
        """Find USD currency (by XML-ID base.USD or by name)."""
        usd = self.env.ref("base.USD", raise_if_not_found=False)
        if not usd:
            usd = self.env["res.currency"].search([("name", "=", "USD")], limit=1)
        return usd

    @api.depends_context("company")
    def _compute_currency_usd_id(self):
        usd = self._get_usd_currency()
        for rec in self:
            rec.currency_usd_id = usd

    @api.depends("standard_price", "company_id")
    def _compute_margin_cost_usd(self):
        """
        Convert company-currency standard_price to USD using Odoo's converter.
        Effectively equivalent to 'standard_price / tasa_inversa_USD' for today.
        """
        today = fields.Date.context_today(self)
        for rec in self:
            price = rec.standard_price or 0.0
            company = rec.company_id or self.env.company
            comp_curr = company.currency_id
            usd = rec.currency_usd_id or rec._get_usd_currency()
            if not usd:
                rec.margin_cost_usd = 0.0
                continue
            rec.margin_cost_usd = comp_curr._convert(price, usd, company, today)
