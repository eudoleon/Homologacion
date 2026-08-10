{
    'name': 'POS No Auto Close Popup',
    'version': '1.0',
    'category': 'Point of Sale',
    'summary': 'Disable auto close of specific popups in POS while allowing manual close',
    'description': 'This module disables the auto close of specific popups in the Point of Sale while allowing manual close for certain screens.',
    'author': 'Your Name',
    'depends': ['point_of_sale'],
    'data': [],
    'assets': {
        'point_of_sale.assets': [
            'custom_pos_autoclose/static/src/js/prevent_auto_close.js',
            'custom_pos_autoclose/static/src/js/allow_manual_close.js',
        ],
    },
    'installable': True,
    'application': False,
}
