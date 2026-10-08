# -*- coding: utf-8 -*-
from odoo import models


class SaleReportUsd(models.Model):
    _inherit = 'sale.report.usd'

    def _select_pos(self):
        """Override to use pos_usd_fields stored USD values instead of generic cr_usd.rate.

        The pos_usd_fields module stores price_subtotal_usd and price_subtotal_incl_usd
        directly on pos.order.line using the tasa_usd from the POS order, which is more
        accurate than the generic res_currency_rate lookup.
        """
        select_ = f"""
            -MIN(l.id) AS id,
            l.product_id AS product_id,
            t.uom_id AS product_uom,
            SUM(l.qty) AS product_uom_qty,
            SUM(l.qty) AS qty_delivered,
            0 AS qty_to_deliver,
            CASE WHEN pos.state = 'invoiced' THEN SUM(l.qty) ELSE 0 END AS qty_invoiced,
            CASE WHEN pos.state != 'invoiced' THEN SUM(l.qty) ELSE 0 END AS qty_to_invoice,
            SUM(l.price_subtotal_incl)
                / MIN({self._case_value_or_one('pos.currency_rate')})
                * 1.0
            AS price_total,
            SUM(l.price_subtotal)
                / MIN({self._case_value_or_one('pos.currency_rate')})
                * 1.0
            AS price_subtotal,
            (CASE WHEN pos.state != 'invoiced' THEN SUM(l.price_subtotal) ELSE 0 END)
                / MIN({self._case_value_or_one('pos.currency_rate')})
                * 1.0
            AS untaxed_amount_to_invoice,
            (CASE WHEN pos.state = 'invoiced' THEN SUM(l.price_subtotal) ELSE 0 END)
                / MIN({self._case_value_or_one('pos.currency_rate')})
                * 1.0
            AS untaxed_amount_invoiced,
            count(*) AS nbr,
            pos.name AS name,
            pos.date_order AS date,
            (CASE WHEN pos.state = 'done' THEN 'sale' ELSE pos.state END) AS state,
            pos.partner_id AS partner_id,
            pos.user_id AS user_id,
            pos.company_id AS company_id,
            NULL AS campaign_id,
            NULL AS medium_id,
            NULL AS source_id,
            t.categ_id AS categ_id,
            pos.pricelist_id AS pricelist_id,
            NULL AS analytic_account_id,
            pos.crm_team_id AS team_id,
            p.product_tmpl_id,
            partner.commercial_partner_id AS commercial_partner_id,
            partner.country_id AS country_id,
            partner.industry_id AS industry_id,
            (SUM(p.weight) * l.qty / u.factor) AS weight,
            (SUM(p.volume) * l.qty / u.factor) AS volume,
            l.discount AS discount,
            SUM((l.price_unit * l.discount * l.qty / 100.0
                / {self._case_value_or_one('pos.currency_rate')}
                * 1.0))
            AS discount_amount,
            pos.id AS order_id,
            SUM(l.price_subtotal_incl_usd) AS price_total_usd,
            SUM(l.price_subtotal_usd) AS price_subtotal_usd,
            (CASE WHEN pos.state != 'invoiced' THEN SUM(l.price_subtotal_usd) ELSE 0 END) AS untaxed_amount_to_invoice_usd,
            (CASE WHEN pos.state = 'invoiced' THEN SUM(l.price_subtotal_usd) ELSE 0 END) AS untaxed_amount_invoiced_usd,
            SUM((l.price_unit_usd * l.discount * l.qty / 100.0)) AS discount_amount_usd,
            usd_currency.id AS usd_currency_id,
            concat('pos.order', ',', pos.id) AS order_reference"""

        additional_fields = self._select_additional_fields()
        additional_fields_info = self._fill_pos_fields(additional_fields)
        template = """,
            %s AS %s"""
        for fname, value in additional_fields_info.items():
            select_ += template % (value, fname)
        return select_
