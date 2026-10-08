# -*- coding: utf-8 -*-
{
    'name': 'Custom Contact',
    'version': '19.0.1.0.0',
    'category': 'Contacts',
    'summary': 'Personalización de la ficha de contactos con tipo de identificación',
    'description': """
    Personalización de Contactos
    ============================
    - Agrega el campo tipo de identificación (id_type) en la ficha de contactos
      ubicado arriba de Documento de Identidad (personas) o arriba de RIF (empresas).
    - Valida la unicidad de la combinación de tipo de identificación y documento (VAT).
    """,
    'author': 'Tu Nombre',
    'license': 'LGPL-3',
    'depends': ['base', 'l10n_ve_full'],
    'data': [
        'views/contact_form_view.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}