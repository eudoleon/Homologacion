# __manifest__.py
{
    'name': 'Agregar Campo de referencia a product.template',
    'version': '19.0.1.0',
    'category': 'Inventory',
    'summary': 'Agregar Campo de referencia a product.template',
    'description': """
        Agregar Campo de referencia a product.template y búsqueda mejorada.
    """,
    'author': 'Steve Piñero',
    'depends': ['stock', 'account'],
    'installable': True,
    'data': [
        'views/product_template.xml',
        'views/account_move.xml',
    ],
    'application': False,
    'license': 'LGPL-3',
}