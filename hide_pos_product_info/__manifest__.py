# -*- coding: utf-8 -*-

{
    'name': 'POS Hide Product Info ',
    'version': '19.0.1.0.0',
    'category': 'Sales/Point of Sale',
    'author': 'Andres Castillo by Contables',
    'license': 'AGPL-3',
    'summary': 'Hide POS product info',
    'depends': ['point_of_sale','pos_restaurant','pos_sale', 'sale_stock'],
    'website': 'www.contablesag.com',
    'data': [
        'views/res_config_settings_view.xml'
    ],
    'installable': True,
    'application': True,
    "assets": {
        # "point_of_sale._assets_pos": [
        #     "hide_pos_product_info/static/src/xml/Screens/ProductScreen/ControlButtons/ProductInfoButton.xml",
        #     "hide_pos_product_info/static/src/xml/Screens/ProductScreen/ControlButtons/RefundButton.xml",
        #     "hide_pos_product_info/static/src/xml/Screens/ProductScreen/ControlButtons/SetPricelistButton.xml",
        #     "hide_pos_product_info/static/src/xml/Screens/ProductScreen/ControlButtons/TableGuestsButton.xml",
        #     "hide_pos_product_info/static/src/xml/Screens/ProductScreen/ControlButtons/Order.xml",
        #     "hide_pos_product_info/static/src/xml/Screens/ProductScreen/ControlButtons/pos_sale.xml",
        #     "hide_pos_product_info/static/src/xml/Screens/ProductScreen/ControlButtons/listorder.xml",
        #     "hide_pos_product_info/static/src/js/OrderManagementScreen/sale.js",
        # ],
    },
    'images': [
        'static/description/before_config.png',
    ]
}
