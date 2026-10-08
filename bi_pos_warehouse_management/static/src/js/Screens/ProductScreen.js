/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { PosStockWarehouse } from "@bi_pos_warehouse_management/js/Popup/PosStockWarehouse";
import { _t } from "@web/core/l10n/translation";

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

patch(PosStore.prototype, {
    _isForbiddenLoc(lid) {
        try {
            if (!lid) return false;
            const loc = this.loc_by_id && this.loc_by_id[lid];
            const name = loc ? (loc.complete_name || loc.name || '') : '';
            return FORBIDDEN_LOCATION_NAMES.some(fn => name === fn || name.includes(fn));
        } catch (e) {
            return false;
        }
    },

    async addLineToCurrentOrder(product, options = {}) {
        let order = this.get_order ? this.get_order() : (this.currentOrder || this.selectedOrder || (this.pos && this.pos.get_order ? this.pos.get_order() : null));
        if (!order) return super.addLineToCurrentOrder(...arguments);

        let partner_id = order.get_partner ? order.get_partner() : (order.partner || order.getPartner?.() || null);
        let location = this.config.stock_location_id;
        let other_locations = this.pos_custom_location;
        const normalizeLoc = (loc) => {
            if (Array.isArray(loc)) return loc[0];
            if (loc && typeof loc === 'object' && loc.id) return loc.id;
            return loc || 0;
        };
        let config_loc = normalizeLoc(this.config.stock_location_id);
        let product_id = product.id;
        let result = [];

        if ((product.type === 'product' || product.type === 'consu') && this.config.display_stock_pos) {
            let products = order.calculate_prod_qty();
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

            try {
                let output = await this.env.services.orm.call('stock.quant', 'get_product_stock', [location, other_locations, product_id]);
                result = output[1];
                if (result && result.length > 0) {
                    let stock_map = {};
                    result.forEach(r => {
                        stock_map[r.location.id] = r.quantity;
                    });
                    product['quant_text'] = JSON.stringify(stock_map);
                }
            } catch (e) {
                console.error("Stock validation error:", e);
            }

            let total_stock = 0;
            result.forEach((r) => {
                let rid = (r && r.location && r.location.id) ? r.location.id : r.location;
                if (allowedLocIds.has(rid) && !this._isForbiddenLoc(rid)) {
                    total_stock += (parseFloat(r.quantity) || 0);
                }
            });

            if (total_stock > used_qty) {
                return super.addLineToCurrentOrder(...arguments);
            } else {
                if (total_stock <= 0) {
                    this.env.services.dialog.add(AlertDialog, {
                        title: _t('Out of Stock'),
                        body: _t('No stock available in the configured locations.'),
                    });
                    return;
                }

                const confirmed = await new Promise((resolve) => {
                    this.env.services.dialog.add(ConfirmationDialog, {
                        title: _t('Out of Stock !!'),
                        body: _t('The product you have selected may be out of stock in the default location. Would you like to check other locations?'),
                        cancelText: _t('Add Anyway'),
                        confirmText: _t('Check Availability'),
                        confirm: () => resolve(true),
                        cancel: () => resolve(false),
                    });
                });

                if (confirmed) {
                    this.env.services.dialog.add(PosStockWarehouse, {
                        product: product,
                        result: result,
                    });
                } else {
                    return super.addLineToCurrentOrder(...arguments);
                }
            }
        } else {
            return super.addLineToCurrentOrder(...arguments);
        }
    },

    async pay() {
        const order = this.get_order ? this.get_order() : (this.currentOrder || this.selectedOrder || (this.pos && this.pos.get_order ? this.pos.get_order() : null));
        if (!order) return super.pay(...arguments);
        const lines = order.get_orderlines ? order.get_orderlines() : (order.lines || []);
        const pos_config = this.config;

        if (!pos_config.display_stock_pos) {
            return super.pay(...arguments);
        }

        let productIds = new Set();
        lines.forEach(line => {
            const prod = line.product || line.get_product?.();
            if (prod && (prod.type === 'product' || prod.type === 'consu')) {
                productIds.add(prod.id);
            }
        });

        let freshStock = {};
        let partner_id = order.get_partner ? order.get_partner() : (order.partner || order.getPartner?.() || null);
        let location = pos_config.stock_location_id;
        const normalizeLoc = (loc) => {
            if (Array.isArray(loc)) return loc[0];
            if (loc && typeof loc === 'object' && loc.id) return loc.id;
            return loc || 0;
        };
        location = normalizeLoc(location);
        let other_locations = this.pos_custom_location;
        let defaultLocId = location ? location : 0;
        let allowedLocIds = new Set();
        if (defaultLocId) allowedLocIds.add(defaultLocId);
        if (other_locations) {
            other_locations.forEach(l => {
                let lid = Array.isArray(l) ? l[0] : (l && l.id ? l.id : l);
                if (!this._isForbiddenLoc(lid)) allowedLocIds.add(lid);
            });
        }

        for (let pid of productIds) {
            try {
                let output = await this.env.services.orm.call('stock.quant', 'get_product_stock', [location, other_locations, pid]);
                if (output) {
                    let prodStock = {};
                    if (defaultLocId) prodStock[defaultLocId] = output[0] || 0;
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
                this.env.services.dialog.add(AlertDialog, {
                    title: _t('Error de conexión'),
                    body: _t('No se pudo verificar el stock. Intente de nuevo.'),
                });
                return;
            }
        }

        for (let line of lines) {
            if (!line.product || !(line.product.type === 'product' || line.product.type === 'consu')) {
                continue;
            }

            let pid = line.product.id;
            let qtyNeeded = line.get_quantity();
            let currentLocId = (line.stock_location_id ? (Array.isArray(line.stock_location_id) ? line.stock_location_id[0] : parseInt(line.stock_location_id)) : defaultLocId);

            let prodStockMap = freshStock[pid] || {};
            let currentAvailable = prodStockMap[currentLocId] || prodStockMap[String(currentLocId)] || 0;

            let totalAllowed = 0;
            let allowedList = Array.from(allowedLocIds);
            allowedList.forEach(lid => {
                totalAllowed += prodStockMap[lid] || prodStockMap[String(lid)] || 0;
            });

            if (allowedLocIds.has(currentLocId) && currentAvailable >= qtyNeeded) {
                prodStockMap[currentLocId] -= qtyNeeded;
            } else {
                if (totalAllowed >= qtyNeeded) {
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
                    this.env.services.dialog.add(AlertDialog, {
                        title: _t('Stock Insuficiente'),
                        body: _t(message),
                    });
                    return;
                }
            }
        }
        return super.pay(...arguments);
    }
});
