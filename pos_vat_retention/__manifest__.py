{
    "name": "POS VAT Retention A",
    "version": "19.0.1.0.0",
    "depends": ["point_of_sale", "base"],
    "data": [
        "views/pos_order_view.xml",
        #"views/res_partner_view.xml",
        "security/ir.model.access.csv",
        "views/res_company_view.xml",
    ],
    "installable": True,
    "auto_install": False,
}