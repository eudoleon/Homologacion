/** @odoo-module **/

import { Component } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

export class StockRestrictionPopup extends Component {
    static template = "pos_restrict_negative_stock.StockRestrictionPopup";
    static components = { Dialog };
    static props = {
        title: { type: String, optional: true },
        productName: { type: String },
        availableStock: { type: Number },
        usedQty: { type: Number, optional: true },
        requestedQty: { type: Number, optional: true },
        maxAllowed: { type: Number, optional: true },
        reason: { type: String, optional: true },
        close: { type: Function },
    };

    confirm() {
        this.props.close();
    }
}
