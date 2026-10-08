# Copyright 2023 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
{
    "name": "Reporte Libro Z",
    "summary": "Reporte de ventas por Z",
    "version": "19.0.1.0.0",
    "author": "Andres Castillo by Contables",
    "license": "AGPL-3",
    "category": "Sale",
    "depends": [
        "pos_sale",
        "sale","pos_fiscal_printer","3mit_print_server"
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/pos.xml",
        "views/sale.xml",
    ],
    "application": False,
    "installable": True,
}
