# -*- coding: utf-8 -*-
{
    'name': 'POS Restrict Negative Stock',
    'version': '19.0.1.0.1',
    'category': 'Point of Sale',
    'summary': 'Restringe la venta de productos con stock insuficiente en el Punto de Venta (POS)',
    'description': """
        Módulo para el Punto de Venta (POS) que evita ventas en negativo con diseño visual interactivo.
    """,
    'author': 'Custom',
    'depends': ['base', 'point_of_sale', 'stock'],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_restrict_negative_stock/static/src/css/pos_stock_popup.css',
            'pos_restrict_negative_stock/static/src/js/StockRestrictionPopup.js',
            'pos_restrict_negative_stock/static/src/js/pos_restrict_negative_stock.js',
            'pos_restrict_negative_stock/static/src/xml/stock_popup.xml',
        ]
    },
    'license': 'AGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}
