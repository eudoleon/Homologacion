odoo.define('mai_pos_dual_currency.CustomPaymentScreen', function(require) {
	'use strict';

	const PaymentScreen = require('point_of_sale.PaymentScreen');
	const Registries = require('point_of_sale.Registries');
	const NumberBuffer = require('point_of_sale.NumberBuffer');
	
	const CustomPaymentScreen = PaymentScreen => 
		class extends PaymentScreen {

			addNewPaymentLine({ detail: paymentMethod }) {
				var self = this;
				// original function: click_paymentmethods
				console.log("this---------------------",this)
				if (this.currentOrder.electronic_payment_in_progress()) {
					this.showPopup('ErrorPopup', {
						title: this.env._t('Error'),
						body: this.env._t('There is already an electronic payment in progress.'),
					});
					return false;
				}else{
					var payment_method = null;
					var igtf_pay = null;
					for (var i = 0; i < this.env.pos.payment_methods.length; i++ ) {
						if (this.env.pos.payment_methods[i].id === paymentMethod.id ){
							if(this.env.pos.payment_methods[i]['is_igtf'] === true){
								payment_method = this.env.pos.payment_methods[i];
								igtf_pay = true;
								break;
							}else{
								payment_method = this.env.pos.payment_methods[i];
								break;
							}   
						}
					}
					if(igtf_pay == true){
						var order = this.env.pos.get_order();
						var due = order.get_due();
						var total  = self.env.pos.company.igtf_percentage * 0.01 * due;
						this.env.pos.get_order().set_igtf_charge(total + order.get_igtf_charge());
						this.currentOrder.add_paymentline(payment_method);
						NumberBuffer.reset();
						this.payment_interface = payment_method.payment_terminal;
						if (this.payment_interface) {
							this.currentOrder.selected_paymentline.set_payment_status('pending');
						}
					}else{
						this.currentOrder.add_paymentline(paymentMethod);
						NumberBuffer.reset();
						this.payment_interface = paymentMethod.payment_terminal;
						if (this.payment_interface) {
							this.currentOrder.selected_paymentline.set_payment_status('pending');
						}
					}
					return true;
				}
			}
			
			_updateSelectedPaymentline() {
				let self = this;
				let rate_company = this.env.pos.config.rate_company;
				let show_currency_rate = this.env.pos.config.show_currency_rate;
						
				if (this.paymentLines.every((line) => line.paid)) {
					this.currentOrder.add_paymentline(this.payment_methods_from_config[0]);
				}
				if (!this.selectedPaymentLine) return; // do nothing if no selected payment line
				// disable changing amount on paymentlines with running or done payments on a payment terminal
				const payment_terminal = this.selectedPaymentLine.payment_method.payment_terminal;
				if (
					payment_terminal &&
					!['pending', 'retry'].includes(this.selectedPaymentLine.get_payment_status())
				) {
					return;
				}
				if (NumberBuffer.get() === null) {
					this.deletePaymentLine({ detail: { cid: this.selectedPaymentLine.cid } });
				} else {
					if(this.selectedPaymentLine.payment_method.is_igtf){
						var due = NumberBuffer.getFloat();

						let total = 0

						for (var i = 0; i < this.paymentLines.length; i++ ) {
							if (this.paymentLines[i].selected == false && this.paymentLines[i].payment_method.is_igtf){
								total  += this.env.pos.company.igtf_percentage * 0.01 * this.paymentLines[i].amount;
							}

						}
						

						// let	price_other_currency = due+total;
						total  += this.env.pos.company.igtf_percentage * 0.01 * due;
						let	price_other_currency = due;
						this.env.pos.get_order().set_igtf_charge(total);

						if(this.selectedPaymentLine.payment_method.pago_usd){
							let it = 0;
							if(rate_company > show_currency_rate){
								it = (total / show_currency_rate).toFixed(2);
							}else{
								it = ((total * show_currency_rate)/rate_company).toFixed(2);
							}
							this.env.pos.get_order().set_igtf_charge(parseFloat(it));
							// price_other_currency = price_other_currency * rate_company;
							price_other_currency = (rate_company * price_other_currency) / show_currency_rate;
							this.selectedPaymentLine.set_usd_amt(due+total);
						}

						this.selectedPaymentLine.set_amount(price_other_currency);
					}else{
						let	price_other_currency = NumberBuffer.getFloat();
						if(this.selectedPaymentLine.payment_method.pago_usd){
							// price_other_currency = price_other_currency * rate_company;
							price_other_currency = (rate_company * price_other_currency) / show_currency_rate;
							this.selectedPaymentLine.set_usd_amt(NumberBuffer.getFloat());
						}
						this.selectedPaymentLine.set_amount(price_other_currency);
					}

					
				}
			}


		}
	Registries.Component.extend(PaymentScreen, CustomPaymentScreen);
	return PaymentScreen;

});