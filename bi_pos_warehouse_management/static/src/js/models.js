/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";

const Order = PosOrder;
const Orderline = PosOrderline;

patch(PosStore.prototype, {
    get pos_custom_location() {
        if (!this.models || !this.models['stock.location']) return [];
        return this.models['stock.location'].getAll();
    },
    get loc_by_id() {
        if (!this.models || !this.models['stock.location']) return {};
        const locs = {};
        for (let loc of this.models['stock.location'].getAll()) {
            locs[loc.id] = loc;
        }
        return locs;
    },
    get_product_total_qty(product) {
        if (typeof product === 'number' || typeof product === 'string') {
            let pid = parseInt(product);
            product = this.models['product.product'] ? this.models['product.product'].get(pid) : null;
        }
        if (!product || !(product.type === 'product' || product.type === 'consu')) return false;
        let quant_text = product.quant_text;
        if (!quant_text) return 0;
        try {
            let stocks = (typeof quant_text === 'string') ? JSON.parse(quant_text) : quant_text;
            let available = 0;
            let config = this.config;
            let configured_locs = config.warehouse_available_ids;
            if (configured_locs && configured_locs.length > 0) {
                let sumAvail = 0;
                configured_locs.forEach(locEntry => {
                    let loc_id = (typeof locEntry === 'object' && locEntry.id) ? locEntry.id : locEntry;
                    let val = parseFloat(stocks[loc_id] || stocks[String(loc_id)] || 0) || 0;
                    sumAvail += val;
                });
                available = sumAvail;
            } else {
                let locConf = config.stock_location_id;
                let loc_id = Array.isArray(locConf) ? locConf[0] : (locConf && locConf.id ? locConf.id : locConf);
                available = parseFloat(stocks[loc_id] || stocks[String(loc_id)] || 0) || 0;
            }
            return available;
        } catch (e) {
            return 0;
        }
    }
});

patch(Order.prototype, {
    setup(obj, options) {
        super.setup(...arguments);
        this.order_products = this.order_products || {};
        this.prd_qty = this.prd_qty || {};
    },
    export_as_JSON() {
        const loaded = super.export_as_JSON(...arguments);
        loaded.order_products = this.order_products || {};
        return loaded;
    },
    init_from_JSON(json) {
        super.init_from_JSON(...arguments);
        this.order_products = json.order_products || {};
        this.prd_qty = json.prd_qty || {};
    },
    calculate_prod_qty() {
        const pos = this.pos || this.store || this.env?.services?.pos || window.pos || {};
        const config = pos.config || this.config || {};
        const products = {};
        const orderlines = this.get_orderlines ? this.get_orderlines() : (this.lines || []);
        const config_loc = config.stock_location_id ? (Array.isArray(config.stock_location_id) ? config.stock_location_id[0] : config.stock_location_id) : false;
        
        if (this.prd_qty === undefined) {
            this.prd_qty = {};
        }
        if (this.order_products === undefined) {
            this.order_products = {};
        }
        if (orderlines.length > 0 && config.display_stock_pos) {
            orderlines.forEach((line) => {
                const prod = line.product || line.get_product?.();
                if (!prod) return;
                
                const qty = line.quantity || line.get_quantity?.() || 0;
                const loc = line.stock_location_id || config_loc;

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
        return products;
    }
});

patch(Orderline.prototype, {
    setup(obj, options) {
        super.setup(...arguments);
        this.stock_location_id = this.stock_location_id || false;
    },
    can_be_merged_with(orderline) {
        if (this.get_product().id === orderline.get_product().id) {
            return true;
        }
        return super.can_be_merged_with(...arguments);
    },
    set_quantity(quantity, keep_price) {
        const pos = this.pos || this.store || this.env?.services?.pos || window.pos || {};
        const config = pos.config || this.config || {};
        if (config.display_stock_pos && quantity !== 'remove' && quantity !== undefined) {
            let qty = parseFloat(quantity);
            const product = this.product || this.get_product?.();
            if (product && (product.type === 'product' || product.type === 'consu') && !isNaN(qty)) {
                let quant_text = product.quant_text;
                if (quant_text) {
                    try {
                        let stocks = (typeof quant_text === 'string') ? JSON.parse(quant_text) : quant_text;
                        let available = 0;
                        
                        if (this.stock_location_id) {
                            let loc_id = this.stock_location_id;
                            available = parseFloat(stocks[loc_id] || stocks[String(loc_id)] || 0) || 0;
                        } else {
                            let configured_locs = config.warehouse_available_ids;
                            if (configured_locs && configured_locs.length > 0) {
                                let sumAvail = 0;
                                configured_locs.forEach(locEntry => {
                                    let loc_id = (typeof locEntry === 'object' && locEntry.id) ? locEntry.id : locEntry;
                                    let val = parseFloat(stocks[loc_id] || stocks[String(loc_id)] || 0) || 0;
                                    sumAvail += val;
                                });
                                available = sumAvail;
                            } else {
                                let locConf = config.stock_location_id;
                                let loc_id = Array.isArray(locConf) ? locConf[0] : (locConf && locConf.id ? locConf.id : locConf);
                                available = parseFloat(stocks[loc_id] || stocks[String(loc_id)] || 0) || 0;
                            }
                        }
                        
                        if (qty > available) {
                            if (available > 0) {
                                quantity = available;
                            } else {
                                const msg = _t('The product you have selected may be out of stock in the default location.');
                                try {
                                    pos.env.services.dialog.add(AlertDialog, {
                                        title: _t('Out of Stock'),
                                        body: msg,
                                    });
                                } catch (e) {
                                    console.warn(msg);
                                }
                                let current_order = this.order || (pos.get_order ? pos.get_order() : null);
                                if (current_order && typeof current_order.removeOrderline === 'function') {
                                    current_order.removeOrderline(this);
                                } else if (this.order_id && typeof this.order_id.removeOrderline === 'function') {
                                    this.order_id.removeOrderline(this);
                                }
                                return true;
                            }
                        }
                    } catch (e) {
                        console.error(e);
                    }
                }
            }
        }
        return super.set_quantity(quantity, keep_price);
    },
    export_as_JSON() {
        const loaded = super.export_as_JSON(...arguments);
        loaded.stock_location_id = this.stock_location_id;
        return loaded;
    },
    init_from_JSON(json) {
        super.init_from_JSON(...arguments);
        this.stock_location_id = json.stock_location_id;
    }
});
