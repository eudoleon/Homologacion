/** @odoo-module */

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class PosStockWarehouse extends Component {
    static template = 'bi_pos_warehouse_management.PosStockWarehouse';
    static components = { Dialog };
    static props = {
        product: Object,
        result: Array,
        close: Function,
        title: { type: String, optional: true },
        confirmText: { type: String, optional: true },
        cancelText: { type: String, optional: true },
    };

    setup() {
        this.pos = useService("pos");
        this.state = useState({
            location_id: null,
            entered_qty: 0,
        });
    }

    selectLocation(loc_id) {
        if (this.state.location_id === loc_id) {
            this.state.location_id = null;
        } else {
            this.state.location_id = loc_id;
        }
    }

    cancel() {
        this.props.close();
    }

    apply() {
        let product = this.props.product;
        let result = this.props.result;
        let entered_qty = parseFloat(this.state.entered_qty) || 0;
        let order = this.pos.get_order ? this.pos.get_order() : (this.pos.selectedOrder || this.pos.getOrder?.());
        let location_id = this.state.location_id;

        let total_available = 0;
        if (result && result.length) {
            for (let i = 0; i < result.length; i++) {
                total_available += parseFloat(result[i].quantity) || 0;
            }
        }

        let orderlines = order.get_orderlines ? order.get_orderlines() : (order.lines || []);
        if (order && entered_qty > 0 && total_available >= entered_qty) {
            let old_orderline = orderlines.filter(item => item.product.id === product.id);

            if (old_orderline.length > 0) {
                let line = old_orderline[0];
                if (typeof line.set_quantity === 'function') {
                    line.set_quantity(parseFloat(line.get_quantity() || line.quantity) + entered_qty);
                }
                order.select_orderline(line);
                this.props.close();
            } else {
                this.pos.addLineToCurrentOrder(product, { quantity: entered_qty });
                this.props.close();
            }
        } else if (entered_qty <= 0) {
            this.env.services.dialog.add(AlertDialog, {
                title: _t('Invalid Quantity'),
                body: _t('Please enter a quantity greater than zero.'),
            });
        } else {
            let msg = 'Available total: ' + total_available + '. You entered: ' + entered_qty;
            this.env.services.dialog.add(AlertDialog, {
                title: _t('Please enter valid amount of quantity.'),
                body: _t(msg),
            });
        }
    }
}
