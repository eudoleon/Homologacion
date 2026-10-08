/** @odoo-module */

import { Component } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

export class PosOutOfStock extends Component {
    static template = 'bi_pos_warehouse_management.PosOutOfStock';
    static components = { Dialog };
    static props = {
        title: { type: String, optional: true },
        warning: { type: String, optional: true },
        loc_list: { type: Array, optional: true },
        confirmText: { type: String, optional: true },
        cancelText: { type: String, optional: true },
        close: Function,
    };

    Ok() {
        this.props.close();
    }

    cancel() {
        this.props.close();
    }
}
