{
    "name": "POS Multi Currency Payment | POS: Show Dual Currency | Multi Currency Payment Venezuela",
    "version": "19.0.1.0.0",
    'sequence': 1,
    "description": """
        Using this module you can add payment in Dual currency.
    """,
    "summary": """Using this module you can add payment in Dual currency.""",
    "category": "Point Of Sale",
    'price': 99,
    'currency': 'USD',
    'license': 'OPL-1',
    "author" : "MAISOLUTIONSLLC",
    'sequence': 1,
    "email": 'apps@maisolutionsllc.com',
    "website":'http://maisolutionsllc.com/',
    "depends": ["point_of_sale", "stock", "mai_pos_igtf_de_venezuela"],
    "data": [
        "views/views.xml"
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'mai_pos_dual_currency/static/src/css/pos.css',
            'mai_pos_dual_currency/static/src/js/pos_dual_currency.js',
            'mai_pos_dual_currency/static/src/xml/pos.xml',
            'mai_pos_dual_currency/static/src/xml/chrome.xml',
        ],
    },
    "images": ['static/description/main_screenshot.png'],
    "live_test_url" : "",
    'demo': [],
    'installable': True,
    'auto_install': False,
    'application': True,
}
