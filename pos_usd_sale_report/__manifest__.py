# -*- coding: utf-8 -*-
{
    "name": "POS USD Sale Report",
    "version": "19.0.1.0.0",
    "summary": "Usa los campos USD almacenados de pos_usd_fields en el reporte sale.report.usd",
    "description": """
        Este módulo extiende el reporte de ventas USD (sale.report.usd) para que
        los pedidos POS utilicen los campos price_subtotal_usd, price_subtotal_incl_usd
        almacenados por pos_usd_fields (basados en la tasa_usd de cada orden POS),
        en lugar de la tasa genérica de res_currency_rate.
    """,
    "category": "Sales",
    "author": "Samir Espina",
    "license": "LGPL-3",
    "depends": ["sale_report_usd", "pos_usd_fields"],
    "data": [],
    "installable": True,
    "application": False,
}