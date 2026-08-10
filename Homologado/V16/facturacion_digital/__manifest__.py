# -*- coding: utf-8 -*-
{
    'name': "Facturacion Digital",
    'summary': """
        Facturacion digital con Smart-Factura Digital
        """,
    'description': """
        Facturacion digital con Smart-Factura Digital
    """,
    'author': "Smart Systems, C.A.",
    'website': "https://smartsystems.com.ve",
    'category': 'Smart Systems/Desarrollos',
    'version': '1.0',
    'depends': ['base', 'base_vat', 'account', 'l10n_ve_full','l10n_ve_invoice'],
    'data': [
        # 'security/ir.model.access.csv',
        'views/category.xml',
        'views/account_move_view.xml',
        'views/res_company.xml',
        'views/res_config_settings.xml',
        'views/account_journal.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'OEEL-1',
}
