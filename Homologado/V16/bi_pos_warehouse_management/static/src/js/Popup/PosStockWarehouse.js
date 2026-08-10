odoo.define('bi_pos_warehouse_management.PosStockWarehouse', function(require) {
	'use strict';

	const AbstractAwaitablePopup = require('point_of_sale.AbstractAwaitablePopup');
	const Registries = require('point_of_sale.Registries');
	var { PosGlobalState, Order, Orderline, models } = require('point_of_sale.models');
	let location_id = null;

	class PosStockWarehouse extends AbstractAwaitablePopup {
		setup() {
			super.setup();
            this.product = this.props.product;
			this.result = this.props.result;
			this.locations = this.result || [];
			this.location_id = null;
			owl.onMounted(this.onMounted);
        }
		
		onMounted(){
			let self = this;
			$('.warehouse-locations').each(function(){
				$('.raghav').removeClass('raghav');
				$(this).on('click',function (event) {
					if ( $(this).hasClass('raghav') )
					{
						$(this).removeClass('raghav');
						$(this).css("border", "1px solid #e2e2e2");
						self.location_id =  null;
					}
					else{
						$('.warehouse-locations').removeClass('raghav');
						$('.warehouse-locations').css("border", "1px solid #e2e2e2");
						$(this).addClass('raghav');	
						$(".raghav").css("border", "2px solid #6ec89b");
						self.location_id = parseInt(event.currentTarget.dataset['productId']);
						$('.warehouse-qty').css('display', 'block');
						$('#stock_qty').focus();
					}
				});
			});

		}

		cancel() {
			this.props.resolve({ confirmed: false, payload: null });
			this.showScreen('ProductScreen');
			this.env.posbus.trigger('close-popup', {
                popupId: this.props.id });
        

		}

		apply() {
			let self = this;
			let product = this.product;
			let result = this.result;
			
			let entered_qty = parseFloat($("#stock_qty").val() || 0) || 0;
			let order = this.env.pos.get_order();
			let location_id = self.location_id;
			// Calcular stock total en las ubicaciones disponibles
			let total_available = 0;
			if (result && result.length) {
				for (let i = 0; i < result.length; i++) {
					total_available += parseFloat(result[i].quantity) || 0;
				}
			}
			// Allow only if stock is sufficient (do not allow when total available is 0)
			if (entered_qty > 0 && total_available >= entered_qty) {
				// Buscar la línea existente solo por producto (sumaremos cantidades de todas las ubicaciones)
				var old_orderline = order.get_orderlines();
				old_orderline = old_orderline.filter(function(item){
					return item.product.id == product.id;
				});

				if (old_orderline.length > 0) {
					// usar float para sumar cantidades (soporta kg)
					old_orderline[0].set_quantity(parseFloat(old_orderline[0].quantity) + entered_qty);
					// seleccionar la línea actualizada para sincronizar el Numpad
					let real_line = order.get_orderlines().find(l => l.id === old_orderline[0].id) || old_orderline[0];
					if (real_line) {
						order.select_orderline(real_line);
					}
					try{
						$('.numpad .value').text('');
						$('.numpad .input, .numpad input').val('');
						const NumberBuffer = require('point_of_sale.NumberBuffer');
						if (NumberBuffer && NumberBuffer.reset) NumberBuffer.reset();
					} catch (e) { /* ignore */ }
					location_id = null;
					this.showScreen('ProductScreen');
					self.env.posbus.trigger('close-popup', {popupId: self.props.id});
				} else {
					var orderline = Orderline.create({}, {pos: this.env.pos, order: order, product: product});
					orderline.product = product;
					// No asignar ubicación: permitimos que la línea represente stock agregado de todas las ubicaciones
					orderline.set_quantity(entered_qty);
					order.add_orderline(orderline);
					let new_line = order.get_last_orderline();
					if (new_line) {
						order.select_orderline(new_line);
						try{
							$('.numpad .value').text('');
							$('.numpad .input, .numpad input').val('');
							const NumberBuffer = require('point_of_sale.NumberBuffer');
							if (NumberBuffer && NumberBuffer.reset) NumberBuffer.reset();
						} catch (e) { /* ignore */ }
					}
					location_id = null;
					this.showScreen('ProductScreen');
					self.env.posbus.trigger('close-popup', {popupId: self.props.id});
				}
			} else if (entered_qty <= 0) {
				self.showPopup('ErrorPopup', {
					title: self.env._t('Invalid Quantity'),
					body: self.env._t('Please enter a quantity greater than zero.'),
				});
			} else {
				let msg = 'Available total: ' + total_available + '. You entered: ' + entered_qty;
				self.showPopup('ErrorPopup', {
					title: self.env._t('Please enter valid amount of quantity.'),
					body: self.env._t(msg),
				});
			}
		}
	}

	PosStockWarehouse.template = 'PosStockWarehouse';
	PosStockWarehouse.defaultProps = {
		confirmText: 'Apply',
		cancelText: 'Cancel',
		title: 'Confirm ?',
		body: '',
	};

	Registries.Component.add(PosStockWarehouse);

	return PosStockWarehouse;
});
