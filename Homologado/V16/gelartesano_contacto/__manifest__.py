{
    'name': 'Gelartesano Contacto',
    'version': '16.0.1.0.0',
    'summary': 'Valida que identification_id sea único entre contactos activos.',
    'author': 'Tu Nombre',
    'depends': ['base'],
    'data': [],
    'installable': True,
    'application': False,
    'assets': {
        'point_of_sale.assets': [
            'gelartesano_contacto/static/src/js/partner_validation.js',
        ],
    },
}