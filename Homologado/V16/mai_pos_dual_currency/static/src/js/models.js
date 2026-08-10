odoo.define('mai_pos_dual_currency.models', function(require) {
	"use strict";

	const { PosGlobalState, Order, Orderline, Payment } = require('point_of_sale.models');
	const Registries = require('point_of_sale.Registries');
	
	const PosRestaurantOrder = (Order) => class PosRestaurantOrder extends Order {
		
		add_paymentline(payment_method) {
			this.assert_editable();
			let rate_company = this.pos.config.rate_company;
			let show_currency_rate = this.pos.config.show_currency_rate;
			if (this.electronic_payment_in_progress()) {
				return false;
			} else {
				var newPaymentline = Payment.create({},{order: this, payment_method:payment_method, pos: this.pos});
				let due = this.get_due()

				if(this.get_igtf_charge() > 0){
					if (this.get_due() == 0){
						due = this.get_igtf_charge()
					}else{
						if(payment_method.is_igtf == false){
							due = this.get_due() + this.get_igtf_charge()
						}else{
							due = this.get_due()
						}
					}
				}else{

					// for (var line)
					let return_order = false
					for (var i = 0; i < this.orderlines.length; i++) {
						// change += this.orderlines[i].get_amount();
						if (this.orderlines[i].refunded_orderline_id) {
							return_order = true
							break;
						}
					}

					if (return_order){
						if (this.get_due() == 0){
							due = this.get_igtf_charge()
						}else{
							if(payment_method.is_igtf == false){
								due = this.get_due() + this.get_igtf_charge()
							}else{
								due = this.get_due()
							}
						}
					}else{
						due = this.get_due()
					}
				}

				newPaymentline.set_amount(due);
				if(payment_method.pago_usd){
					let price = due;
					if(rate_company > show_currency_rate){
						price =  show_currency_rate * due;
					}
					else if(rate_company < show_currency_rate){
						price = due /rate_company;
					}

					newPaymentline.set_usd_amt(price);

				}
				this.paymentlines.add(newPaymentline);
				this.select_paymentline(newPaymentline);
				if(this.pos.config.cash_rounding){
					this.selected_paymentline.set_amount(0);
			 		this.selected_paymentline.set_amount(due);
				}

				if (payment_method.payment_terminal) {
					newPaymentline.set_payment_status('pending');
				}
				return newPaymentline;
			}
		}
	   
	}
	Registries.Model.extend(Order, PosRestaurantOrder);

	const PosPayment = (Payment) => class PosPayment extends Payment {
		
		constructor() {
			super(...arguments);
			this.usd_amt = this.usd_amt || "";
		}
		
		//@override
		clone(){
			const orderline = super.clone(...arguments);
			orderline.usd_amt = this.usd_amt;
			return orderline;
		}
		//@override
		export_as_JSON(){
			const json = super.export_as_JSON(...arguments);
			json.usd_amt = this.usd_amt;
			return json;
		}
		//@override
		init_from_JSON(json){
			super.init_from_JSON(...arguments);
			this.usd_amt = json.usd_amt;
		}

		set_usd_amt(usd_amt){
			this.usd_amt = usd_amt;
		}

		get_usd_amt(){
			return this.usd_amt;
		}
	   
	}
	Registries.Model.extend(Payment, PosPayment);


});
