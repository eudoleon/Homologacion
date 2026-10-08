/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { ReceiptScreen } from "@point_of_sale/app/screens/receipt_screen/receipt_screen";

patch(ReceiptScreen.prototype, {
    setup() {
        super.setup(...arguments);
        const order = this.currentOrder;
        if (!order) {
            return;
        }
        let orderlines = order.get_orderlines ? order.get_orderlines() : (order.lines || []);
        const pos = this.pos || this.env?.services?.pos || window.pos || {};
        let config = pos.config || this.config || {};
        let config_loc = config.stock_location_id ? (Array.isArray(config.stock_location_id) ? config.stock_location_id[0] : config.stock_location_id) : false;
        
        for (let line of orderlines) {
            let prd = line.product || line.get_product?.();
            if (prd && (prd.type === 'product' || prd.type === 'consu')) {
                let loc = line.stock_location_id;
                if (!loc) {
                    loc = config_loc;
                }
                if (prd.quant_text) {
                    try {
                        let stocks = (typeof prd.quant_text === 'string') ? JSON.parse(prd.quant_text) : prd.quant_text;
                        let qtyToDeduct = line.quantity || line.get_quantity?.() || 0;
                        if (stocks[loc]) {
                            stocks[loc] -= qtyToDeduct;
                            prd.quant_text = typeof prd.quant_text === 'string' ? JSON.stringify(stocks) : stocks;
                        } else if (stocks[String(loc)]) {
                            stocks[String(loc)] -= qtyToDeduct;
                            prd.quant_text = typeof prd.quant_text === 'string' ? JSON.stringify(stocks) : stocks;
                        }
                    } catch (e) {
                        console.error(e);
                    }
                }
            }
        }
    }
});