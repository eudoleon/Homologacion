{
    'name': 'Notificacion al Seniat',
    'version': '16.0',
    'summary': 'Manage Fiscal Year Lock Date with Warnings',
    'sequence': 10,
    'description': """""",
    'category': 'Accounting',
    'website': 'https://www.contablesag.com',
    'depends': ['base', 'mail', 'stock', 'account','account_accountant'],
    'data': [
        'data/mail_template2.xml',
        'views/warning.xml',
    ],
    'assets': {
        'web.assets_backend': [
            '/delivery_warning_seniat/static/src/js/form_controller.js',
        ],
    },
    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}
