/** @odoo-module **/

import { SubmitOrderButton } from "@pos_restaurant/app/control_buttons/submit_order_button/submit_order_button";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

patch(SubmitOrderButton.prototype, {
    async click() {
        let order = this.env.services.pos.get_order();
        if (!order.get_partner()) {
            this.env.services.dialog.add(AlertDialog, {
                title: _t('Unknown Customer'),
                body: _t('Please Select Customer To Continue.'),
            });
            return;
        }
        return super.click(...arguments);
    }
});
