{
    'name': 'Version de Odoo',
    'version': '19.0.1.0',
    'category': 'Website',
    'summary': 'Adds a neutralization banner to web layout',
    'depends': ['base', 'web','website','account'],
    'data': [
        'views/web_layout_extension.xml',
    ],
    'installable': True,
    'application': False,
}
