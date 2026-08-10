{
    'name': 'Factura Forma libre',
    'version': '16.0.1.0.0',
    'summary': 'Formato de impresión personalizado para facturas forma Libre',
    'category': 'Accounting',
    'author': 'Marvin Chaviel',
    "website": "https://www.contablesag.com",
    'license': 'LGPL-3',
    'depends': ['account', 'account_dual_currency'],
    'data': [
        'data/paperformat_data.xml',
        'report/invoice_report_dual.xml',
        'report/invoice_report.xml',
        'report/invoice_template.xml',
        'report/invoice_template_dual.xml',
    ],
    'installable': True,
    'application': False,
}