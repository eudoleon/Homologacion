/** @odoo-module **/

import { PosStore } from "@point_of_sale/app/services/pos_store";
import { patch } from "@web/core/utils/patch";
import { getCurrentOrder, getPartner, getPosConfig, openPartnerSelection } from "./pos_customer_required_utils";

patch(PosStore.prototype, {
    async pay() {
        if (this.config.require_customer && this.config.require_customer !== "no") {
            const order = typeof this.get_order === 'function' ? this.get_order() : this.selectedOrder;
            if (order && !getPartner(order)) {
                // Forzar la selección de cliente antes de pagar abriendo la pantalla
                openPartnerSelection(this);
                return; // Cancelar el flujo de pago hasta que seleccionen el cliente
            }
        }
        return super.pay(...arguments);
    }
});