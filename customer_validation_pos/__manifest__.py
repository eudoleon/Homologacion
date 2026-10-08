# -*- coding: utf-8 -*-
{
    'name': 'Customer Validation POS',
    'version': '19.0.1.0.1',
    'author': 'Preway IT Solutions',
    'category': 'Point of Sale',
    'depends': ['point_of_sale', 'l10n_ve_full', 'custom_contact'],
    'summary': 'Valida campos obligatorios y únicos (teléfono de 11 dígitos, correo, cédula/RIF) al guardar clientes en el POS',
    'description': """
        Módulo para validar clientes en el Punto de Venta (POS) en Odoo 19:
        - Teléfono obligatorio y formato flexible (+58, 10-11+ dígitos)
        - Teléfono único
        - Correo electrónico obligatorio y único
        - Cédula / RIF obligatoria, formato válido y única
        - Dirección fiscal y nombre obligatorios y únicos
        - Vista limpia de 2 columnas para el POS y acción redirigida a vista simplificada
        Totalmente integrado con el flujo nativo de Odoo 19.
    """,
    'data': [
        'views/pos_config_view.xml',
        'views/res_partner_view.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'customer_validation_pos/static/src/app/services/pos_store.js',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
