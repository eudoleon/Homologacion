{
    'name': 'Añadir Nota de Crédito botón',
    'version': '16.0.1.0.0',
    'summary': 'Agrega un botón para crear nota de crédito en facturas',
    'depends': ['account'],
    'author': 'Samir Espina by Contables',
    'category': 'Accounting',
    'data': [
        'views/account_move_views.xml',
        'views/credit_note_motivo_confirm_view.xml',
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'auto_install': False,
}
