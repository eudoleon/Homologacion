/* Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>) */
/* See LICENSE file for full copyright and licensing details. */
/* License URL : <https://store.webkul.com/license.html/> */
odoo.define('pos_custom_discounts.pos_custom_discounts', function (require) {
	"use strict";
	const NumpadWidget = require('point_of_sale.NumpadWidget');
	const AbstractAwaitablePopup = require('point_of_sale.AbstractAwaitablePopup');
	const Registries = require('point_of_sale.Registries');
	var core = require('web.core');
	var _t = core._t;
	var PosDB = require('point_of_sale.DB');
	var { PosGlobalState, Orderline } = require('point_of_sale.models');
	const { Gui } = require('point_of_sale.Gui');
	const { onMounted } = owl;

	const WkPosCustomDiscount = PosGlobalState =>
		class extends PosGlobalState {
			async _processData(loadedData) {
				await super._processData(...arguments);
				this.db._loadPosCustomDiscount(loadedData['pos.custom.discount'])
			}
		}
	Registries.Model.extend(PosGlobalState, WkPosCustomDiscount);

	PosDB.include({
		_loadPosCustomDiscount: function (all_discounts) {
			if (all_discounts)
				this.all_discounts = all_discounts;
		},
	})

	const WkPosCustomDiscountOrderline = Orderline =>
		class extends Orderline {
			constructor(obj, options) {
				super(...arguments);
				self.custom_discount = self.custom_discount || '';
				self.custom_discount_reason = self.custom_discount_reason || '';
				self.list_discount = self.list_discount || false;
				self.selected_list_discount = self.selected_list_discount || false;
			}
			init_from_JSON(json) {
				var self = this;
				super.init_from_JSON(...arguments);
				self.custom_discount = json.custom_discount || '';
				self.custom_discount_reason = json.custom_discount_reason || '';
				self.list_discount = json.list_discount || false;
				self.selected_list_discount = json.selected_list_discount || false;
			}
			export_as_JSON() {
				var self = this;
				var loaded = super.export_as_JSON(...arguments);
				if (self.custom_discount_reason)
					loaded.custom_discount_reason = self.custom_discount_reason;
				if (self.custom_discount)
					loaded.custom_discount = self.custom_discount;
				if (self.list_discount)
					loaded.list_discount = self.list_discount;
				if (self.selected_list_discount)
					loaded.selected_list_discount = self.selected_list_discount;
				return loaded
			}
			export_for_printing() {
				var dict = super.export_for_printing(...arguments);
				dict.custom_discount = this.custom_discount;
				dict.custom_discount_reason = this.custom_discount_reason;
				dict.list_discount = this.list_discount;
				dict.selected_list_discount = this.selected_list_discount;
				return dict;
			}
			get_custom_discount_reason() {
				return this.custom_discount_reason;
			}

		}

	Registries.Model.extend(Orderline, WkPosCustomDiscountOrderline);

	// Popup WkCustomDiscountPopup
	class WkCustomDiscountPopup extends AbstractAwaitablePopup {
		setup() {
			super.setup();
			onMounted(this.onMounted);
		}
		onMounted() {
			if (this.props.custom_discount) {
				$("#discount").val(this.props.discount)
				$("#reason").val(this.props.custom_discount_reason)
			}

		}
		click_current_product(event) {
			if (($('#discount').val()) > 100 || $('#discount').val() <= 0) {
				$('#error_div').show();
				$('#customize_error').html('<i class="fa fa-exclamation-triangle" aria-hidden="true"></i > El Porcentaje de Descuento debe estar entre 0 a 100.')
			} else {
				var wk_customize_discount = parseFloat($('#discount').val())
				var reason = ($("#reason").val());
				var order = this.env.pos.get_order();
				order.get_selected_orderline().set_discount(wk_customize_discount);
				order.get_selected_orderline().custom_discount_reason = reason;
				order.get_selected_orderline().custom_discount = true;
				order.save_to_db();
				if (order._updateRewards) {
					order._updateRewards();
				}
				this.cancel();
			}
		}

		click_whole_order(event) {
			var self = this;
			var order = this.env.pos.get_order();
			var orderline_ids = order.get_orderlines();
			if (($('#discount').val()) > 100 || $('#discount').val() <= 0) {
				$('#error_div').show();
				$('#customize_error').html('<i class="fa fa-exclamation-triangle" aria-hidden="true"></i > El Porcentaje de Descuento debe estar entre 0 a 100.')
			} else {
				var wk_customize_discount = parseFloat($('#discount').val());
				var reason = ($("#reason").val());
				for (var i = 0; i < orderline_ids.length; i++) {
					orderline_ids[i].set_discount(wk_customize_discount);
					orderline_ids[i].custom_discount_reason = reason;
					orderline_ids[i].custom_discount = true;
				}
				order.save_to_db();
				if (order._updateRewards) {
					order._updateRewards();
				}
				self.cancel()
			}
		}
		async click_remove_discount() {
			var self = this;
			this.env.pos.get_order().get_selected_orderline().set_discount(0);
			this.env.pos.get_order().get_selected_orderline().custom_discount = false;
			this.env.pos.get_order().get_selected_orderline().custom_discount_reason = '';
			this.env.pos.get_order().save_to_db();
			if (this.env.pos.get_order()._updateRewards) {
				this.env.pos.get_order()._updateRewards();
			}
			self.cancel()
		}
	}
	WkCustomDiscountPopup.template = 'WkCustomDiscountPopup';
	WkCustomDiscountPopup.defaultProps = { title: 'Confirm ?', value: '' };
	Registries.Component.add(WkCustomDiscountPopup);

	// Popup WkDiscountPopup
	class WkDiscountPopup extends AbstractAwaitablePopup {
		setup() {
			super.setup();
			onMounted(this.onMounted);
		}
		onMounted() {
			var wk_discount_list = this.env.pos.db.all_discounts;
			this.wk_discount_percentage = 0;
			this.selected_discount = false;
			$(".button.apply").show();
			$(".button.apply_complete_order").show();
			$("#discount_error").hide();
			if (wk_discount_list && !wk_discount_list.length) {
				$(".button.apply_complete_order").hide();
				$(".button.apply").hide();
			}
			if (this.props.selected_list_discount) {
				$(".wk_popup_body span.wk_product_discount[id=" + this.props.selected_list_discount.id + "]").click()
			}
		}

		async click_remove_discount() {
			this.env.pos.get_order().get_selected_orderline().set_discount(0);
			this.env.pos.get_order().get_selected_orderline().list_discount = false;
			this.env.pos.get_order().get_selected_orderline().selected_list_discount = false;
			this.env.pos.get_order().save_to_db();
			if (this.env.pos.get_order()._updateRewards) {
				this.env.pos.get_order()._updateRewards();
			}
			this.cancel()
		}
		async wk_ask_password(password) {
			var ret = new $.Deferred();
			if (password) {
				const { confirmed, payload: inputPin } = await this.showPopup('NumberPopup', {
					isPassword: true,
					title: this.env._t('Password ?'),
					startingValue: null,
				});
				if (inputPin && Sha1.hash(inputPin) !== password) {
					Gui.showPopup('WebkulErrorPopup', {
						'title': _t('¡¡¡Contraseña incorrecta!!!'),
						'body': _('La contraseña ingresada es incorrecta')
					});
				} else {
					if (inputPin == null) {
						Gui.showPopup('WkDiscountPopup', {
							'title': _t("Listado de Descuentos"),
						});
					} else {
						ret.resolve();
					}
				}
			} else {
				ret.resolve();
			}
			return ret;
		}
		click_wk_product_discount(event) {
			$("#discount_error").hide();
			$(".wk_product_discount").css('background', 'white');
			var discount_id = parseInt($(event.currentTarget).attr('id'));
			$(event.currentTarget).css('background', '#6EC89B');
			var wk_discount_list = this.env.pos.db.all_discounts;
			for (var i = 0; i < wk_discount_list.length; i++) {
				if (wk_discount_list[i].id == discount_id) {
					var wk_discount = wk_discount_list[i];
					this.wk_discount_percentage = this.env.pos.format_currency_no_symbol(wk_discount.discount_percent);
					this.selected_discount = wk_discount;
				}
			}
		}
		click_customize(event) {
			var self = this;
			var employee = _.filter(self.env.pos.employees, function (employee) {
				return employee.id == self.env.pos.get_cashier().id;
			});
			if (self.env.pos.config.allow_security_pin && employee && employee[0] && employee[0].pin) {
				self.wk_ask_password(employee[0].pin).then(function (data) {
					Gui.showPopup('WkCustomDiscountPopup', {
						'title': self.env._t("Personalizar descuento"),
					});
				});
			} else {
				self.showPopup('WkCustomDiscountPopup', {
					'title': self.env._t("Personalizar descuento")
				});
			}
			self.cancel();
		}
		click_apply_complete_order(event) {
			var order = this.env.pos.get_order();
			if (this.wk_discount_percentage != 0) {
				var orderline_ids = order.get_orderlines();
				for (var i = 0; i < orderline_ids.length; i++) {
					orderline_ids[i].set_discount(this.wk_discount_percentage);
					orderline_ids.custom_discount_reason = '';
					orderline_ids.list_discount = true;
					orderline_ids.selected_list_discount = this.selected_discount;
				}
				// $('ul.orderlines li div#custom_discount_reason').text('');
				if (order._updateRewards) {
					order._updateRewards();
				}
				this.cancel();
			} else {
				$(".wk_product_discount").css("background-color", "burlywood");
				setTimeout(function () {
					$(".wk_product_discount").css("background-color", "");
				}, 100);
				setTimeout(function () {
					$(".wk_product_discount").css("background-color", "burlywood");
				}, 200);
				setTimeout(function () {
					$(".wk_product_discount").css("background-color", "");
				}, 300);
				setTimeout(function () {
					$(".wk_product_discount").css("background-color", "burlywood");
				}, 400);
				setTimeout(function () {
					$(".wk_product_discount").css("background-color", "");
				}, 500);
				return;
			}
		}
		click_apply(event) {
			var order = this.env.pos.get_order();
			if (this.wk_discount_percentage != 0) {
				order.get_selected_orderline().set_discount(this.wk_discount_percentage);
				order.get_selected_orderline().custom_discount_reason = '';
				order.get_selected_orderline().list_discount = true;
				order.get_selected_orderline().selected_list_discount = this.selected_discount;
				$('ul.orderlines li.selected div#custom_discount_reason').text('');
				if (order._updateRewards) {
					order._updateRewards();
				}
				this.cancel();
			} else {
				$(".wk_product_discount").css("background-color", "burlywood");
				setTimeout(function () {
					$(".wk_product_discount").css("background-color", "");
				}, 100);
				setTimeout(function () {
					$(".wk_product_discount").css("background-color", "burlywood");
				}, 200);
				setTimeout(function () {
					$(".wk_product_discount").css("background-color", "");
				}, 300);
				setTimeout(function () {
					$(".wk_product_discount").css("background-color", "burlywood");
				}, 400);
				setTimeout(function () {
					$(".wk_product_discount").css("background-color", "");
				}, 500);
				return;
			}
		}
	}
	WkDiscountPopup.template = 'WkDiscountPopup';
	WkDiscountPopup.defaultProps = { title: 'Confirm ?', value: '' };
	Registries.Component.add(WkDiscountPopup);

	// Popup WebkulErrorPopup
	class WebkulErrorPopup extends AbstractAwaitablePopup {
		click_password_ok_button(event) {
			this.cancel();
		}
	}
	WebkulErrorPopup.template = 'WebkulErrorPopup';
	WebkulErrorPopup.defaultProps = { title: 'Confirm ?', value: '' };
	Registries.Component.add(WebkulErrorPopup);

	// Inherit NumpadWidget----------------
	const PosResNumpadWidget = (NumpadWidget) =>
		class extends NumpadWidget {
			changeMode(mode) {
				var self = this;
				var selected_orderline = self.env.pos.get_order().get_selected_orderline()
				if (mode == 'discount' && selected_orderline) {
					if (self.env.pos.config.discount_ids.length || self.env.pos.config.allow_custom_discount) {
						if (selected_orderline && selected_orderline.list_discount && selected_orderline.selected_list_discount) {
							self.showPopup('WkDiscountPopup', {
								'title': self.env._t("Listado de Descuentos"),
								'selected_list_discount': selected_orderline.selected_list_discount
							});
						} else if (selected_orderline && selected_orderline.custom_discount) {
							self.showPopup('WkCustomDiscountPopup', {
								'title': self.env._t("Personalizar Descuento"),
								'discount': selected_orderline.discount,
								'custom_discount': true,
								'custom_discount_reason': selected_orderline.custom_discount_reason,
							});
						} else {
							self.showPopup('WkDiscountPopup', {
								'title': self.env._t("Listado de Descuentos"),
							});
						}
						return;
					} else {
						self.showPopup('WebkulErrorPopup', {
							'title': self.env._t('No hay Descuentos Disponibles'),
							'body': self.env._t('No hay descuento disponible para el TPV actual. Añada el descuento desde la configuración.')
						});
						return;
					}
				}
				else if (mode == 'discount') {
					self.showPopup('WebkulErrorPopup', {
						'title': self.env._t('No hay ninguna línea de pedido seleccionada'),
						'body': self.env._t('No se ha seleccionado ninguna línea de pedido. Añada o seleccione una.')
					});
					return;
				}
				super.changeMode(mode);
			}
		};
	Registries.Component.extend(NumpadWidget, PosResNumpadWidget);
});
