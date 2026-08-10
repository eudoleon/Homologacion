// bi_pos_warehouse_management js
odoo.define('bi_pos_warehouse_management.pos', function(require) {
	"use strict";

	var { PosGlobalState, Order, Orderline, models } = require('point_of_sale.models');
	const Registries = require('point_of_sale.Registries');
    const { Gui } = require('point_of_sale.Gui');


	const PosHomePosGlobalState = (PosGlobalState) => class PosHomePosGlobalState extends PosGlobalState {
		async _processData(loadedData) {
			await super._processData(...arguments);
			let self = this;
			self.prod_with_quant = loadedData['prod_with_quant'];
			self.pos_custom_location = loadedData['pos_custom_location'];
			self.loc_by_id = loadedData['loc_by_id'];
		}
	}
	Registries.Model.extend(PosGlobalState, PosHomePosGlobalState);
	
	const OrderSuper = (Order) => class OrderSuper extends Order {
	    constructor(obj, options) {
			super(...arguments);
			this.order_products = this.order_products || {};
	 		this.prd_qty = this.prd_qty || {};
		}

	    //@override
	    export_as_JSON() {
			var self = this;
			var loaded = super.export_as_JSON(...arguments);
			loaded.order_products = self.order_products || {};
			// loaded.prd_qty = self.calculate_prod_qty() || {};
			return loaded;
		}
		//@override
		init_from_JSON(json){
			super.init_from_JSON(...arguments);
			this.order_products = json.order_products || {};
			this.prd_qty = json.prd_qty || {};
		}

		calculate_prod_qty() {
			var self = this;
			var products = {};
			var order = this.pos.get_order();
			if (order) {
				var orderlines = order.get_orderlines();
				var config_loc = self.pos.config.stock_location_id[0];
				if (order.prd_qty == undefined) {
					order.prd_qty = {};
				}
				if (order.order_products == undefined) {
					order.order_products = {};
				}
				if (orderlines.length > 0 && self.pos.config.display_stock_pos) {
					orderlines.forEach(function (line) {
						var prod = line.product;
						var qty = line.quantity;
						var loc = line.stock_location_id || config_loc;
		
						order.order_products[prod.id] = self.pos.prod_with_quant[prod.id];
		
						if (!products[prod.id]) {
							products[prod.id] = {};
						}
		
						if (!products[prod.id][loc]) {
							products[prod.id][loc] = {
								qty: 0,
								loc: loc,
								name: prod.display_name,
								line: line.id,
								prod: prod.id
							};
						}
		
						products[prod.id][loc].qty += qty;
					});
				}
			}
			return products;
		}		
	}
	Registries.Model.extend(Order, OrderSuper);

	const BiCustomOrderLine = (Orderline) => class BiCustomOrderLine extends Orderline{
		constructor(obj, options) {
        	super(...arguments);
        	this.stock_location_id = this.stock_location_id || false;
		}

		can_be_merged_with(orderline) {
			// Check if products are the same
			var price = parseFloat(this.get_unit_price());
			var new_price = parseFloat(orderline.get_unit_price());
			
			// If the product is the same, we force the merge, ignoring minor price differences or other fields
			// that typically prevent merging (like unperceived float differences).
			// This fulfills the requirement "do not duplicate product in order line".
			if (this.get_product().id === orderline.get_product().id) {
				return true;
			}

			return super.can_be_merged_with(orderline);
		}

		set_quantity(quantity, keep_price){
			if(this.pos.config.display_stock_pos && quantity !== 'remove' && quantity !== undefined){
				let qty = parseFloat(quantity);
				if(this.product.type === 'product' && !isNaN(qty) && !this.product.has_bom){
					let quant_text = this.product.quant_text;
					if(quant_text){
						try{
							let stocks = (typeof quant_text === 'string') ? JSON.parse(quant_text) : quant_text;
							let available = 0;
							
							if (this.stock_location_id) {
								let loc_id = this.stock_location_id;
								available = parseFloat(stocks[loc_id] || stocks[String(loc_id)] || 0) || 0;
							} else {
								// Sumar el stock de todas las ubicaciones configuradas (no tomar la mayor)
								let configured_locs = this.pos.config.warehouse_available_ids;
								if (configured_locs && configured_locs.length > 0) {
									let sumAvail = 0;
									configured_locs.forEach(locEntry => {
										let loc_id = (typeof locEntry === 'object' && locEntry.id) ? locEntry.id : locEntry;
										let val = parseFloat(stocks[loc_id] || stocks[String(loc_id)] || 0) || 0;
										sumAvail += val;
									});
									available = sumAvail;
								} else {
									let locConf = this.pos.config.stock_location_id;
									let loc_id = Array.isArray(locConf) ? locConf[0] : locConf;
									available = parseFloat(stocks[loc_id] || stocks[String(loc_id)] || 0) || 0;
								}
							}
							
							if(qty > available){
								if (available > 0) {
									// Ajustar cantidad al stock disponible sin mostrar popup
									quantity = available;
								} else {
									// No hay stock disponible: no permitir añadir la línea
									const msg = this.pos.env._t('The product you have selected may be out of stock in the default location.');
									try {
										Gui.showPopup('ErrorPopup', {
											title: this.pos.env._t('Out of Stock'),
											body: msg,
										});
									} catch (e) {
										console.warn(msg);
									}
									quantity = 'remove';
									return super.set_quantity(quantity, keep_price);
								}
							}
						}catch(e){
							console.error(e);
						}
					}
				}
			}
			return super.set_quantity(quantity, keep_price);
		}

		export_as_JSON(){
			var loaded = super.export_as_JSON(...arguments);
			loaded.stock_location_id = this.stock_location_id;
			return loaded;
		}
		init_from_JSON(json){
			super.init_from_JSON(...arguments);
			this.stock_location_id = json.stock_location_id;
		}

	}

	Registries.Model.extend(Orderline, BiCustomOrderLine);
});
