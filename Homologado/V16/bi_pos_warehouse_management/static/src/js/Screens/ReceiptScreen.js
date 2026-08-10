// ReceiptScreen js
odoo.define('bi_pos_warehouse_management.ReceiptScreen', function(require) {
	"use strict";

	const Registries = require('point_of_sale.Registries');
	const PosComponent = require('point_of_sale.PosComponent');
	const ReceiptScreen = require('point_of_sale.ReceiptScreen');

	const BiReceiptScreen = (ReceiptScreen) => {
		class BiReceiptScreen extends ReceiptScreen {
			setup() {
                super.setup();
				let self = this;
				const order = this.currentOrder;
				let orderlines = order.get_orderlines();
				let products = order.calculate_prod_qty();
				let config = this.env.pos.config;		
				let config_loc = config.stock_location_id[0];
				$.each(orderlines, function( i, line ){
					let prd = line.product;
					if (prd.type == 'product'){
						let loc = line.stock_location_id;
						if(!loc){
							loc = config_loc;
						}
						let loc_qty = self.env.pos.prod_with_quant[prd.id];
						if(loc_qty && self.env.pos.prod_with_quant[prd.id][loc]){
							self.env.pos.prod_with_quant[prd.id][loc] -= line.quantity;
						}
					}
				});
			}
		}
		BiReceiptScreen.template = 'BiReceiptScreen';
		return BiReceiptScreen;
	};

	Registries.Component.addByExtending(BiReceiptScreen, ReceiptScreen);
	return BiReceiptScreen;
});