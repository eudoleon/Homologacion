{
    'name': 'Notificacion al Seniat',
    'version': '19.0.1.0',  # Actualizado a la versión 19
    'summary': 'Manage Fiscal Year Lock Date with Warnings',
    'author': 'ContablesAG',
    'license': 'LGPL-3',
    'sequence': 10,
    'description': """ """,
    'category': 'Accounting',
    'website': 'https://www.contablesag.com',
    'depends': ['base', 'mail', 'stock', 'account', 'account_accountant'],  # Verificar si alguna dependencia requiere actualización para Odoo 19
    'data': [
        'data/mail_template2.xml',
        'views/warning.xml',
    ],
    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}
