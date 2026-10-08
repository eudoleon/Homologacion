/** @odoo-module **/

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { getCurrentOrder, getPartner, getPosConfig, openPartnerSelection } from "./pos_customer_required_utils";

patch(PaymentScreen.prototype, {
    async validateOrder(isForceValidate) {
        const order = getCurrentOrder(this);
        if (getPosConfig(this).require_customer === "payment" && !getPartner(order)) {
            await makeAwaitable(this.dialog, AlertDialog, {
                title: _t("An anonymous order cannot be confirmed"),
                body: _t("Please select a customer for this order."),
            });
            
            const { payload: newPartner } = await openPartnerSelection(this, getPartner(order));
            if (newPartner && order) {
                order.set_partner(newPartner);
                order.updatePricelist(newPartner);
            }
            
            return false;
        }
        return super.validateOrder(...arguments);
    },
});