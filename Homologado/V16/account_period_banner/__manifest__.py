{
    'name': 'NOTIFICACION DE PERIODO FISCAL',
    'version': '16.0.1.0.0',
    'depends': ['web','base'],
    'data': [
        # 'views/account_banner.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'account_period_banner/static/src/js/account_banner.js',
        ],
    },
    'installable': True,
    'application': False,
}
