/** @odoo-module */

import { PosStore } from "@point_of_sale/app/services/pos_store";
import { patch } from "@web/core/utils/patch";

patch(PosStore.prototype, {
    async _processData(loadedData) {
        await super._processData(...arguments);
        this.db.all_cash_in_out_statement = loadedData['sh.cash.in.out'] || [];
        this.product_temlate_attribute_lineids = loadedData['product.template.attribute.line'] || [];
        this.product_temlate_attribute_ids = loadedData['product.template.attribute.value'] || [];
        this.db.product_temlate_attribute_line_by_id = loadedData['product_temlate_attribute_line_by_id'] || {};
        this.db.product_temlate_attribute_by_id = loadedData['product_temlate_attribute_by_id'] || {};
    },
    get_cashier_user_id() {
        return this.user.id || false;
    }
});
