{
    'name': 'Última Fecha de Pedido de Venta en Contactos',
    'version': '16.0.1.0.0',
    'category': 'Sales',
    'summary': 'Muestra la última fecha de pedido de venta y de compra para cada contacto',
    'author': 'Samir Espina, Daniel Rodriguez',
    'depends': ['sale', 'purchase'],
    'data': [
        'views/res_partner_view.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
