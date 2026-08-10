{
    'name': 'POS Cashea Debt Type',
    'version': '16.0.1.0.0',
    'depends': ['point_of_sale', 'account'],
    'author': 'GitHub Copilot',
    'category': 'Point of Sale',
    'description': 'Configura metodos de pago Cashea en POS y clasifica el tipo de deuda en la factura.',
    'data': [
        'views/pos_payment_method_views.xml',
        'views/pos_order_views.xml',
        'views/account_move_views.xml',
    ],
    'installable': True,
    'application': False,
}