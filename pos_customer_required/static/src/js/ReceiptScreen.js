/** @odoo-module **/

import { ReceiptScreen } from "@point_of_sale/app/screens/receipt_screen/receipt_screen";
import { patch } from "@web/core/utils/patch";
import {
    addNewOrderSafe,
    getCurrentOrder,
    getPartner,
    getPosConfig,
    openPartnerSelection,
    removeOrderSafe,
    resolveNextScreenAfterNewOrder,
    showScreenSafe,
} from "./pos_customer_required_utils";

patch(ReceiptScreen.prototype, {
    async orderDone() {
        const oldOrder = this.currentOrder || getCurrentOrder(this);
        if (!oldOrder) {
            return;
        }

        const createdNewOrder = addNewOrderSafe(this);
        if (createdNewOrder) {
            removeOrderSafe(this, oldOrder);
        }

        if (getPosConfig(this).require_customer === "order") {
            while (true) {
                const currentOrder = getCurrentOrder(this);
                if (!currentOrder) {
                    return;
                }

                const currentPartner = getPartner(currentOrder);
                if (currentPartner) {
                    break;
                }

                const { confirmed, payload: newPartner } = await openPartnerSelection(this, currentPartner);
                if (confirmed && newPartner) {
                    currentOrder.set_partner(newPartner);
                    currentOrder.updatePricelist(newPartner);
                }
            }
        }

        const targetScreen = resolveNextScreenAfterNewOrder(createdNewOrder, this.nextScreen);
        showScreenSafe(this, targetScreen);

        const posConfig = getPosConfig(this);
        const pos = this.env?.services?.pos?.pos || this.env?.services?.pos || this.env?.pos || this.pos;
        if (posConfig.iface_customer_facing_display && typeof pos?.send_current_order_to_customer_facing_display === "function") {
            pos.send_current_order_to_customer_facing_display();
        }
    },
});