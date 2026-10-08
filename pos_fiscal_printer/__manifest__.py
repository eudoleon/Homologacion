# -*- coding: utf-8 -*-
{
    'name': 'REPORTE Z POS',
    'version': '19.0.1.0.0',
    'category': 'Localization',
    'summary': 'REPORTE Z POS',
    'author': 'Andres Castillo by Contables',
    'company': 'Contables Boyer Leon & Asoc.',
    'maintainer': 'Easy Solution Services',
    'website': '',
    'description': 'reporte',
    'depends': ['point_of_sale', '3mit_print_server', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        #'views/inherited_views.xml',
        #'views/x_pos_fiscal_printer_views.xml',
        'views/pos_report_z.xml',
    ],
    'assets': {
        'point_of_sale.assets': [
            # 'pos_fiscal_printer/static/src/scss/**/*',
            # 'pos_fiscal_printer/static/src/js/AbstractReceiptScreen.js',
            # 'pos_fiscal_printer/static/src/js/PartnerDetailsEdit.js',
            # 'pos_fiscal_printer/static/src/js/NotaCreditoPopUp.js',
            # 'pos_fiscal_printer/static/src/js/PrintingMixin.js',
            # 'pos_fiscal_printer/static/src/js/ReporteZPopUp.js',
            # 'pos_fiscal_printer/static/src/js/ReprintingPopUp.js',
            # 'pos_fiscal_printer/static/src/xml/**/*',
            # 'pos_fiscal_printer/static/lib/js/**/*',
            # 'pos_fiscal_printer/static/lib/css/**/*',
        ],
        # 'web.assets_backend': [
        #     'pos_fiscal_printer/static/src/js/GetZBackends.js',
        # ],
    },
    'license': 'LGPL-3',
}
