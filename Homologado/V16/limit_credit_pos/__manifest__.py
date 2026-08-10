{
    'name': 'Límite de Crédito POS',
    'version': '16.0.1.0.0',
    'category': 'Sales',
    'summary': 'Gestión de límite de crédito para contactos y alertas en POS',
    'author': 'Farruggio',
    'depends': ['base', 'account', 'point_of_sale'],
    'data': [
        'views/view_res_partner_credit.xml',
    ],
    'assets': {
        'point_of_sale.assets': [
            'limit_credit_pos/static/src/js/pos_credit_limit.js',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
