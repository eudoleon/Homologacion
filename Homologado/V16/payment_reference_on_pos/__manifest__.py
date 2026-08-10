# -*- coding: utf-8 -*-
#################################################################################
# Author      : CFIS (<https://www.cfis.store/>)
# Copyright(c): 2017-Present CFIS.
# All Rights Reserved.
#
#
#
# This program is copyright property of the author mentioned above.
# You can`t redistribute it and/or modify it.
#
#
# You should have received a copy of the License along with this program.
# If not, see <https://www.cfis.store/>
#################################################################################

{
    "name": "Pos Payment Reference | Payment Reference on POS",
    "summary": """
        This module allows you to provide a payment reference on the pos order payment line.
        """,
    "version": "16.0.1",
    "description": """
        This module allows you to provide a payment reference on the pos order payment line.
        """,    
    "author": "CFIS",
    "maintainer": "CFIS",
    "license" :  "Other proprietary",
    "website": "https://www.cfis.store",
    "images": ["images/payment_reference_on_pos.png"],
    "category": "Point of Sale",
    "depends": [
        "base",
        "point_of_sale",
    ],
    "data": [
        "views/view_pos_config.xml",
        "views/pos_order_view.xml",
        "views/pos_payment_views.xml",
    ],
    "assets": {        
        "point_of_sale.assets": [
            "/payment_reference_on_pos/static/src/css/style.css",            
            "/payment_reference_on_pos/static/src/js/models.js",
            "/payment_reference_on_pos/static/src/js/PaymentScreen.js",
            "/payment_reference_on_pos/static/src/js/PaymentReferencePopup.js",
            "/payment_reference_on_pos/static/src/js/PaymentScreenPaymentLines.js",
            "/payment_reference_on_pos/static/src/xml/*.xml",
        ],
    },
    "installable": True,
    "application": True,
    "price"                 :  8,
    "currency"              :  "EUR",
    "pre_init_hook"         :  "pre_init_check",
}
