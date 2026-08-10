{
    'name': 'POS Payment Partner Fix',
    'version': '16.0',
    'summary': 'Asegura que ambas líneas contables del POS tengan partner_id si el método lo requiere',
    'category': 'Point of Sale',
    'author': 'Aecas',
    'license': 'LGPL-3',
    'depends': ['point_of_sale', 'account'],
    'data': ['data/cron.xml','data/cron2.xml','views/account_move_line_usd_view.xml'],
    'installable': True,
    'auto_install': False,
    'application': False,
}
