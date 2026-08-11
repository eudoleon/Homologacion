{
    'name': 'Custom Banner Module',
    'version': '19.0.1.0.0',
    'category': 'Tools',
    'license': 'LGPL-3',
    'description': 'Módulo para mostrar un banner personalizado en la interfaz de usuario',
    'author': 'Tu Nombre',
    'depends': ['web'],
    'data': [],
    'assets': {
        'web.assets_backend': [
            'my_custom_module/static/src/js/banner.js',
        ],
    },
    'installable': True,
    'auto_install': False,
}
