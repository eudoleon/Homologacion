{
    'name': 'Tasa BCV',
    'version': '19.0.0.0',
    'summary': 'Actualización automática de la tasa de cambio desde el BCV',
    'author': 'Aecas',
    'category': 'Accounting',
    'depends': ['base'],
    'data': ['data/ir_cron_data.xml'],
    'post_init_hook': 'set_bcv_cron_nextcall',
    'installable': True,
    'application': False,
    'auto_install': False,
}
