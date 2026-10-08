{
	"name": "POS print kitchen order receipt KOT in browser| Custom Kitchen Order Receipt | Customer and Cashier name on Kitchen Order Receipt",
	"summary": "Custom Kitchen Order Receipt | Customer and Cashier name on Kitchen Order Receipt",
	"version": "19.0.1.0",
	"description": """Custom Kitchen Order Receipt | Customer and Cashier name on Kitchen Order Receipt""",    
    "category": 'Point of Sale',    
    "author" : "MAISOLUTIONSLLC",
    "email": 'apps@maisolutionsllc.com',
    "website":'http://maisolutionsllc.com/',
    "license": 'OPL-1', 
    "price": 20,
    "currency": "EUR",     
	"category": "Point of Sale",
	"depends": ["pos_restaurant"],
	"data": [
	],
	'installable': True,
	'application': True,
	'auto_install': False,
    "images": ['static/description/main_screenshot.png'],	
    'assets': {
        'point_of_sale._assets_pos': [
            'mai_pos_customised_KOT/static/src/js/models.js',
            'mai_pos_customised_KOT/static/src/xml/pos.xml',
        ],
    },    
}
