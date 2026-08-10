{
    'name': "Tasa Automática BCV",
    'description': """
        Este módulo actualiza la tasa BCV de acuerdo a una acción planificada
    """,

    'author': "Andrés Castillo",
    'website': "contablesag.com",
    'version': '16.0.1.2.2',
    'category': 'Localization',
    'license': 'AGPL-3',
    'depends': ['l10n_ve',],
    'data': [
        'security/ir.model.access.csv',
        'data/days_bcv.xml',
        'data/currency_rate_cron.xml',
        'views/bank_holidays.xml',
        'views/res_config_settings_views.xml',
    ],
}