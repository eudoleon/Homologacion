{
    'name': 'Hide Confirm Button in Sales',
    'version': '19.0.1.0',
    'summary': 'Oculta el botón de Confirmar en Pedidos de Venta',
    'description': 'Este módulo oculta el botón de Confirmar en la vista de Pedidos de Venta.',
    'author': 'Andrés Castillo By Contables',
    'category': 'Sales',
    'depends': ['sale', 'purchase', 'stock'],
    'data': [
         'views/sale_order_view.xml',
         # Legacy (v17): en Odoo 19 esta herencia del wizard puede variar segun edicion.
         # Se mantiene el archivo y su contenido comentado para referencia futura.
         # 'views/sale_order_view_discount.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
