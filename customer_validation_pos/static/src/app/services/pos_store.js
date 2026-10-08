/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";

patch(PosStore.prototype, {
    editPartnerContext(partner) {
        const ctx = super.editPartnerContext(...arguments);
        return {
            ...ctx,
            in_pos_partner_edit: true,
            pos_config_id: this.config?.id,
        };
    },
});
