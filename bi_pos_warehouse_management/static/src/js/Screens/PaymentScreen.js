/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { _t } from "@web/core/l10n/translation";

import { PosOutOfStock } from "@bi_pos_warehouse_management/js/Popup/PosOutOfStock";

patch(PaymentScreen.prototype, {
    async validateOrder(isForceValidate) {
        let order = this.currentOrder;
        let products = order.calculate_prod_qty();
        const pos = this.pos || this.env?.services?.pos || window.pos || {};
        let pos_config = pos.config || this.config || {};
        let partner_id = order.get_partner ? order.get_partner() : (order.partner || order.getPartner?.() || null);
        let location = pos_config.stock_location_id;
        let other_locations = pos.pos_custom_location;

        let res = {};
        let call_super = true;

        if (pos_config.display_stock_pos) {
            for (const prod_id in products) {
                try {
                    let output = await this.env.services.orm.call('stock.quant', 'get_product_stock', [
                        partner_id ? partner_id.id : false, 
                        location, 
                        other_locations, 
                        parseInt(prod_id)
                    ]);
                    res[prod_id] = output[1];
                } catch (e) {
                    console.error("Error fetching stock during validateOrder", e);
                }
            }

            let processed_keys = {};

            for (const [prod_id, loc_data] of Object.entries(products)) {
                let product = this.pos.db.get_product_by_id(prod_id);
                if (product && product.has_bom) {
                    continue;
                }
                for (const [loc_id, line_data] of Object.entries(loc_data)) {
                    let key_unique = `${prod_id}_${loc_id}`;
                    if (processed_keys[key_unique]) continue;
                    processed_keys[key_unique] = true;

                    let qty = line_data.qty;
                    let prd = line_data.name;
                    let ol = line_data.line;

                    if (this.pos.loc_by_id && this.pos.loc_by_id[loc_id]) {
                        let loc_name = this.pos.loc_by_id[loc_id]['complete_name'];
                        let loc_list = [];
                        let data = {};

                        let resProd = res[prod_id] || [];
                        for (let v of resProd) {
                            let id = v.location.id;
                            if (v.quantity != 0) {
                                loc_list.push([
                                    this.pos.loc_by_id[id]?.complete_name,
                                    v.quantity,
                                    id
                                ]);
                            }
                            data[id] = v.quantity;
                        }

                        if (qty > (data[loc_id] || 0)) {
                            let wrning = prd + ': required ' + qty;
                            let odrln = order.get_orderline ? order.get_orderline(ol) : (order.lines ? order.lines.find(l => l.id === ol) : null);
                            if (odrln && typeof odrln.set_quantity === 'function') {
                                odrln.set_quantity(data[loc_id] || 0);
                            }
                            call_super = false;
                            
                            // Try to show popup
                            try {
                                this.env.services.dialog.add(PosOutOfStock, {
                                    'title': _t('Out of Stock'),
                                    'warning': _t(wrning),
                                });
                            } catch(e) {
                                console.warn(wrning);
                            }
                        }
                    }
                }
            }
        }

        if (call_super) {
            super.validateOrder(isForceValidate);
        }
    }
});
