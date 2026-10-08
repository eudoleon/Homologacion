# -*- coding: utf-8 -*-
{
    'name': "POS Customization for Ticket Screen",
    'summary': "POS Customization for Ticket Screen",
    'description': """POS Customization for Ticket Screen Load Order""",
    'author': "Daniel Rodriguez by Contables",
    'category': 'Point of Sale',
    'license': 'LGPL-3',
    'version': '19.0.0.0',
    'depends': ['base', 'point_of_sale',],
    "application" :  True,
    "installable" :  True,


    'assets': {
        'point_of_sale.assets': [
            'pos_ticket_screen_load_order/static/src/js/TicketScreen.js',
            'pos_ticket_screen_load_order/static/src/xml/pos.xml',
        ],
    },

    "auto_install" :  False,
}

