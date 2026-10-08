/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";

patch(ControlButtons.prototype, {
    async applyDiscount(percent) {
        const order = this.pos.getOrder();
        if (order) {
            order.pc_discount = percent;
        }
        return super.applyDiscount(percent);
    },
});
