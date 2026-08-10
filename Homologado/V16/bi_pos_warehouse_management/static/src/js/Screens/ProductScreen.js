odoo.define('bi_pos_warehouse_management.ProductScreen', function(require) {
	"use strict";

	const ProductScreen = require('point_of_sale.ProductScreen');
	const PosComponent = require('point_of_sale.PosComponent');
	const Registries = require('point_of_sale.Registries');
	const { useListener } = require("@web/core/utils/hooks");
	const { useState } = owl;
	const { parse } = require('web.field_utils');
	const NumberBuffer = require('point_of_sale.NumberBuffer');

	// Nombres de ubicaciones excluidas (no tomar stock de aquí)
	const FORBIDDEN_LOCATION_NAMES = [
		'PISOV/stock/Depósito/Vencidos',
		'PISOV/stock/Depósito/Freezer 1',
		'PISOV/stock/Depósito/Freezer 2',
		'PISOV/stock/Depósito/Freezer 3',
		'PISOV/stock/Depósito/Freezer 4',
		'FNORT/Stock/Estanteria',
		'FNORT/Stock',
		'Event/Stock',
		'Depos/Stock/vencidos',
		'Depos/Stock/Produccion cocina',
		'Depos/Stock/Freezer 1',
		'Depos/Stock/Freezer 2',
		'Depos/Stock/Freezer 3',
		'Depos/Stock/Freezer 4',
		'Depos/Stock/Freezer 5',
		'Depos/Stock/Devolucion',
		'Depos/Stock/Averias',
		'Depos/Stock'
	];

    const BiProductScreen = (ProductScreen) =>
    class extends ProductScreen {

		_isForbiddenLoc(lid) {
			try {
				if (!lid) return false;
				const loc = this.env.pos.loc_by_id && this.env.pos.loc_by_id[lid];
				const name = loc ? (loc.complete_name || loc.name || '') : '';
				return FORBIDDEN_LOCATION_NAMES.some(fn => name === fn || name.includes(fn));
			} catch (e) {
				return false;
			}
		}

		setup() {
			super.setup();
			// Desactivar reasignación/selección automática de ubicaciones en tiempo real
			// No iniciar el polling de stock para evitar cambios automáticos en las líneas
		}

		willUnmount() {
			super.willUnmount && super.willUnmount();
			this._stopStockPolling && this._stopStockPolling();
		}

		_startStockPolling() {
			this._stopStockPolling();
			this._stockPollingInterval = setInterval(async () => {
				const order = this.env.pos.get_order();
				const selectedLine = order && order.get_selected_orderline && order.get_selected_orderline();
				if (!selectedLine || !selectedLine.product || selectedLine.product.type !== 'product' || selectedLine.product.has_bom) return;
				if (!this.env.pos.config.display_stock_pos) return;

				let partner_id = this.env.pos.get_order().get_partner();
				let location = this.env.pos.config.stock_location_id;
				let other_locations = this.env.pos.pos_custom_location;
				let product = selectedLine.product;
				let product_id = product.id;

				let output;
				try {
					output = await this.rpc({
						model: 'stock.quant',
						method: 'get_product_stock',
						args: [partner_id, location, other_locations, product_id],
					});
				} catch (e) {
					return;
				}

				let quant_text = null;
				if (output && output[1]) {
					let result = output[1];
					if (result && result.length > 0) {
						let stock_map = {};
						result.forEach(r => {
							stock_map[r.location.id] = r.quantity;
						});
						product['quant_text'] = JSON.stringify(stock_map);
						quant_text = product['quant_text'];
					}
				}
				if (!quant_text && this.env.pos.prod_with_quant && this.env.pos.prod_with_quant[selectedLine.product.id]) {
					quant_text = this.env.pos.prod_with_quant[selectedLine.product.id];
				}
				if (!quant_text) return;

				let stocks = (typeof quant_text === 'string') ? JSON.parse(quant_text) : quant_text;
				let configured_locs = this.env.pos.config.warehouse_available_ids || [];
				let orderlines = order.get_orderlines();

				// Calcular la cantidad total deseada para este producto (sumando todas las líneas)
				let totalQty = 0;
				orderlines.forEach(l => {
					if (l.product && l.product.id === selectedLine.product.id) {
						totalQty += parseFloat(l.get_quantity() || 0);
					}
				});

				// Calcular el stock disponible en cada ubicación y repartir la cantidad total entre todas
				let usageMap = {};
				orderlines.forEach(l => {
					if (l.product && l.product.id === selectedLine.product.id && l.stock_location_id) {
						let loc = parseInt(l.stock_location_id);
						usageMap[loc] = (usageMap[loc] || 0) + parseFloat(l.get_quantity() || 0);
					}
				});

				let totalAvailable = 0;
				let locsWithStock = [];
				for (let locEntry of configured_locs) {
					let loc_id = (typeof locEntry === 'object' && locEntry.id) ? locEntry.id : locEntry;
					if (this._isForbiddenLoc(loc_id)) continue;
					let stockAtLoc = stocks.hasOwnProperty(loc_id) ? parseFloat(stocks[loc_id]) || 0 : 0;
					let used = usageMap[loc_id] || 0;
					let availableAtLoc = stockAtLoc - used + used; // sumar lo que ya tiene la línea
					if (availableAtLoc > 0) {
						totalAvailable += availableAtLoc;
						locsWithStock.push({loc_id, availableAtLoc});
					}
				}

				let qtyToSet = Math.min(totalQty, totalAvailable);
				let qtyRestante = qtyToSet;

				// Repartir la cantidad entre las ubicaciones, actualizando o creando líneas
				for (let i = 0; i < locsWithStock.length; i++) {
					let {loc_id, availableAtLoc} = locsWithStock[i];
					let qtyForLoc = Math.min(qtyRestante, availableAtLoc);
					let line = orderlines.find(l =>
						l.product.id === selectedLine.product.id &&
						l.stock_location_id == loc_id
					);
					if (qtyForLoc > 0) {
						if (line && typeof line.set_quantity === 'function') {
							line.set_quantity(qtyForLoc);
						} else if (!line) {
							let newLine = order.add_product(selectedLine.product, {
								extras: { stock_location_id: loc_id },
							});
							if (newLine && typeof newLine.set_quantity === 'function') {
								newLine.stock_location_id = loc_id;
								newLine.set_quantity(qtyForLoc);
							} else if (newLine) {
								newLine.quantity = qtyForLoc;
							}
						}
						qtyRestante -= qtyForLoc;
					} else if (line && typeof line.set_quantity === 'function') {
						line.set_quantity(0);
					} else if (line) {
						line.quantity = 0;
					}
					if (qtyRestante <= 0) break;
				}
				// Eliminar líneas con cantidad 0
				order.get_orderlines().forEach(l => {
					if (
						l.product.id === selectedLine.product.id &&
						l.quantity <= 0
					) {
						order.remove_orderline(l);
					}
				});

				// Quitar la selección de ubicación en tiempo real si la cantidad total es mayor que el stock de la ubicación seleccionada
				if (selectedLine && selectedLine.stock_location_id) {
					let selectedLocId = parseInt(selectedLine.stock_location_id);
					let selectedLocStock = stocks[selectedLocId] || 0;
					let selectedLocLineQty = orderlines
						.filter(l => l.product.id === selectedLine.product.id && l.stock_location_id == selectedLocId)
						.reduce((sum, l) => sum + parseFloat(l.get_quantity() || 0), 0);
					if (selectedLocLineQty > selectedLocStock) {
						selectedLine.stock_location_id = null;
					}
				}
				return;
			}, 5000); // cada 5 segundos
		}

		_stopStockPolling() {
			if (this._stockPollingInterval) {
				clearInterval(this._stockPollingInterval);
				this._stockPollingInterval = null;
			}
		}

		async _updateSelectedOrderline(event) {
			const order = this.env.pos.get_order();
			// Añadimos await para asegurarnos de que la limpieza del buffer funciona
			const selectedLine = order.get_selected_orderline();
			
			if (this.env.pos.config.display_stock_pos && 
				this.env.pos.numpadMode === 'quantity' && 
				selectedLine && 
				selectedLine.product && 
				selectedLine.product.type === 'product' && 
				!selectedLine.product.has_bom) {
					
				try {
					let partner_id = this.env.pos.get_order().get_partner();
					let location = this.env.pos.config.stock_location_id;
					const normalizeLoc = (loc) => {
						if (Array.isArray(loc)) return loc[0];
						if (loc && typeof loc === 'object' && loc.id) return loc.id;
						return loc || 0;
					};
					location = normalizeLoc(location);
					let other_locations = this.env.pos.pos_custom_location;
					let product = selectedLine.product;
					let product_id = product.id;

					let output = await this.rpc({
						model: 'stock.quant',
						method: 'get_product_stock',
						args: [partner_id, location, other_locations, product_id],
					});

					if (output && output[1]) {
						let result = output[1];
						if (result && result.length > 0) {
							let stock_map = {};
							result.forEach(r => {
								stock_map[r.location.id] = r.quantity;
							});
							product['quant_text'] = JSON.stringify(stock_map);
						}
					}
				} catch (e) {
					console.error("Stock validation error:", e);
				}

				const inputVal = event.detail.buffer;
				const newQty = inputVal === null ? 0 : parseFloat(inputVal) || 0;
				const currentQty = selectedLine.quantity;
				
				let quant_text = selectedLine.product.quant_text;
				
				// Fallback to global data if product data missing
				if (!quant_text && this.env.pos.prod_with_quant && this.env.pos.prod_with_quant[selectedLine.product.id]) {
					quant_text = this.env.pos.prod_with_quant[selectedLine.product.id];
				}

				if (quant_text) {
					try {
						let stocks = (typeof quant_text === 'string') ? JSON.parse(quant_text) : quant_text;
						let available = 0;

						if (selectedLine.stock_location_id) {
							let loc_id = parseInt(selectedLine.stock_location_id);
							if (stocks.hasOwnProperty(loc_id)) {
								available = stocks[loc_id];
							} else if (stocks.hasOwnProperty(String(loc_id))) {
								available = stocks[String(loc_id)];
							}
						} else {
							// Sumar el stock de todas las ubicaciones configuradas (excluyendo ubicaciones prohibidas)
								let configured_locs = this.env.pos.config.warehouse_available_ids || [];
								let totalAvailable = 0;
								if (configured_locs && configured_locs.length > 0) {
									configured_locs.forEach(locEntry => {
										let loc_id = Array.isArray(locEntry) ? locEntry[0] : (locEntry && locEntry.id ? locEntry.id : locEntry);
										if (this._isForbiddenLoc(loc_id)) return;
										let val = 0;
										if (stocks.hasOwnProperty(loc_id)) val = parseFloat(stocks[loc_id]) || 0;
										else if (stocks.hasOwnProperty(String(loc_id))) val = parseFloat(stocks[String(loc_id)]) || 0;
										totalAvailable += val;
									});
								} else {
									let locConf = this.env.pos.config.stock_location_id;
									let loc_id = Array.isArray(locConf) ? locConf[0] : locConf;
									if (stocks.hasOwnProperty(loc_id)) {
										totalAvailable = parseFloat(stocks[loc_id]) || 0;
									} else if (stocks.hasOwnProperty(String(loc_id))) {
										totalAvailable = parseFloat(stocks[String(loc_id)]) || 0;
									}
								}
								// Restar la cantidad que ya está usada por otras líneas del mismo producto (excluyendo la línea seleccionada)
								try {
									let usedByOtherLines = 0;
									order.get_orderlines().forEach(l => {
										if (l.product && l.product.id === selectedLine.product.id && l !== selectedLine) {
											usedByOtherLines += parseFloat(l.get_quantity() || 0);
										}
									});
									available = Math.max(0, totalAvailable - usedByOtherLines);
								} catch (e) {
									available = totalAvailable;
								}
						}
						
						// Si el nuevo qty excede la disponibilidad local, no reasignar automáticamente.
						if (newQty > available && newQty > currentQty) {
							await this.showPopup('ErrorPopup', {
								title: this.env._t('Límite de stock excedido'),
								body: this.env._t('No se puede aumentar la cantidad automáticamente a otra ubicación. Seleccione la ubicación manualmente.'),
							});
							NumberBuffer.reset();
							return;
						}
					} catch (e) {
						console.error("Stock validation error:", e);
					}
				}
			}
			
			await super._updateSelectedOrderline(event);
		}

		async _clickProduct(event) {
			let self = this;
			const product = event.detail;
			let order = self.env.pos.get_order();
			let partner_id = order.get_partner();
			let location = self.env.pos.config.stock_location_id;
			let other_locations = self.env.pos.pos_custom_location;
			const normalizeLoc = (loc) => {
				if (Array.isArray(loc)) return loc[0];
				if (loc && typeof loc === 'object' && loc.id) return loc.id;
				return loc || 0;
			};
			let config_loc = normalizeLoc(self.env.pos.config.stock_location_id);
			let product_id = product['id'];
			let result = [];
		
			if (product.type === 'product' && self.env.pos.config.display_stock_pos && !product.has_bom) {
				let products = order.calculate_prod_qty();
				// Calcular cantidad ya usada del producto en las ubicaciones permitidas
				let used_qty = 0;
				let allowedLocIds = new Set();
				if (config_loc && !this._isForbiddenLoc(config_loc)) allowedLocIds.add(config_loc);
				if (other_locations) {
					other_locations.forEach(l => {
						let lid = Array.isArray(l) ? l[0] : (l && l.id ? l.id : l);
						if (!this._isForbiddenLoc(lid)) allowedLocIds.add(lid);
					});
				}
				if (products[product_id]) {
					for (let locKey in products[product_id]) {
						let locNum = parseInt(locKey);
						if (allowedLocIds.has(locNum)) {
							used_qty += products[product_id][locKey].qty || 0;
						}
					}
				}
			
				await this.rpc({
					model: 'stock.quant',
					method: 'get_product_stock',
					args: [partner_id, location, other_locations, product_id],
				}).then(function (output) {
					result = output[1];
					if (result && result.length > 0) {
						let stock_map = {};
						result.forEach(r => {
							stock_map[r.location.id] = r.quantity;
						});
						product['quant_text'] = JSON.stringify(stock_map);
					}
				});
			
				// Calcular stock total en las ubicaciones permitidas devueltas
				let total_stock = 0;
				result.forEach((r) => {
					let rid = (r && r.location && r.location.id) ? r.location.id : r.location;
					if (allowedLocIds.has(rid) && !this._isForbiddenLoc(rid)) {
						total_stock += (parseFloat(r.quantity) || 0);
					}
				});
				// Si hay stock total disponible mayor que lo ya usado, permitir añadir normalmente
				if (total_stock > used_qty) {
					super._clickProduct(event);
				} else {
					// Si no hay stock en absoluto, bloquear la adición y mostrar error
					if (total_stock <= 0) {
						await self.showPopup('ErrorPopup', {
							title: this.env._t('Out of Stock'),
							body: this.env._t('No stock available in the configured locations.'),
						});
						return;
					}
					// No hay suficiente stock en la ubicación por defecto: ofrecer al usuario elegir manualmente.
					await self._getAddProductOptions(product);
					const { confirmed } = await this.showPopup('ConfirmPopup', {
						title: this.env._t('Out of Stock !!'),
						body: this.env._t('The product you have selected may be out of stock in the default location. Would you like to check other locations?'),
						cancelText: this.env._t('Add Anyway'),
						confirmText: this.env._t('Check Availability'),
						product: product,
						result: result,
					});
					if (confirmed) {
						await this.showPopup('PosStockWarehouse', {
							'product': product,
							'result': result,
						});
					} else {
						super._clickProduct(event);
					}
				}
			} else {
				super._clickProduct(event);
			}
		}
		

		async _onClickPay() {
			const order = this.env.pos.get_order();
			const lines = order.get_orderlines();
			const pos_config = this.env.pos.config;

			// Si la configuración de stock no está activa, pasamos directamente
			if (!pos_config.display_stock_pos) {
				return super._onClickPay();
			}

			// Preparar lista de productos únicos para consultar stock
			let productIds = new Set();
			lines.forEach(line => {
				if (line.product && line.product.type === 'product' && !line.product.has_bom) {
					productIds.add(line.product.id);
				}
			});

			// Mapas para control de stock
			// freshStock[productId][locationId] = quantity
			let freshStock = {};
			
			let partner_id = order.get_partner();
			let location = pos_config.stock_location_id;
			const normalizeLoc = (loc) => {
				if (Array.isArray(loc)) return loc[0];
				if (loc && typeof loc === 'object' && loc.id) return loc.id;
				return loc || 0;
			};
			location = normalizeLoc(location);
			let other_locations = this.env.pos.pos_custom_location;
			
			// Ubicación por defecto
			let defaultLocId = location ? location : 0;
			
			// Lista de IDs permitidos (Ubicaciones configuradas + Default)
			let allowedLocIds = new Set();
			if (defaultLocId) allowedLocIds.add(defaultLocId);
			if (other_locations) {
				other_locations.forEach(l => {
					let lid = Array.isArray(l) ? l[0] : (l && l.id ? l.id : l);
					if (!this._isForbiddenLoc(lid)) allowedLocIds.add(lid);
				});
			}

			// Obtener stock fresco de todos los productos
			for (let pid of productIds) {
				try {
					let output = await this.rpc({
						model: 'stock.quant',
						method: 'get_product_stock',
						args: [partner_id, location, other_locations, pid],
					});

					if (output) {
						let prodStock = {};
						// Stock en ubicación por defecto
						if (defaultLocId) {
							prodStock[defaultLocId] = output[0] || 0;
						}
						// Stock en otras ubicaciones
						if (output[1]) {
							output[1].forEach(r => {
								let rid = (r && r.location && r.location.id) ? r.location.id : r.location;
								if (!this._isForbiddenLoc(rid)) prodStock[rid] = r.quantity;
							});
						}
						freshStock[pid] = prodStock;
					}
				} catch (e) {
					console.error("Error fetching stock for product", pid, e);
					await this.showPopup('ErrorPopup', {
						title: this.env._t('Error de conexión'),
						body: this.env._t('No se pudo verificar el stock. Intente de nuevo.'),
					});
					return;
				}
			}

			// Validar y Reasignar líneas
			let blocked = false;

			for (let line of lines) {
				if (!line.product || line.product.type !== 'product' || line.product.has_bom) {
					continue;
				}

				let pid = line.product.id;
				let qtyNeeded = line.get_quantity();
				// Ubicación actual de la línea o default (Asegurar Entero para validación en Set)
				let currentLocId = (line.stock_location_id ? (Array.isArray(line.stock_location_id) ? line.stock_location_id[0] : parseInt(line.stock_location_id)) : defaultLocId);
				
				// Stock disponible en la ubicación seleccionada
					let prodStockMap = freshStock[pid] || {};
					let currentAvailable = prodStockMap[currentLocId] || prodStockMap[String(currentLocId)] || 0;

				// VALIDACIÓN: Si la ubicación actual tiene stock suficiente, usamos esa. 
				// Si no, pero el stock total en ubicaciones permitidas es suficiente, permitimos continuar (sin reasignar automáticamente).
				// Calcular stock total en ubicaciones permitidas
				let totalAllowed = 0;
				let allowedList = Array.from(allowedLocIds);
				allowedList.forEach(lid => {
					totalAllowed += prodStockMap[lid] || prodStockMap[String(lid)] || 0;
				});

				// DEBUG: imprimir información clave para depuración
				try {
					console.log('POS-STOCK-CHECK', {
						product: line.product.display_name,
						pid: pid,
						qtyNeeded: qtyNeeded,
						currentLocId: currentLocId,
						currentAvailable: currentAvailable,
						allowedLocIds: Array.from(allowedLocIds),
						totalAllowed: totalAllowed,
						prodStockMap: prodStockMap,
					});
				} catch (e) { /* ignore logging errors */ }

				if (allowedLocIds.has(currentLocId) && currentAvailable >= qtyNeeded) {
					prodStockMap[currentLocId] -= qtyNeeded;
				} else {
					if (totalAllowed >= qtyNeeded) {
						// Consumir del mapa temporal distribuyendo entre ubicaciones permitidas
						let remaining = qtyNeeded;
						for (let lid of allowedList) {
							let availableAt = prodStockMap[lid] || prodStockMap[String(lid)] || 0;
							if (availableAt <= 0) continue;
							let take = Math.min(availableAt, remaining);
							prodStockMap[lid] = (prodStockMap[lid] || prodStockMap[String(lid)] || 0) - take;
							remaining -= take;
							if (remaining <= 0) break;
						}
					} else {
						let productName = line.product.display_name;
						let message = `El producto "${productName}" no tiene suficiente stock en las ubicaciones permitidas.`;
						await this.showPopup('ErrorPopup', {
							title: this.env._t('Stock Insuficiente'),
							body: this.env._t(message),
						});
						return; // Detener proceso al primer error
					}
				}
			}

			// Si llegamos aquí, todas las líneas tienen asignada una ubicación con stock suficiente.
			super._onClickPay();
		}

	};

	Registries.Component.extend(ProductScreen, BiProductScreen);

	return ProductScreen;
});
