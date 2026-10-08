{
    'name': 'Restricción de productos en facturas',
    'author': 'Samir Espina, Dev By Contables',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'depends': ['account', 'product', 'sale'],
    'data': [
        'views/account_move_line_view.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}